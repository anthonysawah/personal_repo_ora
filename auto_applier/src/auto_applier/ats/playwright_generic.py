"""Playwright + Claude-vision-driven generic form filler.

Routes any submission whose ATS isn't directly supported (Workday, iCIMS,
arbitrary company career sites) through a real browser. For each step:

  1. Take a screenshot of the page.
  2. Extract form-relevant elements (visible inputs/selects/textareas/buttons).
  3. Send screenshot + elements + candidate profile + answers to Claude Sonnet
     (vision input + prompt caching on the static system prompt + profile).
  4. Receive a JSON action plan (fill/click/select/upload/wait + done flag).
  5. Execute the actions, wait for network-idle, loop.
  6. Stop on captcha (return failure), confirmation page (success), login wall
     (failure with "needs account"), or max iterations.
"""

from __future__ import annotations

import base64
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

from .. import config as _config
from ..utils.logging import get_logger
from .base import SubmitContext, SubmitResult, SubmitterAdapter
from .registry import register

log = get_logger(__name__)

MAX_ITERATIONS = 12
NAV_TIMEOUT_MS = 60_000
ACTION_WAIT_MS = 800

CONFIRM_PATTERNS = [
    r"thank[\s-]you",
    r"application[\s-](received|submitted|complete)",
    r"successfully[\s-](applied|submitted)",
    r"we[\s'-]ve[\s-]received[\s-]your[\s-]application",
    r"your[\s-]application[\s-]has[\s-]been[\s-]received",
    r"submission[\s-](received|complete)",
]

CAPTCHA_PATTERNS = [
    r"recaptcha",
    r"hcaptcha",
    r"cloudflare[\s-]challenge",
    r"i'?m[\s-]not[\s-]a[\s-]robot",
    r"verify[\s-]you[\s-]are[\s-]human",
]

LOGIN_PATTERNS = [
    r"sign[\s-]in[\s-]to[\s-]continue",
    r"create[\s-]an[\s-]account[\s-]to[\s-]apply",
    r"log[\s-]in[\s-]to[\s-]your[\s-]account",
]


class _Action(BaseModel):
    type: str  # fill | click | select | check | upload_resume | wait | scroll
    selector: Optional[str] = None
    value: Optional[str] = None
    ms: Optional[int] = None


class _ActionPlan(BaseModel):
    actions: list[_Action] = Field(default_factory=list)
    done: bool = False  # set true after submitting the final form
    needs_human: bool = False
    reason: str = ""


_SYSTEM_INSTRUCTIONS = """\
You are a job-application form-filler. Each turn, I will show you:
  - a screenshot of the candidate's browser
  - a JSON list of visible form elements (each with selector/label/type/options)
  - the candidate's profile and a Q&A bank for common application questions
  - the actions you have already taken on this page (so you don't repeat)
  - the URL and ATS kind

Your job: return a JSON action plan that fills the visible form using the
candidate's information, then either clicks Next/Continue (multi-step) or
clicks the final Submit button. NEVER fabricate information that isn't in
the profile/qa_bank.

Action types you may use:
  - {"type": "fill",   "selector": "<css>", "value": "<text>"}
  - {"type": "select", "selector": "<css>", "value": "<option>"}
  - {"type": "check",  "selector": "<css>"}
  - {"type": "click",  "selector": "<css>"}
  - {"type": "upload_resume", "selector": "<css>"}    # uploads tailored PDF resume
  - {"type": "wait",   "ms": 1500}
  - {"type": "scroll", "selector": "<css>"}            # scroll element into view

Rules:
  - Use the EXACT selector strings I give you in the elements JSON.
  - Match each form field to the most relevant profile/qa_bank entry. If a
    field has no good match (e.g. "describe a time you failed" essay), set
    "needs_human": true and explain in "reason". Don't make up answers.
  - If the page has clearly navigated to a confirmation/thank-you state,
    set "done": true and return an empty actions list.
  - Prefer clicking Next/Continue over Submit unless this is the final page
    AND the form is fully filled. Submitting too early loses progress.
  - If you see a captcha, set "needs_human": true with reason "captcha".
  - If you see a login wall asking to create an account, set "needs_human"
    true with reason "login_required: <url>".

Output format (JSON only, no prose):
{
  "actions": [...],
  "done": false,
  "needs_human": false,
  "reason": ""
}
"""


