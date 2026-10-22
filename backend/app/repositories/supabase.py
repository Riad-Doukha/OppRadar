"""Supabase-backed repository (PostgREST + Storage) using the service-role client.

The service role bypasses RLS, so every user-scoped query filters on user_id
explicitly — never drop those .eq("user_id", ...) calls.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import date, datetime, time, timezone
from typing import Any

from postgrest.exceptions import APIError
from supabase import Client

from app.models import OpportunityFilters
from app.repositories.base import POSITIONED, ChildTable, NotFoundError, Row

OPPORTUNITY_COLUMNS = (
    "id,external_id,title,organizer,type,mode,location,country,language,deadline,funding,"
    "eligibility,benefits,summary,url,source,trust_level,scam_flags,added_via,created_at"
)


def _json(fields: Row) -> Row:
    """Make dates/times JSON-serialisable for PostgREST."""
    return {
        k: v.isoformat() if isinstance(v, (date, datetime, time)) else v for k, v in fields.items()
    }


def _first(data: list[Row], what: str) -> Row:
    if not data:
        raise NotFoundError(what)
    return data[0]


class SupabaseRepository:
    def __init__(self, client_factory: Callable[[], Client], bucket: str) -> None:
        # One client per thread: supabase-py talks HTTP/2 over a single shared
        # connection, which breaks when several threads use it at once
        # (WinError 10035 on Windows) — and FastAPI + services.parallel do.
        self._client_factory = client_factory
        self._local = threading.local()
        self.bucket = bucket

    @property
    def db(self) -> Client:
        client = getattr(self._local, "client", None)
        if client is None:
            client = self._local.client = self._client_factory()
        return client

    # -- profile --------------------------------------------------------------- #
    def get_profile(self, user_id: str) -> Row | None:
        data = self.db.table("profiles").select("*").eq("user_id", user_id).execute().data
        return data[0] if data else None

    def ensure_profile(self, user_id: str, full_name: str = "") -> Row:
        # The on_auth_user_created trigger normally creates both rows; this
        # covers users created before the trigger existed.
        row = self.get_profile(user_id)
        if row is not None:
            return row
        self.db.table("profiles").upsert(
            {"user_id": user_id, "full_name": full_name},
            on_conflict="user_id",
            ignore_duplicates=True,
        ).execute()
        self.db.table("notification_settings").upsert(
            {"user_id": user_id}, on_conflict="user_id", ignore_duplicates=True
        ).execute()
        return _first(
            self.db.table("profiles").select("*").eq("user_id", user_id).execute().data,
            f"profile {user_id}",
        )

    def update_profile(self, user_id: str, fields: Row) -> Row:
        data = self.db.table("profiles").update(_json(fields)).eq("user_id", user_id).execute().data
        return _first(data, f"profile {user_id}")

    # -- child lists ------------------------------------------------------------- #
    def list_children(self, table: ChildTable, user_id: str) -> list[Row]:
        order = (
            "position"
            if table in POSITIONED
            else ("created_at" if table in {"experiences", "certificates"} else "id")
        )
        return self.db.table(table).select("*").eq("user_id", user_id).order(order).execute().data

    def replace_children(self, table: ChildTable, user_id: str, rows: list[Row]) -> list[Row]:
        # Not atomic over PostgREST; the wizard re-sends whole lists on every
        # autosave, so a failed insert heals on the next save.
        self.db.table(table).delete().eq("user_id", user_id).execute()
        if rows:
            payload = [
                {
                    **_json(row),
                    "user_id": user_id,
                    **({"position": i} if table in POSITIONED else {}),
                }
                for i, row in enumerate(rows)
            ]
            self.db.table(table).insert(payload).execute()
        return self.list_children(table, user_id)

    def insert_child(self, table: ChildTable, user_id: str, row: Row) -> Row:
        data = self.db.table(table).insert({**_json(row), "user_id": user_id}).execute().data
        return _first(data, table)

    def update_child(self, table: ChildTable, user_id: str, child_id: str, fields: Row) -> Row:
        data = (
            self.db.table(table)
            .update(_json(fields))
            .eq("id", child_id)
            .eq("user_id", user_id)
            .execute()
            .data
        )
        return _first(data, f"{table} {child_id}")

    def delete_child(self, table: ChildTable, user_id: str, child_id: str) -> None:
        data = (
            self.db.table(table).delete().eq("id", child_id).eq("user_id", user_id).execute().data
        )
        _first(data, f"{table} {child_id}")

    # -- alerts & consent ---------------------------------------------------------- #
    def delete_user(self, user_id: str) -> None:
        # Every public table references auth.users with on delete cascade.
        self.db.auth.admin.delete_user(user_id)

    def get_notification_settings(self, user_id: str) -> Row:
        data = (
            self.db.table("notification_settings").select("*").eq("user_id", user_id).execute().data
        )
        if data:
            return data[0]
        return _first(
            self.db.table("notification_settings").insert({"user_id": user_id}).execute().data,
            f"notification settings {user_id}",
        )

    def update_notification_settings(self, user_id: str, fields: Row) -> Row:
        self.get_notification_settings(user_id)  # make sure the row exists
        data = (
            self.db.table("notification_settings")
            .update(_json(fields))
            .eq("user_id", user_id)
            .execute()
            .data
        )
        return _first(data, f"notification settings {user_id}")

    def active_consents(self, user_id: str) -> list[str]:
        data = (
            self.db.table("consents")
            .select("kind")
            .eq("user_id", user_id)
            .is_("revoked_at", "null")
            .execute()
            .data
        )
        return [row["kind"] for row in data]

    def grant_consent(self, user_id: str, kind: str) -> None:
        if kind not in self.active_consents(user_id):
            self.db.table("consents").insert({"user_id": user_id, "kind": kind}).execute()

    def revoke_consent(self, user_id: str, kind: str) -> None:
        (
            self.db.table("consents")
            .update({"revoked_at": datetime.now(timezone.utc).isoformat()})
            .eq("user_id", user_id)
            .eq("kind", kind)
            .is_("revoked_at", "null")
            .execute()
        )

    # -- documents + files ------------------------------------------------------------ #
    def create_document(self, row: Row) -> Row:
        return _first(self.db.table("documents").insert(_json(row)).execute().data, "document")

    def update_document(self, document_id: str, fields: Row) -> Row:
        data = self.db.table("documents").update(_json(fields)).eq("id", document_id).execute().data
        return _first(data, f"document {document_id}")

    def get_document(self, user_id: str, document_id: str) -> Row | None:
        data = (
            self.db.table("documents")
            .select("*")
            .eq("id", document_id)
            .eq("user_id", user_id)
            .execute()
            .data
        )
        return data[0] if data else None

    def list_documents(self, user_id: str) -> list[Row]:
        return (
            self.db.table("documents")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
            .data
        )

    def delete_document(self, user_id: str, document_id: str) -> Row:
        data = (
            self.db.table("documents")
            .delete()
            .eq("id", document_id)
            .eq("user_id", user_id)
            .execute()
            .data
        )
        return _first(data, f"document {document_id}")

    def put_file(self, path: str, data: bytes, content_type: str) -> None:
        self.db.storage.from_(self.bucket).upload(
            path, data, file_options={"content-type": content_type, "upsert": "false"}
        )

    def delete_file(self, path: str) -> None:
        self.db.storage.from_(self.bucket).remove([path])

    # -- opportunities ------------------------------------------------------------------ #
    def list_opportunities(self, filters: OpportunityFilters) -> tuple[list[Row], int]:
        if filters.ids is not None and not filters.ids:
            return [], 0
        query: Any = (
            self.db.table("opportunities")
            .select(OPPORTUNITY_COLUMNS, count="exact")
            .eq("review_status", "approved")
        )
        if filters.q:
            # websearch_to_tsquery as a plain filter: .text_search() returns a
            # builder that can't take the type/id filters chained after it.
            words = filters.q.split()
            text = " or ".join(words) if filters.match_any else filters.q
            query = query.filter("search", "wfts(simple)", text)
        if filters.types:
            query = query.in_("type", filters.types)
        if filters.modes:
            query = query.in_("mode", filters.modes)
        if filters.country:
            query = query.ilike("country", filters.country)
        if filters.trust_levels:
            query = query.in_("trust_level", filters.trust_levels)
        if not filters.include_expired:
            query = query.or_(f"deadline.is.null,deadline.gte.{date.today().isoformat()}")
        if filters.deadline_before:
            query = query.lte("deadline", filters.deadline_before.isoformat())
        if filters.ids is not None:
            query = query.in_("id", filters.ids)
        if filters.exclude_ids:
            query = query.not_.in_("id", filters.exclude_ids)
        if filters.url_like:
            query = query.ilike("url", f"%{filters.url_like}%")
        if filters.created_after:
            query = query.gte("created_at", filters.created_after.isoformat())
        response = (
            query.order("deadline", nullsfirst=False)
            .order("title")
            .range(filters.offset, filters.offset + filters.limit - 1)
            .execute()
        )
        return response.data, response.count or 0

    def get_opportunity(self, opportunity_id: str) -> Row | None:
        data = (
            self.db.table("opportunities")
            .select(OPPORTUNITY_COLUMNS)
            .eq("id", opportunity_id)
            .eq("review_status", "approved")
            .execute()
            .data
        )
        return data[0] if data else None

    def upsert_opportunities(self, rows: list[Row]) -> int:
        if not rows:
            return 0
        data = (
            self.db.table("opportunities")
            .upsert([_json(r) for r in rows], on_conflict="external_id")
            .execute()
            .data
        )
        return len(data)

    # -- applications ---------------------------------------------------------------- #
    def list_applications(self, user_id: str) -> list[Row]:
        return (
            self.db.table("applications")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
            .data
        )

    def upsert_application(self, user_id: str, opportunity_id: str, fields: Row) -> Row:
        if self.get_opportunity(opportunity_id) is None:
            raise NotFoundError(f"opportunity {opportunity_id}")
        row = {"user_id": user_id, "opportunity_id": opportunity_id, **fields}
        data = (
            self.db.table("applications")
            .upsert(_json(row), on_conflict="user_id,opportunity_id")
            .execute()
            .data
        )
        return _first(data, f"application for {opportunity_id}")

    def delete_application(self, user_id: str, opportunity_id: str) -> None:
        data = (
            self.db.table("applications")
            .delete()
            .eq("user_id", user_id)
            .eq("opportunity_id", opportunity_id)
            .execute()
            .data
        )
        _first(data, f"application for {opportunity_id}")

    # -- chat ---------------------------------------------------------------------------- #
    def list_chat(self, user_id: str, limit: int) -> list[Row]:
        rows = (
            self.db.table("chat_messages")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )
        return list(reversed(rows))

    def add_chat(self, row: Row) -> Row:
        return _first(self.db.table("chat_messages").insert(_json(row)).execute().data, "chat")

    def clear_chat(self, user_id: str) -> None:
        self.db.table("chat_messages").delete().eq("user_id", user_id).execute()

    # -- notifications -------------------------------------------------------------- #
    def list_notifications(
        self, user_id: str, kinds: list[str] | None, since: datetime, limit: int
    ) -> list[Row]:
        query: Any = (
            self.db.table("notifications")
            .select("*")
            .eq("user_id", user_id)
            .is_("dismissed_at", "null")
            .gte("created_at", since.isoformat())
        )
        if kinds:
            query = query.in_("kind", kinds)
        return query.order("created_at", desc=True).limit(limit).execute().data

    def count_unread_notifications(self, user_id: str, since: datetime) -> int:
        return (
            self.db.table("notifications")
            .select("id", count="exact", head=True)
            .eq("user_id", user_id)
            .is_("read_at", "null")
            .is_("dismissed_at", "null")
            .gte("created_at", since.isoformat())
            .execute()
            .count
            or 0
        )

    def add_notification(self, row: Row) -> Row | None:
        try:
            data = self.db.table("notifications").insert(_json(row)).execute().data
        except APIError as exc:
            if exc.code == "23505":  # dedupe_key already used for this user
                return None
            raise
        return data[0] if data else None

    def mark_notifications_read(self, user_id: str, ids: list[str] | None) -> None:
        query: Any = (
            self.db.table("notifications")
            .update({"read_at": datetime.now(timezone.utc).isoformat()})
            .eq("user_id", user_id)
            .is_("read_at", "null")
        )
        if ids is not None:
            if not ids:
                return
            query = query.in_("id", ids)
        query.execute()

    def dismiss_notification(self, user_id: str, notification_id: str) -> None:
        data = (
            self.db.table("notifications")
            .update({"dismissed_at": datetime.now(timezone.utc).isoformat()})
            .eq("user_id", user_id)
            .eq("id", notification_id)
            .execute()
            .data
        )
        _first(data, f"notification {notification_id}")

    # -- per-user opportunity state ------------------------------------------------ #
    def list_opportunity_states(self, user_id: str) -> list[Row]:
        return self.db.table("user_opportunities").select("*").eq("user_id", user_id).execute().data

    def set_opportunity_state(self, user_id: str, opportunity_id: str, fields: Row) -> Row:
        if self.get_opportunity(opportunity_id) is None:
            raise NotFoundError(f"opportunity {opportunity_id}")
        row = {"user_id": user_id, "opportunity_id": opportunity_id, **fields}
        data = (
            self.db.table("user_opportunities")
            .upsert(_json(row), on_conflict="user_id,opportunity_id")
            .execute()
            .data
        )
        return _first(data, f"opportunity state {opportunity_id}")
