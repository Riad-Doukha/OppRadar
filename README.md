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
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt    # installs ../ai in editable mode too
pytest                                 # offline: in-memory repo + fake LLM
ruff check app tests scripts && ruff format --check app tests scripts
uvicorn app.main:app --reload          # http://localhost:8000/docs
```

Without a Supabase project you can still click through the API with
`DATA_BACKEND=memory` (data is lost on restart; auth still needs Supabase JWTs).

### 3. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev                            # http://localhost:3000 (needs the API on :8000)
npm run lint && npm run typecheck && npm run build
npm run i18n:check                     # en/fr/ar message files have the same keys
npm run gen:api                        # regenerate lib/api/schema.d.ts from the API
npm run e2e                            # Playwright: public pages, API mocked (what CI runs)
npm run e2e:full                       # + signed-in journey against your Supabase (see below)
```

The UI is in **English, French and Arabic** (right-to-left), with light, dark
and "system" themes. Text lives in `messages/<locale>/<section>.json` — add every
new key in all three files; `npm run i18n:check` (also in CI) catches gaps. The
language is a cookie (`NEXT_LOCALE`), so URLs don't change.

`npm run e2e:full` needs the API on :8000 and the root `.env`: it creates a
throwaway account with the service-role key, walks log in → 5-step setup →
dashboard → save → apply → Applications → Premium → delete account, and always
removes the account. Locally it uses your installed Chrome.

`next.config.mjs` reads the repo-root `.env`, so there is no `frontend/.env`.
After changing backend models, refresh the types:
`python backend/scripts/export_openapi.py frontend/lib/api/openapi.json && npm run gen:api`.

### 4. Database (Supabase)

Apply the migrations **in order** — either with the CLI
(`supabase link --project-ref <ref> && supabase db push`) or by pasting each file
into the dashboard's **SQL Editor** and pressing Run:

| File | Adds |
| --- | --- |
| `0001_initial_schema.sql` | profiles + onboarding, documents bucket, opportunities, RLS, signup trigger |
| `0002_user_opportunities.sql` | Save / Not interested per user |
| `0003_settings.sql` | alert rules, extra consents, retention, agent settings |
| `0004_notifications.sql` | general notifications (deadline, tip, system, …) |
| `0005_applications_chat.sql` | tracked applications, chat history links |
| `0006_premium_reservations.sql` | Premium early-access reservations (no payments) |
| `0007_opportunity_review.sql` | admin review notes, organisation contact, "own submissions" |

Then seed the fixtures and the read-only demo account:
`cd backend && python scripts/seed.py --demo`.

**Admins** review organisation submissions and manage opportunities at `/admin`.
Make someone an admin (they log out and back in afterwards):
`cd backend && python scripts/make_admin.py you@example.com` (`--revoke` to undo).
The role is in `app_metadata`, which users can't change themselves.

Auth settings (e-mail confirmation, 8-char passwords with a digit, 30-min reset
links, Google) are in `supabase/config.toml`; on a hosted project set them under
Authentication in the dashboard. Note: the npm `supabase` CLI 2.109 (Bun build)
crashes with "Illegal instruction" on some CPUs — use the dashboard or
`scoop install supabase` instead.

### 5. Everything in Docker (optional)

```bash
docker compose up --build              # API on :8000, web on :3000
```

Uses the root `.env` (the web image bakes in the `NEXT_PUBLIC_*` values at build
time) and your Supabase project — apply the migrations first. The API image
installs CPU-only PyTorch for the AI package.

## Configuration

Copy `.env.example` to `.env` at the repo root — nothing secret lives in the repo.
Every part reads that one file: the backend (Supabase keys, demo account), the
frontend (`NEXT_PUBLIC_*` only — never put the service-role key there) and the AI
(`LLM_PROVIDER`, `GEMINI_API_KEY`; more options in `ai/.env.example`).

## CI

`.github/workflows/ci.yml` runs on pushes to `main`/`develop` and on every PR,
with no secrets:
- **backend** — ruff (lint + format) and pytest (in-memory repository, fake LLM);
- **frontend** — ESLint, translation check, type-check, production build;
- **e2e** — Playwright on the public pages of a production build (API mocked);
- **docker** — builds both images.

## Troubleshooting (Windows)

- **Python hangs on start-up (API, tests, seed).** If the Windows WMI service is
  stuck, `platform.system()` blocks forever — Supabase, PyMuPDF and onnxruntime
  all call it on import. Fix: `Restart-Service Winmgmt -Force` (admin) or reboot.
- **`next build` / ESLint / tests crash with "out of memory".** Check free memory;
  a long-running `next dev` can grow to several GB — restart it.
- **"Failed to fetch" in the browser.** Is the API running on :8000? Unexpected
  API errors now return a JSON 500 with details in the API log.

## Git workflow

All work happens on **`develop`**. `main` is reserved for stable releases.

1. Branch off `develop`: `git checkout -b feature/<topic>` (git cannot create
   `develop/...` branches while a `develop` branch exists)
2. Open a PR **back into `develop`** — CODEOWNERS auto-requests the right reviewer.
3. `schemas.py` and `llm.py` are shared: both AI owners must approve changes there.

## Status

| Area                | Status                                                |
| ------------------- | ----------------------------------------------------- |
| Repo scaffold       | ✅ Done · CI on push/PR                               |
| DB schema           | ✅ Migrations 0001–0007, RLS on every table           |
| Ingestion           | 🚧 Scaffolded — fetchers/extractor being built        |
| CV parsing          | 🚧 Scaffolded                                         |
| Matching            | ⬜ Not started (Ikbel)                                |
| Chat assistant      | ⬜ Not started (Ikbel)                                |
| Frontend            | ✅ Landing + public Explore, auth, onboarding, dashboard, opportunity pages, Ask the agent (search-based), Apply assistant, Applications, profile, settings, notifications, Premium (coming soon), organisation submissions, admin · EN/FR/AR · light/dark |
| Backend API         | ✅ Auth, onboarding, CV upload, feed, settings, notifications, applications, chat (search fallback), Premium reservations, submissions + admin review — matching, AI chat and drafting wait on the AI phases |
| Tests               | ✅ 88 backend tests · Playwright public suite in CI · full journey locally |
| Eval harness        | ⬜ Test sets being labelled                           |

## Built by

- **Riad Doukha** — frontend, backend, database
- **Ahlem Toubrinet** — AI ingestion + CV parsing
- **Ikbel** — AI matching + chat assistant