def _re_any(haystack: str, patterns: list[str]) -> bool:
    h = haystack.lower()
    return any(re.search(p, h, re.IGNORECASE) for p in patterns)


def is_captcha_present(html_or_text: str) -> bool:
    return _re_any(html_or_text or "", CAPTCHA_PATTERNS)


def is_confirmation_present(html_or_text: str, url: str = "") -> bool:
    if _re_any(url or "", [r"/(confirmation|success|thanks|complete)"]):
        return True
    return _re_any(html_or_text or "", CONFIRM_PATTERNS)


def is_login_wall(html_or_text: str, url: str = "") -> bool:
    if _re_any(url or "", [r"/(login|signin|sign-in)"]):
        return True
    return _re_any(html_or_text or "", LOGIN_PATTERNS)


def _profile_compact_yaml(profile_dict: dict) -> str:
    """Emit a compact profile representation for the prompt (drop bulk like full bullets)."""
    keep_keys = (
        "personal",
        "work_authorization",
        "compensation",
        "target_titles",
        "target_locations",
        "remote_ok",
        "relocate_ok",
        "qa_bank",
    )
    compact = {k: profile_dict.get(k) for k in keep_keys if profile_dict.get(k)}
    return yaml.safe_dump(compact, sort_keys=False, allow_unicode=True)


_FORM_EXTRACT_JS = r"""
() => {
  function visible(el) {
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  }
  function buildSelector(el) {
    if (el.id) return '#' + CSS.escape(el.id);
    if (el.getAttribute('data-test')) return '[data-test=\"' + el.getAttribute('data-test') + '\"]';
    if (el.getAttribute('data-testid')) return '[data-testid=\"' + el.getAttribute('data-testid') + '\"]';
    if (el.name) return el.tagName.toLowerCase() + '[name=\"' + el.name + '\"]';
    // Build a path
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && parts.length < 5) {
      let part = cur.tagName.toLowerCase();
      if (cur.classList && cur.classList.length) {
        part += '.' + Array.from(cur.classList).slice(0,2).join('.');
      }
      const siblings = cur.parentElement ? Array.from(cur.parentElement.children).filter(s => s.tagName === cur.tagName) : [];
      if (siblings.length > 1) {
        part += ':nth-of-type(' + (siblings.indexOf(cur) + 1) + ')';
      }
      parts.unshift(part);
      cur = cur.parentElement;
    }
    return parts.join(' > ');
  }
  function labelFor(el) {
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
    if (el.id) {
      const lab = document.querySelector('label[for=\"' + CSS.escape(el.id) + '\"]');
      if (lab) return lab.innerText.trim();
    }
    let p = el.parentElement;
    for (let i = 0; i < 3 && p; i++, p = p.parentElement) {
      const lab = p.querySelector('label');
      if (lab && lab.innerText) return lab.innerText.trim();
    }
    return el.placeholder || el.title || '';
  }
  const out = [];
  document.querySelectorAll('input, select, textarea, button').forEach(el => {
    if (!visible(el)) return;
    const tag = el.tagName.toLowerCase();
    const t = el.type || null;
    if (tag === 'input' && (t === 'hidden' || t === 'submit' && el.value === '')) return;
    const o = {
      tag, type: t,
      selector: buildSelector(el),
      label: labelFor(el).slice(0, 200),
      placeholder: el.placeholder || null,
      name: el.name || null,
      id: el.id || null,
      required: !!el.required,
      value: tag === 'input' || tag === 'textarea' ? (el.value || '') : null,
      text: tag === 'button' ? (el.innerText || el.value || '').trim().slice(0, 80) : null,
    };
    if (tag === 'select') {
      o.options = Array.from(el.options).slice(0, 50).map(opt => ({value: opt.value, label: (opt.textContent || '').trim().slice(0,80)}));
    }
    out.push(o);
  });
  return out.slice(0, 200);  // cap
}
"""


