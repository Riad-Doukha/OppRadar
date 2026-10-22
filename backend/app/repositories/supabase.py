"""Supabase-backed repository (PostgREST + Storage) using the service-role client.

The service role bypasses RLS, so every user-scoped query filters on user_id
explicitly — never drop those .eq("user_id", ...) calls.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

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
    def __init__(self, client: Client, bucket: str) -> None:
        self.db = client
        self.bucket = bucket

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
        query: Any = (
            self.db.table("opportunities")
            .select(OPPORTUNITY_COLUMNS, count="exact")
            .eq("review_status", "approved")
        )
        if filters.q:
            query = query.text_search(
                "search", filters.q, options={"config": "simple", "type": "websearch"}
            )
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
