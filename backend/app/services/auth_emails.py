"""Supabase Auth emails (confirm sign-up, reset password, change email…) sent by
us through Gmail, via Supabase's "Send Email" auth hook.

Supabase signs each hook call (Standard Webhooks). We verify it, write the email
in the user's language (user_metadata.locale, set at sign-up) and link to our
/auth/callback with a token_hash, so the link works on any device or browser.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from html import escape
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from app.config import get_settings
from app.services import mailer

TOLERANCE = 5 * 60  # seconds: older signed calls are refused (replays)

# Where each link lands after /auth/callback, unless the app asked for another page.
NEXT = {"signup": "/onboarding", "invite": "/onboarding", "recovery": "/reset-password",
        "email_change": "/settings", "magiclink": "/dashboard"}  # fmt: skip

TEXT = {
    "en": {
        "signup": ("Confirm your OppRadar account", "Welcome! Confirm your email to start your scan.", "Confirm my email"),
        "invite": ("You're invited to OppRadar", "You've been invited to OppRadar. Accept to create your account.", "Accept the invitation"),
        "recovery": ("Reset your OppRadar password", "We got a request to reset your password. The link works once.", "Choose a new password"),
        "email_change": ("Confirm your new email", "Confirm this change of the email address on your OppRadar account.", "Confirm the change"),
        "magiclink": ("Your OppRadar sign-in link", "Use this link to sign in to OppRadar.", "Sign in"),
        "reauthentication": ("Your OppRadar code", "Enter this code to confirm it's you:", ""),
        "ignore": "If you didn't ask for this, you can ignore this email.",
    },
    "fr": {
        "signup": ("Confirmez votre compte OppRadar", "Bienvenue ! Confirmez votre e-mail pour lancer votre analyse.", "Confirmer mon e-mail"),
        "invite": ("Vous êtes invité sur OppRadar", "Vous avez été invité sur OppRadar. Acceptez pour créer votre compte.", "Accepter l'invitation"),
        "recovery": ("Réinitialisez votre mot de passe OppRadar", "Nous avons reçu une demande de réinitialisation de votre mot de passe. Le lien ne fonctionne qu'une fois.", "Choisir un nouveau mot de passe"),
        "email_change": ("Confirmez votre nouvel e-mail", "Confirmez ce changement d'adresse e-mail sur votre compte OppRadar.", "Confirmer le changement"),
        "magiclink": ("Votre lien de connexion OppRadar", "Utilisez ce lien pour vous connecter à OppRadar.", "Se connecter"),
        "reauthentication": ("Votre code OppRadar", "Saisissez ce code pour confirmer que c'est bien vous :", ""),
        "ignore": "Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail.",
    },
    "ar": {
        "signup": ("أكّد حسابك في OppRadar", "مرحبًا! أكّد بريدك الإلكتروني لبدء المسح.", "تأكيد بريدي"),
        "invite": ("دعوة للانضمام إلى OppRadar", "تمت دعوتك إلى OppRadar. اقبل الدعوة لإنشاء حسابك.", "قبول الدعوة"),
        "recovery": ("إعادة تعيين كلمة مرور OppRadar", "وصلنا طلب لإعادة تعيين كلمة مرورك. يعمل الرابط مرة واحدة.", "اختيار كلمة مرور جديدة"),
        "email_change": ("أكّد بريدك الجديد", "أكّد تغيير عنوان البريد الإلكتروني في حسابك على OppRadar.", "تأكيد التغيير"),
        "magiclink": ("رابط الدخول إلى OppRadar", "استخدم هذا الرابط لتسجيل الدخول إلى OppRadar.", "تسجيل الدخول"),
        "reauthentication": ("رمزك في OppRadar", "أدخل هذا الرمز لتأكيد هويتك:", ""),
        "ignore": "إذا لم تطلب ذلك، يمكنك تجاهل هذه الرسالة.",
    },
}  # fmt: skip


class HookError(Exception):
    pass


def verify(body: bytes, headers: dict[str, str], now: float | None = None) -> None:
    """Standard Webhooks signature check; raises HookError when it does not match."""
    secret = get_settings().supabase_email_hook_secret
    if not secret:
        raise HookError("hook secret not configured")
    msg_id, stamp = headers.get("webhook-id", ""), headers.get("webhook-timestamp", "")
    if not (msg_id and stamp.isdigit()):
        raise HookError("missing signature headers")
    if abs((now or time.time()) - int(stamp)) > TOLERANCE:
        raise HookError("stale timestamp")
    key = base64.b64decode(secret.split("whsec_", 1)[-1])
    signed = f"{msg_id}.{stamp}.".encode() + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    given = [s.split(",", 1)[-1] for s in headers.get("webhook-signature", "").split()]
    if not any(hmac.compare_digest(expected, sig) for sig in given):
        raise HookError("bad signature")


def _next(action: str, redirect_to: str) -> str:
    """The page the app asked for (redirect_to=…/auth/callback?next=/x), same-origin only."""
    asked = parse_qs(urlsplit(redirect_to or "").query).get("next", [""])[0]
    if asked.startswith("/") and not asked.startswith("//"):
        return asked
    return NEXT.get(action, "/dashboard")


def _link(action: str, token_hash: str, redirect_to: str) -> str:
    query = urlencode(
        {"token_hash": token_hash, "type": action, "next": _next(action, redirect_to)}
    )
    return f"{get_settings().app_url.rstrip('/')}/auth/callback?{query}"


def _email(locale: str, action: str, link: str | None, code: str = "") -> tuple[str, str]:
    t = TEXT.get(locale, TEXT["en"])
    subject, intro, button = t.get(action, t["magiclink"])
    if link:
        action_html = (
            f'<p><a href="{escape(link)}" style="display:inline-block;background:#8b34ff;color:#fff;'
            f'padding:12px 20px;border-radius:10px;font-weight:bold;text-decoration:none">{escape(button)}</a></p>'
        )
    else:
        action_html = (
            f'<p style="font-size:28px;font-weight:bold;letter-spacing:4px">{escape(code)}</p>'
        )
    body = f'<p>{escape(intro)}</p>{action_html}<p style="color:#6b6580;font-size:13px">{escape(t["ignore"])}</p>'
    return subject, mailer.layout(locale, body, None)


def messages(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(to, subject, html) for one hook call."""
    user, data = payload.get("user") or {}, payload.get("email_data") or {}
    action = data.get("email_action_type", "")
    locale = (user.get("user_metadata") or {}).get("locale") or "en"
    redirect_to = data.get("redirect_to", "")
    if action == "reauthentication":
        return [(user["email"], *_email(locale, action, None, data.get("token", "")))]
    if action == "email_change":
        # Supabase's naming is reversed here: token_hash goes with the NEW address,
        # token_hash_new with the current one (both are sent when Secure email change is on).
        out = []
        if data.get("token_hash") and user.get("new_email"):
            out.append(
                (
                    user["new_email"],
                    *_email(locale, action, _link(action, data["token_hash"], redirect_to)),
                )
            )
        if data.get("token_hash_new"):
            out.append(
                (
                    user["email"],
                    *_email(locale, action, _link(action, data["token_hash_new"], redirect_to)),
                )
            )
        return out
    return [
        (user["email"], *_email(locale, action, _link(action, data["token_hash"], redirect_to)))
    ]


def handle(body: bytes, headers: dict[str, str], payload: dict[str, Any]) -> None:
    """Verify and send; raises HookError (bad call) or RuntimeError (Gmail refused)."""
    verify(body, headers)
    for to, subject, html in messages(payload):
        if not mailer.send(to, subject, html):
            raise RuntimeError(f"email to {to} was not sent")
