# Local JSON storage with a tiny, replaceable interface (users, opportunities,
# matches, notifications, chat history). No database — one JSON file per
# collection, atomic writes, thread-safe for the background agent.
# Called by: api.py, agent.py, notebooks. A real DB can replace this module only.

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

from oppradar_ai.config import get_settings
from oppradar_ai.schemas import (
    ChatTurn,
    MatchResult,
    Notification,
    Opportunity,
    Profile,
)

logger = logging.getLogger(__name__)


class StoreError(RuntimeError):
    """Unexpected storage failure (unreadable/corrupt store file)."""


def make_id(prefix: str, *parts: str) -> str:
    """Deterministic short id, e.g. make_id("opp", title, organizer).

    Example:
        >>> make_id("opp", "ML Intern", "Ooredoo")
        'opp-3f2a1c9d0e7b'
    """
    blob = "|".join(parts).lower().strip()
    return f"{prefix}-{hashlib.sha1(blob.encode('utf-8')).hexdigest()[:12]}"


class JsonStore:
    """Tiny key/value storage over one JSON file per collection.

    Example:
        >>> store = JsonStore()
        >>> store.save_opportunities([opp])      # upsert by id
        >>> store.list_opportunities()
    """

    COLLECTIONS = ("users", "opportunities", "matches", "notifications", "chat")

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or get_settings().store_dir
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # -- generic file handling ------------------------------------------------- #
    def _path(self, collection: str) -> Path:
        return self.root / f"{collection}.json"

    def _load(self, collection: str) -> dict[str, Any]:
        path = self._path(collection)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreError(f"store file {path.name} is unreadable: {exc}") from exc
        if not isinstance(data, dict):
            raise StoreError(f"store file {path.name} must contain a JSON object")
        return data

    def _save(self, collection: str, data: dict[str, Any]) -> None:
        path = self._path(collection)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)  # atomic on the same filesystem

    def reset(self) -> None:
        """Delete every stored collection (notebooks and tests use this)."""
        with self._lock:
            for collection in self.COLLECTIONS:
                self._path(collection).unlink(missing_ok=True)
        logger.info("store reset at %s", self.root)

    # -- users (Profile) -------------------------------------------------------- #
    def save_user(self, profile: Profile) -> Profile:
        """Insert or update one profile, keyed by user_id."""
        with self._lock:
            users = self._load("users")
            users[profile.user_id] = profile.model_dump(mode="json")
            self._save("users", users)
        logger.info("saved profile for %s (%s)", profile.user_id, profile.full_name or "no name")
        return profile

    def get_user(self, user_id: str) -> Profile | None:
        """Return one profile, or None when unknown."""
        with self._lock:
            data = self._load("users").get(user_id)
        return Profile.model_validate(data) if data else None

    def list_users(self) -> list[Profile]:
        """Return every stored profile."""
        with self._lock:
            data = list(self._load("users").values())
        return [Profile.model_validate(row) for row in data]

    # -- opportunities ---------------------------------------------------------- #
    def save_opportunities(self, opportunities: list[Opportunity]) -> list[Opportunity]:
        """Upsert opportunities by id (generating a stable id when missing)."""
        saved: list[Opportunity] = []
        with self._lock:
            store = self._load("opportunities")
            for opp in opportunities:
                opp.id = opp.id or make_id("opp", opp.url or opp.title, opp.organizer)
                store[opp.id] = opp.model_dump(mode="json")
                saved.append(opp)
            self._save("opportunities", store)
        logger.info("saved %d opportunities (store now has %d)", len(saved), len(store))
        return saved

    def get_opportunity(self, opportunity_id: str) -> Opportunity | None:
        with self._lock:
            data = self._load("opportunities").get(opportunity_id)
        return Opportunity.model_validate(data) if data else None

    def list_opportunities(self) -> list[Opportunity]:
        """Return every stored opportunity."""
        with self._lock:
            data = list(self._load("opportunities").values())
        return [Opportunity.model_validate(row) for row in data]

    # -- matches ------------------------------------------------------------------ #
    def save_matches(self, profile_id: str, matches: list[MatchResult]) -> list[MatchResult]:
        """Replace the match set of one profile."""
        with self._lock:
            store = self._load("matches")
            store[profile_id] = [m.model_dump(mode="json") for m in matches]
            self._save("matches", store)
        logger.info("saved %d matches for %s", len(matches), profile_id)
        return matches

    def get_matches(self, profile_id: str) -> list[MatchResult]:
        with self._lock:
            data = self._load("matches").get(profile_id, [])
        return [MatchResult.model_validate(row) for row in data]

    # -- notifications ------------------------------------------------------------- #
    def add_notifications(self, notifications: list[Notification]) -> list[Notification]:
        """Append notifications (assigning ids) and persist them."""
        with self._lock:
            store = self._load("notifications")
            rows = store.setdefault("items", [])
            for note in notifications:
                note.id = note.id or make_id(
                    "ntf", note.opportunity_id, note.profile_id, str(note.created_at)
                )
                rows.append(note.model_dump(mode="json"))
            self._save("notifications", store)
        logger.info("stored %d notifications", len(notifications))
        return notifications

    def notification_history(self, profile_id: str, limit: int = 50) -> list[Notification]:
        """Most recent notifications for one profile (newest last)."""
        with self._lock:
            rows = self._load("notifications").get("items", [])
        notes = [Notification.model_validate(r) for r in rows if r.get("profile_id") == profile_id]
        return notes[-limit:]

    def sent_count_today(self, profile_id: str, today: date | None = None) -> int:
        """How many instant notifications were already SENT today (for the daily cap)."""
        today = today or date.today()
        with self._lock:
            rows = self._load("notifications").get("items", [])
        return sum(
            1
            for r in rows
            if r.get("profile_id") == profile_id
            and r.get("status") == "sent"
            and datetime.fromisoformat(r["created_at"]).date() == today
        )

    # -- chat --------------------------------------------------------------------- #
    def append_chat(self, profile_id: str, turn: ChatTurn) -> None:
        """Append one chat turn (user or assistant)."""
        with self._lock:
            store = self._load("chat")
            store.setdefault(profile_id, []).append(turn.model_dump(mode="json"))
            self._save("chat", store)

    def chat_history(self, profile_id: str, limit: int = 20) -> list[ChatTurn]:
        """The last chat turns for one profile (oldest first)."""
        with self._lock:
            rows = self._load("chat").get(profile_id, [])
        return [ChatTurn.model_validate(r) for r in rows[-limit:]]
