# OppRadar — Architecture

```
┌──────────────┐   HTTPS/WS   ┌───────────────┐   REST    ┌───────────────┐
│   Frontend   │ ───────────► │    Backend    │ ────────► │    Supabase   │
│  Next.js/TS  │ ◄─────────── │    FastAPI    │ ◄──────── │ Postgres+Auth │
└──────────────┘              └──────┬────────┘           └───────────────┘
                                     │ in-process import (-e ../ai)
                              ┌──────▼────────────────────────────────────┐
                              │              AI (oppradar_ai)             │
                              │                                           │
  sources.yaml ─► fetchers ─► extractor ─► dedupe ─► scam_check ─► store  │
                              │                                           │
  CV (pdf/docx) ─► cv_parser ┴► profile ─► matching (filters, embeddings, │
                                            scorer, reasons)              │
                              │                                           │
                              │ chat (retrieval + assistant) ◄── LLM API  │
                              └───────────────────────────────────────────┘
```

**Ten-line summary.** The Next.js frontend talks only to the FastAPI backend
over REST (and WebSocket for live updates). The backend owns auth checks and
persistence against Supabase (Postgres + Row Level Security); the browser never
touches the service-role key. The AI is a plain Python package (`oppradar_ai`)
imported directly by the backend via an editable install — no separate AI
microservice to deploy. Scheduled jobs run the ingestion pipeline
(fetch → LLM extraction → dedupe → scam check) and write clean `Opportunity`
rows into Postgres. Users upload a CV once; `cv_parser` turns it into a
`Profile` row. `matching` scores every live opportunity against a profile and
stores `MatchResult` rows with explanation strings. `chat` retrieves the top-k
relevant opportunities per query (vector search over embeddings) and grounds a
generated answer in them, citing each opportunity. Everything that needs an LLM
goes through the single shared client in `llm.py`, so keys, retries and
rate-limits live in one place. Secrets come only from `.env` (see
`.env.example`).

## Web app (frontend + backend)

**Backend** (`backend/app`) is layered: `routers/` (HTTP, auth dependencies) →
`services/` (rules, notifications, the AI gateway `services/ai.py`) →
`repositories/` (persistence). Two repositories implement the same protocol:
`SupabaseRepository` (service-role client, one per thread; every user query
filters on `user_id`) and `MemoryRepository` (tests and DB-less runs). Routers
never import `oppradar_ai` directly — only `services/ai.py` does, so each new AI
phase is a one-file change there. Access levels come from the Supabase JWT:
`User` (signed in), `Writer` (not the read-only demo) and `Admin`
(`app_metadata.role = "admin"`, set with `scripts/make_admin.py`).

**Opportunities flow.** The AI pipeline (or `scripts/seed.py` for now) upserts
published rows. Organisations can also submit one (`/me/submissions`): it is
stored hidden (`review_status = 'pending'`) until an admin approves it at
`/admin`; the submitter is notified either way. Admins can re-label the trust
level (e.g. mark a scam), edit or delete. Students only ever see approved rows
(enforced by the repository filters and by RLS).

**Frontend** (`frontend/`, Next.js App Router) renders pages on the server and
fetches data in the browser with React Query through `lib/api/client.ts`, which
attaches the Supabase access token. Types come from the API's OpenAPI schema
(`npm run gen:api`) — nothing is hand-copied. `middleware.ts` refreshes the
session and sends signed-out visitors to `/login?next=…`. Text is translated with
next-intl (`messages/<en|fr|ar>/*.json`, language in a cookie, Arabic
right-to-left with logical CSS properties); colours are theme tokens in
`app/globals.css`, redefined under `.dark`.

**Honest about what isn't built yet.** Screens whose engine waits on an AI phase
(match scores, AI chat, drafting, alert delivery) work with what exists today
and say so, and Premium is a free reservation clearly marked "coming soon" — no
fake data and no payments.
