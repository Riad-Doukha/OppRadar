"""In-memory repository — tests and DB-less local runs (DATA_BACKEND=memory).

Mimics the column defaults and the signup trigger of the SQL schema so the
API behaves the same against both backends.
"""

from __future__ import annotations

import copy
import threading
import uuid
from datetime import date, datetime, time, timezone
from typing import Any

from app.models import OpportunityFilters
from app.repositories.base import POSITIONED, ChildTable, NotFoundError, Row


def _now() -> datetime:
    return datetime.now(timezone.utc)


def profile_defaults(user_id: str, full_name: str = "") -> Row:
    """Column defaults of public.profiles."""
    return {
        "user_id": user_id,
        "full_name": full_name,
        "birth_year": None,
        "nationality": None,
        "country": None,
        "wilaya": None,
        "education_level": None,
        "field_of_study": None,
        "institution": None,
        "current_year": None,
        "graduation_year": None,
        "gpa_value": None,
        "gpa_scale": None,
        "interests": [],
        "opportunity_types": [],
        "preferred_location": None,
        "availability": None,
        "goal": None,
        "onboarding_step": 1,
        "onboarding_completed_at": None,
        "agent_started_at": None,
        "is_demo": False,
        "history_retention": "12_months",
        "agent_settings": {},
        "summary": "",
        "completeness": 0.0,
        "completeness_suggestions": [],
        "conflicts": [],
        "field_confidences": [],
        "created_at": _now(),
        "updated_at": _now(),
    }


def opportunity_defaults() -> Row:
    """Column defaults of public.opportunities."""
    return {
        "external_id": None,
        "type": "other",
        "mode": None,
        "location": "",
        "country": "",
        "language": "en",
        "deadline": None,
        "funding": None,
        "eligibility": [],
        "benefits": [],
        "summary": "",
        "url": "",
        "source": "manual",
        "trust_level": "unknown",
        "scam_flags": [],
        "added_via": "pipeline",
        "review_status": "approved",
        "review_note": None,
        "reviewed_at": None,
        "reviewed_by": None,
        "contact_email": None,
        "submitted_by": None,
    }


def notification_defaults(user_id: str) -> Row:
    """Column defaults of public.notification_settings."""
    return {
        "user_id": user_id,
        "email_enabled": True,
        "telegram_enabled": False,
        "telegram_chat_id": None,
        "telegram_linked_at": None,
        "threshold": 70,
        "frequency": "instant",
        "quiet_start": time(22, 0),
        "quiet_end": time(7, 0),
        "rule_new_match": True,
        "rule_deadline_reminders": True,
        "rule_application_updates": True,
        "rule_weekly_digest": True,
        "rule_profile_tips": False,
        "bundle_non_urgent": False,
    }


