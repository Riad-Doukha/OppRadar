"""Outgoing email (match alerts, digests, deadline reminders, test alert).

Sends through the Gmail API (services/gmail.py) once GMAIL_* is set; otherwise
it only logs, so dev and tests never send anything. Every alert email carries a
one-click unsubscribe link (signed, no login needed) that turns email alerts off.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from html import escape
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.services import gmail

log = logging.getLogger(__name__)

# Short, translated copy (the app's own messages live in the frontend).
TEXT = {
    "en": {
        "subject_one": "New match: {title}",
        "subject_many": "{count} new opportunities for you",
        "subject_scan": "Your OppRadar agent found new opportunities",
        "intro": "Here is what OppRadar found for you:",
        "deadline": "Deadline reminder",
        "open": "Open in OppRadar",
        "verify": "Always verify details on the official page. OppRadar never asks for payment.",
        "why": "You get this because email alerts are on.",
        "unsubscribe": "Turn off email alerts",
        "test_subject": "OppRadar test alert",
        "test_body": "Your email alerts work. Matches above your threshold will arrive here.",
    },
    "fr": {
        "subject_one": "Nouvelle correspondance : {title}",
        "subject_many": "{count} nouvelles opportunités pour vous",
        "subject_scan": "Votre agent OppRadar a trouvé de nouvelles opportunités",
        "intro": "Voici ce qu'OppRadar a trouvé pour vous :",
        "deadline": "Rappel d'échéance",
        "open": "Ouvrir dans OppRadar",
        "verify": "Vérifiez toujours les détails sur la page officielle. OppRadar ne demande jamais de paiement.",
        "why": "Vous recevez ce message car les alertes e-mail sont activées.",
        "unsubscribe": "Désactiver les alertes e-mail",
        "test_subject": "Alerte de test OppRadar",
        "test_body": "Vos alertes e-mail fonctionnent. Les correspondances au-dessus de votre seuil arriveront ici.",
    },
    "ar": {
        "subject_one": "فرصة مطابقة جديدة: {title}",
        "subject_many": "{count} فرص جديدة لك",
        "subject_scan": "وجد وكيل OppRadar فرصًا جديدة لك",
        "intro": "إليك ما وجده OppRadar لك:",
        "deadline": "تذكير بالموعد النهائي",
        "open": "افتح في OppRadar",
        "verify": "تحقّق دائمًا من التفاصيل في الصفحة الرسمية. لا يطلب OppRadar أي دفع أبدًا.",
        "why": "تصلك هذه الرسالة لأن تنبيهات البريد مفعّلة.",
        "unsubscribe": "إيقاف تنبيهات البريد",
        "test_subject": "تنبيه تجريبي من OppRadar",
        "test_body": "تنبيهات البريد تعمل. ستصلك هنا الفرص التي تتجاوز حدّك.",
    },
}


def _secret() -> bytes:
    s = get_settings()
    return (
        s.email_secret or s.supabase_jwt_secret or s.supabase_service_role_key or "dev"
    ).encode()


def unsubscribe_token(user_id: str) -> str:
    return hmac.new(_secret(), f"unsubscribe:{user_id}".encode(), hashlib.sha256).hexdigest()[:32]


def valid_unsubscribe(user_id: str, token: str) -> bool:
    return hmac.compare_digest(unsubscribe_token(user_id), token)


def unsubscribe_url(user_id: str) -> str:
    base = get_settings().api_public_url.rstrip("/")
    return f"{base}/email/unsubscribe?{urlencode({'u': user_id, 't': unsubscribe_token(user_id)})}"


def layout(locale: str, body_html: str, user_id: str | None) -> str:
    t = TEXT.get(locale, TEXT["en"])
    direction = "rtl" if locale == "ar" else "ltr"
    footer = (
        f'<p style="color:#6b6580;font-size:12px">{escape(t["why"])} '
        f'<a href="{escape(unsubscribe_url(user_id))}" style="color:#6b21d6">{escape(t["unsubscribe"])}</a></p>'
        if user_id
        else ""
    )
    return (
        f'<div dir="{direction}" style="font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#1e113e">'
        '<p style="font-size:20px;font-weight:bold;color:#8b34ff">OppRadar</p>'
        f"{body_html}"
        f'<p style="color:#6b6580;font-size:12px">{escape(t["verify"])}</p>{footer}</div>'
    )


def alert_email(locale: str, user_id: str, items: list[dict[str, Any]]) -> tuple[str, str]:
    """(subject, html) for one or more alerts. All AI/user text is escaped."""
    t = TEXT.get(locale, TEXT["en"])
    app = get_settings().app_url.rstrip("/")
    # The scan summary leads the email and names it; the matches follow.
    items = sorted(items, key=lambda n: n.get("kind") != "digest")
    if items[0].get("kind") == "digest":
        subject = t["subject_scan"]
    elif len(items) == 1:
        subject = t["subject_one"].format(title=items[0]["title"])
    else:
        subject = t["subject_many"].format(count=len(items))
    rows = []
    for n in items:
        label = (
            f'<p style="color:#a75c05;font-size:12px;margin:0">{escape(t["deadline"])}</p>'
            if n.get("kind") == "deadline"
            else ""
        )
        link = f"{app}{n.get('action_url') or '/notifications'}"
        rows.append(
            '<div style="border:1px solid #e7e2f0;border-radius:12px;padding:12px;margin:8px 0">'
            f'{label}<p style="font-weight:bold;margin:4px 0">{escape(n["title"])}</p>'
            f'<p style="margin:4px 0;color:#4a4360">{escape(n.get("body") or "")}</p>'
            f'<a href="{escape(link)}" style="color:#6b21d6;font-weight:bold">{escape(t["open"])}</a></div>'
        )
    return subject, layout(locale, f"<p>{escape(t['intro'])}</p>{''.join(rows)}", user_id)


def test_email(locale: str, user_id: str) -> tuple[str, str]:
    t = TEXT.get(locale, TEXT["en"])
    return t["test_subject"], layout(locale, f"<p>{escape(t['test_body'])}</p>", user_id)


def send(to: str, subject: str, html: str, user_id: str | None = None) -> bool:
    """True when the provider accepted it (or, without a provider, when it was logged)."""
    if not gmail.configured():
        log.info("email (not sent, Gmail not configured) to=%s subject=%r", to, subject)
        return True
    headers: dict[str, str] = {}
    if user_id:
        url = unsubscribe_url(user_id)
        headers = {
            "List-Unsubscribe": f"<{url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
    try:
        gmail.send(get_settings().mail_from, to, subject, html, headers)
        return True
    except httpx.HTTPError as exc:
        log.warning("email to %s failed: %s", to, exc)
        return False