def _client():
    import anthropic

    if not _config.settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(
        api_key=_config.settings.anthropic_api_key, max_retries=6
    )


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    return t.strip()


def _plan_actions(
    *,
    screenshot_png: bytes,
    elements: list[dict],
    profile_compact: str,
    answers: dict[str, str],
    history: list[dict],
    page_url: str,
    ats_kind: str,
    iteration: int,
) -> _ActionPlan:
    client = _client()
    image_b64 = base64.standard_b64encode(screenshot_png).decode("ascii")

    user_blocks: list[dict] = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": image_b64},
        },
        {
            "type": "text",
            "text": (
                f"<page url=\"{page_url}\" ats=\"{ats_kind}\" iteration=\"{iteration}\">\n"
                f"<elements>\n{json.dumps(elements, indent=2)[:18000]}\n</elements>\n"
                f"<answers>\n{json.dumps(answers, indent=2)[:6000]}\n</answers>\n"
                f"<history>\n{json.dumps(history, indent=2)[:4000]}\n</history>\n"
                "</page>\nReturn the JSON action plan."
            ),
        },
    ]

    resp = client.messages.create(
        model=_config.settings.tailor_model,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_INSTRUCTIONS + "\n\n<candidate_profile>\n" + profile_compact + "\n</candidate_profile>",
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_blocks}],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    data = json.loads(_strip_fences(text))
    return _ActionPlan.model_validate(data)


def _execute_action(page, action: _Action, resume_pdf_path: Path) -> dict:
    sel = action.selector or ""
    t = action.type
    log.info("playwright action type=%s selector=%s", t, sel[:80])
    try:
        if t == "fill" and action.value is not None:
            page.fill(sel, action.value, timeout=15_000)
        elif t == "select" and action.value is not None:
            page.select_option(sel, action.value, timeout=15_000)
        elif t == "check":
            page.check(sel, timeout=15_000)
        elif t == "click":
            page.click(sel, timeout=15_000)
        elif t == "upload_resume":
            page.set_input_files(sel, str(resume_pdf_path), timeout=15_000)
        elif t == "scroll":
            page.locator(sel).scroll_into_view_if_needed(timeout=15_000)
        elif t == "wait":
            page.wait_for_timeout(int(action.ms or 1000))
        else:
            return {"ok": False, "type": t, "selector": sel, "error": f"unknown action {t}"}
        page.wait_for_timeout(ACTION_WAIT_MS)
        return {"ok": True, "type": t, "selector": sel, "value": action.value}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "type": t, "selector": sel, "error": str(e)[:200]}


