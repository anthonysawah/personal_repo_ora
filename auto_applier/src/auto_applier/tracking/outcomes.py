"""IMAP-based outcome tracker.

Connects to the user's mailbox (live.com / outlook.com / Gmail), fetches
recent emails, and matches them against submitted applications by company
name + recipient. Classifies each match as one of:

  - confirmation_received  ("we have received your application")
  - interview_invitation   ("we'd like to set up time", "schedule a call")
  - rejection              ("we have decided to move forward with other candidates")
  - other_response         (matched the company but unclear cue)

Updates the Application row with a status note. Doesn't change AppStatus
itself (keep submitted) — that's the "what we did" stage. We add notes on
the existing `error` field repurposed as a freeform note string when status
is `submitted`.

Auth: requires an IMAP App Password. For Outlook/live.com:
  https://account.microsoft.com/security  → App passwords (requires 2FA)
For Gmail:
  https://myaccount.google.com/apppasswords (requires 2FA)
"""

from __future__ import annotations

import email
import imaplib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable

from sqlmodel import select

from .. import config as _config
from ..db import session_scope
from ..models import Application, AppStatus, Job
from ..utils.logging import get_logger

log = get_logger(__name__)


CLASSIFIERS: list[tuple[str, list[str]]] = [
    (
        "rejection",
        [
            r"decided[\s-]to[\s-]move[\s-]forward[\s-]with[\s-]other",
            r"will[\s-]not[\s-]be[\s-]moving[\s-]forward",
            r"other[\s-]candidate",
            r"unfortunately",
            r"we[\s'-]re[\s-]unable[\s-]to[\s-]offer",
            r"position[\s-]has[\s-]been[\s-]filled",
            r"not[\s-]selected",
        ],
    ),
    (
        "interview_invitation",
        [
            r"schedule[\s-]a[\s-](call|chat|interview|conversation)",
            r"set[\s-]up[\s-]time",
            r"phone[\s-]screen",
            r"would[\s-]love[\s-]to[\s-]chat",
            r"book[\s-]a[\s-]time",
            r"calendly",
            r"next[\s-]step",
        ],
    ),
    (
        "confirmation_received",
        [
            r"we[\s'-]ve[\s-]received[\s-]your[\s-]application",
            r"we[\s'-]ve[\s-]got[\s-]your[\s-]application",
            r"thanks[\s-]for[\s-]applying",
            r"thank[\s-]you[\s-]for[\s-]applying",
            r"application[\s-]received",
            r"your[\s-]application[\s-]has[\s-]been[\s-]received",
            r"successfully[\s-]submitted",
        ],
    ),
]


def classify(text: str) -> str | None:
    t = (text or "").lower()
    for label, patterns in CLASSIFIERS:
        for pat in patterns:
            if re.search(pat, t):
                return label
    return None


@dataclass
class _Hit:
    app_id: int
    company: str
    label: str
    subject: str
    sender: str
    date: datetime


def _decode_part(part) -> str:
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except Exception:
        return payload.decode("utf-8", errors="replace")


def _get_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        chunks: list[str] = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                chunks.append(_decode_part(part))
        if chunks:
            return "\n".join(chunks)
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                chunks.append(_decode_part(part))
        return "\n".join(chunks)
    return _decode_part(msg)


def _connect_imap() -> imaplib.IMAP4_SSL:
    s = _config.settings
    if not s.imap_host or not s.imap_user or not s.imap_password:
        raise RuntimeError(
            "IMAP not configured. Set IMAP_HOST / IMAP_USER / IMAP_PASSWORD in .env. "
            "Use an App Password (not your account password)."
        )
    conn = imaplib.IMAP4_SSL(s.imap_host, s.imap_port)
    conn.login(s.imap_user, s.imap_password)
    conn.select(s.imap_folder)
    return conn


def _company_pattern(company: str) -> re.Pattern[str] | None:
    co = (company or "").strip()
    if not co:
        return None
    return re.compile(rf"\b{re.escape(co)}\b", re.IGNORECASE)


def fetch_outcomes(lookback_days: int | None = None) -> dict:
    """Scan recent inbox messages and update applications with outcome notes."""
    s = _config.settings
    days = lookback_days if lookback_days is not None else s.imap_lookback_days
    since = datetime.now(timezone.utc) - timedelta(days=days)

    stats = {
        "scanned": 0, "matched": 0,
        "confirmation_received": 0,
        "interview_invitation": 0, "rejection": 0,
        "other_response": 0,
    }

    with session_scope() as session:
        rows = session.exec(
            select(Application).where(Application.status == AppStatus.submitted)
        ).all()
        # Pre-compute (app_id, job, regex) so we don't N+1 inside the imap loop.
        app_index: list[tuple[Application, Job, re.Pattern[str]]] = []
        for a in rows:
            j = session.get(Job, a.job_id)
            if not j:
                continue
            pat = _company_pattern(j.company)
            if pat:
                app_index.append((a, j, pat))

    if not app_index:
        log.info("outcomes: no submitted applications to track")
        return stats

    conn = _connect_imap()
    try:
        date_str = since.strftime("%d-%b-%Y")
        typ, data = conn.search(None, f'(SINCE "{date_str}")')
        if typ != "OK":
            log.warning("imap search failed: %s", typ)
            return stats
        message_ids = data[0].split() if data and data[0] else []
        log.info("outcomes: scanning %d messages since %s", len(message_ids), date_str)

        hits: list[_Hit] = []
        for mid in message_ids:
            stats["scanned"] += 1
            typ, msg_data = conn.fetch(mid, "(RFC822)")
            if typ != "OK" or not msg_data:
                continue
            raw = msg_data[0][1]
            if not isinstance(raw, (bytes, bytearray)):
                continue
            msg = email.message_from_bytes(raw)
            subject = (msg.get("Subject") or "").strip()
            sender = (msg.get("From") or "").strip()
            try:
                msg_date = parsedate_to_datetime(msg.get("Date") or "") or since
            except Exception:
                msg_date = since
            body = _get_body(msg)
            haystack = f"{subject}\n{sender}\n{body}"

            label = classify(haystack)
            if not label:
                continue

            for app_obj, job, pat in app_index:
                if pat.search(haystack):
                    hits.append(
                        _Hit(
                            app_id=app_obj.id,
                            company=job.company,
                            label=label,
                            subject=subject[:200],
                            sender=sender[:200],
                            date=msg_date,
                        )
                    )
                    break  # only count once per email
    finally:
        try:
            conn.close()
        except Exception:
            pass
        conn.logout()

    # Persist hits
    with session_scope() as session:
        for h in hits:
            a = session.get(Application, h.app_id)
            if not a:
                continue
            note = (
                f"[{h.label}] {h.date.isoformat(timespec='minutes')} "
                f"<{h.sender}> — {h.subject}"
            )
            existing = a.confirmation_text or ""
            if note in existing:
                continue
            a.confirmation_text = (existing + "\n" + note).strip() if existing else note
            stats[h.label] += 1
            stats["matched"] += 1
            session.add(a)
        session.commit()

    return stats
