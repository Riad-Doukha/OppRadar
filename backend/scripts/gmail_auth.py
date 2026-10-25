"""One-time: authorize the sending Gmail account and print GMAIL_REFRESH_TOKEN.

    cd backend
    python scripts/gmail_auth.py                      # uses GMAIL_CLIENT_ID / _SECRET from .env
    python scripts/gmail_auth.py --client-id ... --client-secret ...

Needs an OAuth client of type "Desktop app" (Google Cloud console), with the
Gmail API enabled and the consent screen published ("In production"); in
"Testing" the refresh token stops working after 7 days. Sign in with the account
that will send the emails. Only the gmail.send scope is asked for: the app can
send mail as that account, never read it.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import secrets
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services.gmail import SCOPE, TOKEN_URL  # noqa: E402

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--client-id", default=settings.gmail_client_id)
    parser.add_argument("--client-secret", default=settings.gmail_client_secret)
    args = parser.parse_args()
    if not (args.client_id and args.client_secret):
        sys.exit("Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET, or pass them as options.")

    result: dict[str, str] = {}
    done = threading.Event()

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            result.update({k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OppRadar: done. You can close this tab and go back to the terminal.")
            done.set()

        def log_message(self, *_: object) -> None:
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Callback)
    redirect = f"http://127.0.0.1:{server.server_port}/"
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    state = secrets.token_urlsafe(16)
    url = AUTH_URL + "?" + urlencode({
        "client_id": args.client_id, "redirect_uri": redirect, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state,
        "code_challenge": challenge.decode(), "code_challenge_method": "S256",
    })  # fmt: skip
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("Opening Google sign-in. If no browser opens, visit:\n\n" + url + "\n")
    webbrowser.open(url)
    done.wait()
    server.shutdown()

    if result.get("state") != state or "code" not in result:
        sys.exit(f"Authorization failed: {result.get('error', 'no code returned')}")
    r = httpx.post(TOKEN_URL, data={
        "client_id": args.client_id, "client_secret": args.client_secret, "code": result["code"],
        "code_verifier": verifier, "grant_type": "authorization_code", "redirect_uri": redirect,
    }, timeout=20)  # fmt: skip
    r.raise_for_status()
    token = r.json().get("refresh_token")
    if not token:
        sys.exit("Google returned no refresh token. Remove the app's access at "
                 "https://myaccount.google.com/permissions and run this again.")  # fmt: skip
    print("Add this to your environment (.env locally, Render in production):\n")
    print(f"GMAIL_REFRESH_TOKEN={token}\n")
    print("Keep it secret: it lets anyone send email as this account.")


if __name__ == "__main__":
    main()
