# OppRadar 📡

**An AI-powered radar for opportunities.** OppRadar ingests internships, jobs,
scholarships, competitions and bootcamps from across the web, checks them for
scams, matches them to your CV, and lets you chat with an assistant about what
fits you best.

## What it does

1. **Ingestion** — fetches opportunities from configured sources
   (`ai/oppradar_ai/ingestion/sources.yaml`), extracts them into a structured
   schema with an LLM, de-duplicates them, and scores scam risk.
2. **Profile** — parses a CV (PDF/DOCX) into a structured profile.
3. **Matching** — hard filters (deadline, mode, location) + semantic similarity
   (embeddings) + skill overlap → a ranked list with human-readable reasons.
4. **Chat** — a retrieval-augmented assistant that answers questions about the
   opportunities you qualify for.
5. **App** — Next.js frontend + FastAPI backend + Supabase (Postgres, auth).

## Repository layout

| Path                     | Contents                                      | Owner(s) |
| ------------------------ | --------------------------------------------- | -------- |
| `frontend/`              | Next.js + TypeScript app                       | Riad     |
| `backend/`               | FastAPI app (routers, services, sockets)       | Riad     |
| `supabase/migrations/`   | Postgres schema + RLS                          | Riad     |
| `ai/oppradar_ai/schemas.py`, `llm.py` | **Shared** AI code (changes need both AI owners' approval) | Riad, Ahlem, Ikbel |
| `ai/oppradar_ai/ingestion/`, `profile/` | Fetching, extraction, dedupe, scam check, CV parsing | Ahlem |
| `ai/oppradar_ai/matching/`, `chat/`     | Filters, embeddings, scoring, RAG assistant   | Ikbel    |
| `ai/notebooks/`          | Experiments — one prefix per person           | Ahlem, Ikbel |
| `docs/`                  | SRS, architecture, AI interface & design      | All      |

## How to run

### 1. AI package (standalone)

```bash
cd ai
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp ../.env.example ../.env                          # fill in your keys
pytest                                              # run the test suite
```

See [`ai/README.md`](ai/README.md) for running the AI part alone.

### 2. Backend (FastAPI)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scriptsctivate
pip install -r requirements-dev.txt    # installs ../ai in editable mode too
pytest                                 # offline: in-memory repo + fake LLM
uvicorn app.main:app --reload          # http://localhost:8000/docs
```

Without a Supabase project you can still click through the API with
`DATA_BACKEND=memory` (data is lost on restart; auth still needs Supabase JWTs).

### 3. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev                            # http://localhost:3000
```

### 4. Database (Supabase)

```bash
supabase start                         # local stack (needs Docker)
supabase db reset                      # applies supabase/migrations/
cd backend && python scripts/seed.py --demo   # fixtures + read-only demo account
```

No Docker? Create a free project at supabase.com, run
`supabase link --project-ref <ref> && supabase db push`, and put its URL/keys in `.env`.
Auth settings (e-mail confirmation, 8-char passwords with a digit, 30-min reset
links, Google) live in `supabase/config.toml`.

## Configuration

Copy `.env.example` to `.env` and fill in the values — nothing secret lives in
the repo. The AI reads `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` and
`EMBEDDING_MODEL`; the backend reads the Supabase variables.

## Git workflow

All work happens on **`develop`**. `main` is reserved for stable releases.

1. Branch off `develop`: `git checkout -b feature/<topic>` (git cannot create
   `develop/...` branches while a `develop` branch exists)
2. Open a PR **back into `develop`** — CODEOWNERS auto-requests the right reviewer.
3. `schemas.py` and `llm.py` are shared: both AI owners must approve changes there.

## Status

| Area                | Status                                                |
| ------------------- | ----------------------------------------------------- |
| Repo scaffold       | ✅ Done                                               |
| DB schema           | ✅ Profile/onboarding, documents, opportunities, RLS  |
| Ingestion           | 🚧 Scaffolded — fetchers/extractor being built        |
| CV parsing          | 🚧 Scaffolded                                         |
| Matching            | ⬜ Not started (Ikbel)                                |
| Chat assistant      | ⬜ Not started (Ikbel)                                |
| Frontend            | ⬜ Not started (Riad)                                 |
| Backend API         | 🚧 Auth, onboarding, CV upload, opportunities — matching/chat wait on AI |
| Eval harness        | ⬜ Test sets being labelled                           |

## Built by

- **Riad Doukha** — frontend, backend, database
- **Ahlem Toubrinet** — AI ingestion + CV parsing
- **Ikbel** — AI matching + chat assistant
