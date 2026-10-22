"""Grant or revoke the admin role (app_metadata.role = "admin").

    cd backend
    python scripts/make_admin.py you@example.com            # grant
    python scripts/make_admin.py you@example.com --revoke   # revoke

The role lives in app_metadata, which only the service role can change, so
users can't make themselves admin. It is read from the access token: the
person must log out and back in (or wait for the token refresh, ~1 hour).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.db import get_db  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("email")
    parser.add_argument("--revoke", action="store_true", help="remove the admin role")
    args = parser.parse_args()

    client = get_db()
    if client is None:
        raise SystemExit("Supabase is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY).")
    email = args.email.strip().lower()
    user = next(
        (u for u in client.auth.admin.list_users() if (u.email or "").lower() == email), None
    )
    if user is None:
        raise SystemExit(f"No account with the email {email}. Sign up first.")
    if (user.app_metadata or {}).get("demo"):
        raise SystemExit("The demo account can't be an admin.")

    meta = dict(user.app_metadata or {})
    if args.revoke:
        meta.pop("role", None)
    else:
        meta["role"] = "admin"
    client.auth.admin.update_user_by_id(user.id, {"app_metadata": meta})
    state = "no longer an admin" if args.revoke else "now an admin"
    print(f"{email} is {state}. They need to log out and back in for it to apply.")


if __name__ == "__main__":
    main()
