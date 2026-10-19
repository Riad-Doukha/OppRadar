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
