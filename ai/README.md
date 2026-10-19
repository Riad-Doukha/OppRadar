# OppRadar AI (`oppradar_ai`)

The AI core of OppRadar: opportunity ingestion, CV parsing, matching, and the
chat assistant. Plain Python package — no service to deploy; the backend imports
it directly (`backend/requirements.txt` has `-e ../ai`).

## Run it alone

```bash
cd ai
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp ../.env.example ../.env     # or create ai/.env — fill LLM_API_KEY etc.
pytest                         # deterministic tests, no network needed
```

Optional extras:

```bash
pip install -e ".[embeddings]"  # local sentence-transformers embeddings
pip install -e ".[cv]"          # PDF/DOCX CV parsing (pypdf, python-docx)
```

## Layout

```
oppradar_ai/
├── schemas.py      SHARED — every Pydantic model. Both owners approve changes.
├── llm.py          SHARED — the single LLM/embedding client (keys, retries).
├── ingestion/      fetchers → extractor → dedupe → scam_check   (Ahlem)
├── profile/        CV → Profile                                 (Ahlem)
├── matching/       filters → embeddings → scorer → reasons      (Ikbel)
└── chat/           retrieval → assistant                        (Ikbel)
```

The five functions the backend may call are documented in
[`../docs/ai-interface.md`](../docs/ai-interface.md).

## Notebooks

Experiments live in `notebooks/`, one prefix per person so they never collide:

- `you_*.ipynb` — Ahlem (ingestion / extraction)
- `ikbel_*.ipynb` — Ikbel (matching / chat)

## Data

- `data/fixtures/opportunities.json` — 30 synthetic opportunities used by tests
  and demos. **Never** commit real scraped data here.
- `data/eval/` — labelled eval sets + synthetic profiles.
- `data/private/` — real user data (CVs etc.) — **git-ignored**.

## Conventions

- Anything that talks to the LLM goes through `oppradar_ai.llm` — no direct
  API calls elsewhere.
- New code that can fail on bad input raises a subclass of
  `oppradar_ai.errors.AIRuntimeError`.
- Public functions validate against `schemas.py` before returning.