@register("__fallback__")
@register("unknown")
@register("workday")
@register("icims")
class PlaywrightGenericSubmitter(SubmitterAdapter):
    name = "playwright_generic"

    def submit(self, ctx: SubmitContext) -> SubmitResult:
        if ctx.dry_run:
            return SubmitResult(
                ok=True,
                confirmation_text=f"DRY RUN: would open {ctx.job.apply_url} with Playwright + Claude",
                extra={"apply_url": ctx.job.apply_url, "fallback": True},
            )

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return SubmitResult(
                ok=False,
                error=(
                    "Playwright not installed. Run:\n"
                    "  pip install 'auto_applier[playwright]'\n"
                    "  playwright install chromium"
                ),
            )

        return self._do_submit(ctx, sync_playwright)

    def _do_submit(self, ctx: SubmitContext, sync_playwright) -> SubmitResult:
        apply_url = ctx.job.apply_url or ctx.job.jd_url
        if not apply_url:
            return SubmitResult(ok=False, error="no apply_url on job")

        # Where to dump screenshots / artifacts.
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        art_dir = _config.settings.artifacts_dir / day / f"app-{ctx.application.id}" / "playwright"
        art_dir.mkdir(parents=True, exist_ok=True)

        profile_dict = ctx.profile.model_dump()
        profile_compact = _profile_compact_yaml(profile_dict)
        history: list[dict] = []
        last_screenshot_path: str | None = None

        headless = bool(getattr(_config.settings, "playwright_headless", False))

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                viewport={"width": 1280, "height": 1024},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()

            try:
                page.goto(apply_url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
                page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT_MS)
            except Exception as e:  # noqa: BLE001
                browser.close()
                return SubmitResult(ok=False, error=f"navigation failed: {e}")

            for it in range(MAX_ITERATIONS):
                screenshot_path = art_dir / f"step-{it:02d}.png"
                screenshot_bytes = page.screenshot(type="png", full_page=False)
                screenshot_path.write_bytes(screenshot_bytes)
                last_screenshot_path = str(screenshot_path)

                page_text = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
                page_url = page.url

                if is_captcha_present(page_text):
                    browser.close()
                    return SubmitResult(
                        ok=False,
                        error="captcha detected — apply manually",
                        confirmation_screenshot_path=last_screenshot_path,
                        extra={"apply_url": apply_url, "iter": it},
                    )

                if is_confirmation_present(page_text, page_url):
                    log.info("confirmation detected at iter=%d", it)
                    browser.close()
                    return SubmitResult(
                        ok=True,
                        confirmation_text=page_text[:2000],
                        confirmation_screenshot_path=last_screenshot_path,
                        extra={"apply_url": apply_url, "iter": it, "final_url": page_url},
                    )

                if is_login_wall(page_text, page_url) and it == 0:
                    browser.close()
                    return SubmitResult(
                        ok=False,
                        error=f"login required at {page_url} — needs human account creation",
                        confirmation_screenshot_path=last_screenshot_path,
                    )

                try:
                    elements = page.evaluate(_FORM_EXTRACT_JS) or []
                except Exception as e:  # noqa: BLE001
                    log.warning("form extraction failed: %s", e)
                    elements = []

                if not elements:
                    log.warning("no form elements found at iter=%d", it)
                    browser.close()
                    return SubmitResult(
                        ok=False,
                        error="no form elements detected on page",
                        confirmation_screenshot_path=last_screenshot_path,
                    )

                try:
                    plan = _plan_actions(
                        screenshot_png=screenshot_bytes,
                        elements=elements,
                        profile_compact=profile_compact,
                        answers=ctx.answers,
                        history=history[-10:],
                        page_url=page_url,
                        ats_kind=str(ctx.job.ats_kind),
                        iteration=it,
                    )
                except Exception as e:  # noqa: BLE001
                    browser.close()
                    return SubmitResult(
                        ok=False,
                        error=f"Claude planning failed: {e}",
                        confirmation_screenshot_path=last_screenshot_path,
                    )

                if plan.needs_human:
                    browser.close()
                    return SubmitResult(
                        ok=False,
                        error=f"needs_human: {plan.reason}",
                        confirmation_screenshot_path=last_screenshot_path,
                        extra={"apply_url": apply_url, "iter": it},
                    )

                if plan.done and not plan.actions:
                    page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT_MS)
                    final_text = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
                    if is_confirmation_present(final_text, page.url):
                        final_path = art_dir / f"step-{it+1:02d}-confirm.png"
                        final_path.write_bytes(page.screenshot(type="png", full_page=False))
                        browser.close()
                        return SubmitResult(
                            ok=True,
                            confirmation_text=final_text[:2000],
                            confirmation_screenshot_path=str(final_path),
                            extra={"apply_url": apply_url, "iter": it + 1, "final_url": page.url},
                        )

                for action in plan.actions:
                    res = _execute_action(page, action, ctx.resume_pdf_path)
                    history.append(res)
                    if not res["ok"]:
                        log.warning("action failed: %s", res)
                        # don't bail — Claude may recover next iteration

                # Let any navigations / SPA transitions settle.
                try:
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(0.5)

            browser.close()
            return SubmitResult(
                ok=False,
                error=f"max iterations ({MAX_ITERATIONS}) reached without confirmation",
                confirmation_screenshot_path=last_screenshot_path,
            )
