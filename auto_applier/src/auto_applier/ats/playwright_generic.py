from __future__ import annotations

from ..utils.logging import get_logger
from .base import SubmitContext, SubmitResult, SubmitterAdapter
from .registry import register

log = get_logger(__name__)


@register("__fallback__")
@register("unknown")
@register("workday")
@register("icims")
class PlaywrightGenericSubmitter(SubmitterAdapter):
    """Playwright-driven, LLM-assisted generic form filler.

    Phase 3 implementation. For MVP this returns a staged / deferred result
    so the pipeline can still run end-to-end without optional deps installed.
    Install with `pip install 'auto_applier[playwright]' && playwright install chromium`.
    """

    name = "playwright_generic"

    def submit(self, ctx: SubmitContext) -> SubmitResult:
        if ctx.dry_run:
            return SubmitResult(
                ok=True,
                confirmation_text=f"DRY RUN: would open {ctx.job.apply_url} with Playwright + Claude",
                extra={"apply_url": ctx.job.apply_url, "fallback": True},
            )

        # Check if playwright is available.
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError:
            return SubmitResult(
                ok=False,
                error=(
                    "Playwright not installed. Run:\n"
                    "  pip install 'auto_applier[playwright]'\n"
                    "  playwright install chromium"
                ),
            )

        # Phase 3 real implementation: open the URL, screenshot, pass DOM + screenshot
        # + profile + answers to Claude, receive a JSON action list, execute it, loop
        # until a confirmation heuristic fires, then screenshot the confirmation page.
        # For MVP we defer with a clear message so the application row shows up as
        # failed and the user can fill manually.
        return SubmitResult(
            ok=False,
            error=(
                "Playwright form-filler not yet implemented (Phase 3). "
                f"Apply manually at {ctx.job.apply_url}"
            ),
        )
