# AI ↔ Backend interface

The backend imports the `oppradar_ai` package in-process (editable install via
`backend/requirements.txt`). **Only `backend/app/services/ai.py` imports it** —
routers call that module, so wiring a new AI phase is a one-file change.

Shared data shapes live in `ai/oppradar_ai/schemas.py` (changes need approval
from both AI owners). The web database mirrors them in
`supabase/migrations/0001_initial_schema.sql`.

## Available now (AI Phase 2 — documents)

| Function | Used by | Notes |
| --- | --- | --- |
| `documents.read_document(path) -> DocumentContent` | `POST /documents` (background) | PDF text layer, OCR fallback for scans (~4 s/page). Raises `ValueError` for unsupported types. |
| `documents.extract_cv(text, source_file) -> CVExtraction` | same | One LLM call. `LLMError` when the provider is down/rate-limited. |
| `documents.extract_certificate(...)`, `extract_portfolio(...)` | same (`kind`) | |
| `documents.build_profile(extractions, user_id) -> ProfileBuildResult` | not wired yet | The web profile is edited by the user in the onboarding wizard; the CV only **pre-fills** it (`services.ai.cv_prefill`). |

Both slow calls run in a thread pool from a FastAPI background task, and the
stages are pushed to the browser as `document:progress` Socket.IO events.

## Coming next (backend side is ready to plug in)

| AI deliverable | Backend endpoint waiting for it | Input the backend will pass |
| --- | --- | --- |
| Ingestion + scam check | `POST /admin/ingest`, scheduled agent | Rows go through `services.ai.opportunity_row(Opportunity)` into `public.opportunities` (upsert on `external_id` = `Opportunity.id`). |
| Matching | `POST /me/agent/start` (returns 501 today), `GET /matches` | `services.ai.to_ai_profile(me) -> Profile` + the stored `Opportunity` list. Expects `list[MatchResult]` (score 0–100). |
| Notifications | agent loop, `GET /notifications` | `notification_settings` row: channels, `threshold` (50–100), `frequency` (instant/daily/weekly), quiet hours. |
| Chat | `POST /chat` | question + `ChatTurn` history + `Profile`; expects `ChatAnswer`. |

## Proposal for `schemas.py` (needs Ahlem + Ikbel)

The onboarding design collects more than `Profile` holds. Until the schema
grows, `to_ai_profile()` flattens it:

| Design field | Today's mapping | Proposed schema change |
| --- | --- | --- |
| Opportunity types `datathon`, `competition` | → `HACKATHON`, `OTHER` | add both to `OpportunityType` |
| Skill level (beginner/intermediate/advanced) | dropped (names only) | `skills: list[Skill{name, level}]` or a parallel `skill_levels` map |
| Language level (basic/good/fluent) | `"Arabic (fluent)"` strings | `languages: list[Language{name, level}]` |
| Birth year, nationality, wilaya | not passed | add to `Profile` (age limits, nationality rules, local opportunities) |
| Goal (20–300 chars) | appended to `summary` | `goal: str` |
| Preferred location (algeria/abroad/remote/anywhere) | `algeria` → `countries=["Algeria"]`, `remote` → `modes=["remote"]` | `Preferences.location_scope` |
| Education level / current year / GPA | not passed | `EducationItem.level`, `Profile.current_year`, `Profile.gpa{value, scale}` |
| CV review card shows birth year + current year | not extracted | add `birth_year`, `current_year` to `CVExtraction` |

## Error contract

- `oppradar_ai.llm.LLMError` → the API answers **503** ("AI service unavailable");
  inside document processing the document is marked `failed` with a readable error.
- `ValueError` from the readers → document `failed` ("We could not read this file").
- Anything else is a bug: logged with a traceback, document `failed`.
- Everything runs offline with `LLM_PROVIDER=fake` (the backend test suite does).