class MemoryRepository:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.profiles: dict[str, Row] = {}
        self.children: dict[str, list[Row]] = {}
        self.notification_settings: dict[str, Row] = {}
        self.consents: list[Row] = []
        self.documents: dict[str, Row] = {}
        self.files: dict[str, bytes] = {}
        self.opportunities: dict[str, Row] = {}
        self.opportunity_states: dict[tuple[str, str], Row] = {}
        self.notifications: dict[str, Row] = {}
        self.applications: dict[tuple[str, str], Row] = {}
        self.matches: dict[str, list[Row]] = {}
        self.ingestion_runs: list[Row] = []
        self.chat: list[Row] = []
        self.reservations: dict[str, Row] = {}

    # -- profile --------------------------------------------------------------- #
    def get_profile(self, user_id: str) -> Row | None:
        with self._lock:
            row = self.profiles.get(user_id)
            return copy.deepcopy(row) if row else None

    def ensure_profile(self, user_id: str, full_name: str = "") -> Row:
        with self._lock:
            if user_id not in self.profiles:
                self.profiles[user_id] = profile_defaults(user_id, full_name)
                self.notification_settings[user_id] = notification_defaults(user_id)
            return copy.deepcopy(self.profiles[user_id])

    def update_profile(self, user_id: str, fields: Row) -> Row:
        with self._lock:
            row = self.profiles.get(user_id)
            if row is None:
                raise NotFoundError(f"profile {user_id}")
            row.update(copy.deepcopy(fields), updated_at=_now())
            return copy.deepcopy(row)

    def delete_user(self, user_id: str) -> None:
        """Mirrors `on delete cascade` from auth.users."""
        with self._lock:
            self.profiles.pop(user_id, None)
            self.notification_settings.pop(user_id, None)
            for table in list(self.children):
                self.children[table] = [r for r in self.children[table] if r["user_id"] != user_id]
            self.consents = [c for c in self.consents if c["user_id"] != user_id]
            self.documents = {k: d for k, d in self.documents.items() if d["user_id"] != user_id}
            self.applications = {k: v for k, v in self.applications.items() if k[0] != user_id}
            self.chat = [m for m in self.chat if m["user_id"] != user_id]
            self.reservations.pop(user_id, None)
            self.matches.pop(user_id, None)
            self.notifications = {
                k: v for k, v in self.notifications.items() if v["user_id"] != user_id
            }
            self.opportunity_states = {
                k: v for k, v in self.opportunity_states.items() if k[0] != user_id
            }

    # -- child lists ------------------------------------------------------------- #
    def _rows(self, table: ChildTable) -> list[Row]:
        return self.children.setdefault(table, [])

    def list_children(self, table: ChildTable, user_id: str) -> list[Row]:
        with self._lock:
            rows = [copy.deepcopy(r) for r in self._rows(table) if r["user_id"] == user_id]
        if table in POSITIONED:
            return sorted(rows, key=lambda r: r.get("position", 0))
        return sorted(rows, key=lambda r: r.get("created_at") or _now())

    def replace_children(self, table: ChildTable, user_id: str, rows: list[Row]) -> list[Row]:
        with self._lock:
            kept = [r for r in self._rows(table) if r["user_id"] != user_id]
            self.children[table] = kept
            for i, row in enumerate(rows):
                self._insert(table, user_id, row, position=i)
        return self.list_children(table, user_id)

    def _insert(self, table: ChildTable, user_id: str, row: Row, position: int = 0) -> Row:
        new = {"id": str(uuid.uuid4()), "user_id": user_id, "created_at": _now(), **row}
        if table in POSITIONED:
            new.setdefault("position", position)
        self._rows(table).append(new)
        return copy.deepcopy(new)

    def insert_child(self, table: ChildTable, user_id: str, row: Row) -> Row:
        with self._lock:
            return self._insert(table, user_id, copy.deepcopy(row))

    def update_child(self, table: ChildTable, user_id: str, child_id: str, fields: Row) -> Row:
        with self._lock:
            for row in self._rows(table):
                if row["id"] == child_id and row["user_id"] == user_id:
                    row.update(copy.deepcopy(fields))
                    return copy.deepcopy(row)
        raise NotFoundError(f"{table} {child_id}")

    def delete_child(self, table: ChildTable, user_id: str, child_id: str) -> None:
        with self._lock:
            rows = self._rows(table)
            for i, row in enumerate(rows):
                if row["id"] == child_id and row["user_id"] == user_id:
                    del rows[i]
                    return
        raise NotFoundError(f"{table} {child_id}")

    # -- alerts & consent ---------------------------------------------------------- #
    def get_notification_settings(self, user_id: str) -> Row:
        with self._lock:
            row = self.notification_settings.setdefault(user_id, notification_defaults(user_id))
            return copy.deepcopy(row)

    def update_notification_settings(self, user_id: str, fields: Row) -> Row:
        with self._lock:
            row = self.notification_settings.setdefault(user_id, notification_defaults(user_id))
            row.update(copy.deepcopy(fields))
            return copy.deepcopy(row)

    def active_consents(self, user_id: str) -> list[str]:
        with self._lock:
            return [
                c["kind"]
                for c in self.consents
                if c["user_id"] == user_id and c["revoked_at"] is None
            ]

    def grant_consent(self, user_id: str, kind: str) -> None:
        with self._lock:
            if kind not in self.active_consents(user_id):
                self.consents.append(
                    {"user_id": user_id, "kind": kind, "granted_at": _now(), "revoked_at": None}
                )

    def revoke_consent(self, user_id: str, kind: str) -> None:
        with self._lock:
            for c in self.consents:
                if c["user_id"] == user_id and c["kind"] == kind and c["revoked_at"] is None:
                    c["revoked_at"] = _now()

    # -- documents + files ------------------------------------------------------------ #
    def create_document(self, row: Row) -> Row:
        with self._lock:
            new: Row = {
                "id": str(uuid.uuid4()),
                "kind": "cv",
                "status": "queued",
                "read_method": None,
                "warnings": [],
                "extraction": None,
                "error": None,
                "created_at": _now(),
                "updated_at": _now(),
                **row,
            }
            self.documents[new["id"]] = new
            return copy.deepcopy(new)

    def update_document(self, document_id: str, fields: Row) -> Row:
        with self._lock:
            row = self.documents.get(document_id)
            if row is None:
                raise NotFoundError(f"document {document_id}")
            row.update(copy.deepcopy(fields), updated_at=_now())
            return copy.deepcopy(row)

    def get_document(self, user_id: str, document_id: str) -> Row | None:
        with self._lock:
            row = self.documents.get(document_id)
            return copy.deepcopy(row) if row and row["user_id"] == user_id else None

    def list_documents(self, user_id: str) -> list[Row]:
        with self._lock:
            rows = [copy.deepcopy(r) for r in self.documents.values() if r["user_id"] == user_id]
        return sorted(rows, key=lambda r: r["created_at"], reverse=True)

    def delete_document(self, user_id: str, document_id: str) -> Row:
        with self._lock:
            row = self.get_document(user_id, document_id)
            if row is None:
                raise NotFoundError(f"document {document_id}")
            del self.documents[document_id]
            return row

    def put_file(self, path: str, data: bytes, content_type: str) -> None:
        with self._lock:
            self.files[path] = data

    def delete_file(self, path: str) -> None:
        with self._lock:
            self.files.pop(path, None)

    # -- opportunities ------------------------------------------------------------------ #
    def list_opportunities(self, filters: OpportunityFilters) -> tuple[list[Row], int]:
        today = date.today()
        with self._lock:
            rows = [
                copy.deepcopy(r)
                for r in self.opportunities.values()
                if r.get("review_status", "approved") == "approved"
            ]
        q = (filters.q or "").lower().split()
        country = (filters.country or "").lower()
        before = filters.deadline_before
        ids = None if filters.ids is None else set(filters.ids)
        excluded = set(filters.exclude_ids)
        after = filters.created_after
        url_like = (filters.url_like or "").lower()

        def keep(r: Row) -> bool:
            deadline = _as_date(r.get("deadline"))
            haystack = " ".join(
                str(r.get(k) or "")
                for k in ("title", "organizer", "summary", "location", "country")
            ).lower()
            return (
                (not filters.types or r["type"] in filters.types)
                and (not filters.modes or r.get("mode") in filters.modes)
                and (not country or (r.get("country") or "").lower() == country)
                and (not filters.trust_levels or r["trust_level"] in filters.trust_levels)
                and (filters.include_expired or deadline is None or deadline >= today)
                and (before is None or (deadline is not None and deadline <= before))
                and (not q or (any if filters.match_any else all)(t in haystack for t in q))
                and (not url_like or url_like in (r.get("url") or "").lower())
                and (ids is None or r["id"] in ids)
                and r["id"] not in excluded
                and (after is None or r["created_at"] >= after)
            )  # fmt: skip

        matched = [r for r in rows if keep(r)]
        matched.sort(key=lambda r: (_as_date(r.get("deadline")) or date.max, r["title"]))
        return matched[filters.offset : filters.offset + filters.limit], len(matched)

    def get_opportunity(self, opportunity_id: str) -> Row | None:
        row = self.get_opportunity_any(opportunity_id)
        return row if row and row.get("review_status", "approved") == "approved" else None

    def upsert_opportunities(self, rows: list[Row]) -> int:
        with self._lock:
            by_external = {r.get("external_id"): k for k, r in self.opportunities.items()}
            for row in rows:
                key = by_external.get(row.get("external_id")) or str(uuid.uuid4())
                base: dict[str, Any] = self.opportunities.get(
                    key, {"id": key, "created_at": _now()}
                )
                base.update(copy.deepcopy(row))
                self.opportunities[key] = base
        return len(rows)

    # -- review: any status ------------------------------------------------------------ #
    def _review_rows(self, statuses: list[str], trust_levels: list[str]) -> list[Row]:
        with self._lock:
            return [
                copy.deepcopy(r)
                for r in self.opportunities.values()
                if (not statuses or r.get("review_status", "approved") in statuses)
                and (not trust_levels or r.get("trust_level", "unknown") in trust_levels)
            ]

    def review_list(
        self,
        statuses: list[str],
        trust_levels: list[str],
        q: str | None,
        submitted_by: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Row], int]:
        words = (q or "").lower().split()

        def keep(r: Row) -> bool:
            text = " ".join(str(r.get(k) or "") for k in ("title", "organizer", "summary")).lower()
            return all(w in text for w in words) and (
                not submitted_by or r.get("submitted_by") == submitted_by
            )

        rows = [r for r in self._review_rows(statuses, trust_levels) if keep(r)]
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        return rows[offset : offset + limit], len(rows)

    def count_opportunities(
        self, statuses: list[str], trust_levels: list[str], active_only: bool = False
    ) -> int:
        today = date.today()
        return sum(
            1
            for r in self._review_rows(statuses, trust_levels)
            if not active_only
            or (deadline := _as_date(r.get("deadline"))) is None
            or deadline >= today
        )

    def get_opportunity_any(self, opportunity_id: str) -> Row | None:
        with self._lock:
            row = self.opportunities.get(opportunity_id)
            return copy.deepcopy(row) if row else None

    def create_opportunity(self, row: Row) -> Row:
        key = str(uuid.uuid4())
        with self._lock:
            self.opportunities[key] = {
                **opportunity_defaults(),
                **copy.deepcopy(row),
                "id": key,
                "created_at": _now(),
                "updated_at": _now(),
            }
            return copy.deepcopy(self.opportunities[key])

    def update_opportunity(self, opportunity_id: str, fields: Row) -> Row:
        with self._lock:
            row = self.opportunities.get(opportunity_id)
            if row is None:
                raise NotFoundError(f"opportunity {opportunity_id}")
            row.update(copy.deepcopy(fields), updated_at=_now())
            return copy.deepcopy(row)

    def delete_opportunity(self, opportunity_id: str) -> None:
        with self._lock:
            if self.opportunities.pop(opportunity_id, None) is None:
                raise NotFoundError(f"opportunity {opportunity_id}")
            # on delete cascade (saves, applications)
            self.applications = {
                k: v for k, v in self.applications.items() if k[1] != opportunity_id
            }
            self.opportunity_states = {
                k: v for k, v in self.opportunity_states.items() if k[1] != opportunity_id
            }
            self.matches = {
                uid: [m for m in rows if str(m["opportunity_id"]) != opportunity_id]
                for uid, rows in self.matches.items()
            }

    # -- AI pipeline -------------------------------------------------------------------- #
    def replace_matches(self, user_id: str, rows: list[Row]) -> None:
        with self._lock:
            self.matches[user_id] = [
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "created_at": _now(),
                    **copy.deepcopy(r),
                }
                for r in rows
            ]

    def get_matches(self, user_id: str) -> list[Row]:
        with self._lock:
            rows = [copy.deepcopy(r) for r in self.matches.get(user_id, [])]
        return sorted(rows, key=lambda r: -float(r["score"]))

    def agent_user_ids(self) -> list[str]:
        with self._lock:
            return [uid for uid, p in self.profiles.items() if p.get("agent_started_at")]

    def add_ingestion_run(self, row: Row) -> Row:
        with self._lock:
            saved = {"id": str(uuid.uuid4()), **copy.deepcopy(row)}
            self.ingestion_runs.append(saved)
            return copy.deepcopy(saved)

    def list_ingestion_runs(self, limit: int) -> list[Row]:
        with self._lock:
            rows = sorted(self.ingestion_runs, key=lambda r: r["started_at"], reverse=True)
            return copy.deepcopy(rows[:limit])

    # -- applications ---------------------------------------------------------------- #
    def list_applications(self, user_id: str) -> list[Row]:
        with self._lock:
            rows = [copy.deepcopy(a) for (uid, _), a in self.applications.items() if uid == user_id]
        return sorted(rows, key=lambda a: a["updated_at"], reverse=True)

    def upsert_application(self, user_id: str, opportunity_id: str, fields: Row) -> Row:
        with self._lock:
            if opportunity_id not in self.opportunities:
                raise NotFoundError(f"opportunity {opportunity_id}")
            row = self.applications.setdefault(
                (user_id, opportunity_id),
                {"id": str(uuid.uuid4()), "user_id": user_id, "opportunity_id": opportunity_id,
                 "status": "submitted", "reference": None, "notes": "", "submitted_at": None,
                 "created_at": _now()},
            )  # fmt: skip
            row.update(copy.deepcopy(fields), updated_at=_now())
            return copy.deepcopy(row)

    def delete_application(self, user_id: str, opportunity_id: str) -> None:
        with self._lock:
            if self.applications.pop((user_id, opportunity_id), None) is None:
                raise NotFoundError(f"application for {opportunity_id}")

    # -- chat ---------------------------------------------------------------------------- #
    def list_chat(self, user_id: str, limit: int) -> list[Row]:
        with self._lock:
            rows = [copy.deepcopy(m) for m in self.chat if m["user_id"] == user_id]
        return rows[-limit:]

    def add_chat(self, row: Row) -> Row:
        with self._lock:
            new = {"id": str(uuid.uuid4()), "citations": [], "opportunity_ids": [],
                   "created_at": _now(), **copy.deepcopy(row)}  # fmt: skip
            self.chat.append(new)
            return copy.deepcopy(new)

    def clear_chat(self, user_id: str) -> None:
        with self._lock:
            self.chat = [m for m in self.chat if m["user_id"] != user_id]

    # -- premium early access --------------------------------------------------------- #
    def get_reservation(self, user_id: str) -> Row | None:
        with self._lock:
            row = self.reservations.get(user_id)
            return copy.deepcopy(row) if row else None

    def upsert_reservation(self, user_id: str, fields: Row) -> Row:
        with self._lock:
            row = self.reservations.setdefault(
                user_id, {"user_id": user_id, "payment_method": None, "created_at": _now()}
            )
            row.update(copy.deepcopy(fields), updated_at=_now())
            return copy.deepcopy(row)

    def delete_reservation(self, user_id: str) -> None:
        with self._lock:
            if self.reservations.pop(user_id, None) is None:
                raise NotFoundError("reservation")

    def count_reservations(self, before: datetime | None = None) -> int:
        with self._lock:
            return sum(
                1 for r in self.reservations.values() if before is None or r["created_at"] <= before
            )

    # -- notifications -------------------------------------------------------------- #
    def _visible(self, user_id: str, since: datetime) -> list[Row]:
        return [
            n
            for n in self.notifications.values()
            if n["user_id"] == user_id and n["dismissed_at"] is None and n["created_at"] >= since
        ]

    def list_notifications(
        self, user_id: str, kinds: list[str] | None, since: datetime, limit: int
    ) -> list[Row]:
        with self._lock:
            rows = [n for n in self._visible(user_id, since) if not kinds or n["kind"] in kinds]
            rows.sort(key=lambda n: n["created_at"], reverse=True)
            return copy.deepcopy(rows[:limit])

    def count_unread_notifications(self, user_id: str, since: datetime) -> int:
        with self._lock:
            return sum(1 for n in self._visible(user_id, since) if n["read_at"] is None)

    def add_notification(self, row: Row) -> Row | None:
        with self._lock:
            key = row.get("dedupe_key")
            if key and any(
                n["user_id"] == row["user_id"] and n.get("dedupe_key") == key
                for n in self.notifications.values()
            ):
                return None
            new = {
                "id": str(uuid.uuid4()), "kind": "match", "body": "", "opportunity_id": None,
                "score": None, "deadline": None, "action_url": None, "dedupe_key": None,
                "read_at": None, "dismissed_at": None, "created_at": _now(), **copy.deepcopy(row),
            }  # fmt: skip
            self.notifications[new["id"]] = new
            return copy.deepcopy(new)

    def mark_notifications_read(self, user_id: str, ids: list[str] | None) -> None:
        with self._lock:
            for n in self.notifications.values():
                if (
                    n["user_id"] == user_id
                    and n["read_at"] is None
                    and (ids is None or n["id"] in ids)
                ):
                    n["read_at"] = _now()

    def dismiss_notification(self, user_id: str, notification_id: str) -> None:
        with self._lock:
            n = self.notifications.get(notification_id)
            if n is None or n["user_id"] != user_id:
                raise NotFoundError(f"notification {notification_id}")
            n["dismissed_at"] = _now()

    # -- per-user opportunity state ------------------------------------------------ #
    def list_opportunity_states(self, user_id: str) -> list[Row]:
        with self._lock:
            return [
                copy.deepcopy(r)
                for (uid, _), r in self.opportunity_states.items()
                if uid == user_id
            ]

    def set_opportunity_state(self, user_id: str, opportunity_id: str, fields: Row) -> Row:
        with self._lock:
            if opportunity_id not in self.opportunities:
                raise NotFoundError(f"opportunity {opportunity_id}")
            row = self.opportunity_states.setdefault(
                (user_id, opportunity_id),
                {
                    "user_id": user_id,
                    "opportunity_id": opportunity_id,
                    "saved_at": None,
                    "dismissed_at": None,
                },
            )
            row.update(copy.deepcopy(fields), updated_at=_now())
            return copy.deepcopy(row)


def _as_date(value: Any) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
