# OppRadar AI

The AI layer of OppRadar: document intake, opportunity ingestion, matching,
notifications and a grounded chat assistant — all free-tier tools, all testable
from Jupyter notebooks with `LLM_PROVIDER=fake` (no network, no keys).

> **Status:** being rebuilt phase by phase per the project spec.
> Currently available (Phase 1): `config.py`, `schemas.py`, `llm.py`
> (Gemini / Ollama / fake + cache + retries), `store.py`, synthetic samples
> with ground truth, fixtures, and `notebooks/00_setup.ipynb`.
> Full install/run documentation lands in the final phase.

## Quick start

```bash
cd ai
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env        # defaults to LLM_PROVIDER=fake — runs offline
pytest                      # test suite (offline, uses the fake provider)
jupyter lab notebooks/00_setup.ipynb
```

The package supports Python **3.10+**. In VS Code / Jupyter, pick an interpreter that
has it installed — e.g. the `DM_ENV_310` conda env (`E:\anaconda\envs\DM_ENV_310\python.exe`),
also registered as the kernel **"DM_ENV_310 (Python 3.10)"**.

## Layout

```
oppradar_ai/          the package (config, schemas, llm, store, then per-feature modules)
notebooks/            numbered labs 00-09, one per feature area
data/samples/         SYNTHETIC CVs/certificates/portfolios + ground-truth JSON
data/fixtures/        synthetic opportunities + profiles for matching tests
data/cache/           LLM/Tavily/embedding caches (git-ignored)
data/live_feed/       drop folder for the live-agent demo
data/eval/            labelled test sets and results
scripts/              generators for the synthetic data above
tests/                pytest (always runs with the fake provider)
```

## Before a demo: regenerate the fixtures

`scripts/make_fixtures.py` stamps every opportunity with a deadline **relative to
the day it ran**, so committed fixtures drift out of date. Refresh them and the
sample documents right before a demo:

```bash
cd ai
python scripts/make_fixtures.py   # writes opportunities/profiles + data/eval/scam_labels.json
python scripts/make_samples.py    # rewrites the synthetic CVs/certificates/portfolios
```

`make_fixtures.py` prints a `WARNING: fixtures were last generated on ...` if the
stamp in `data/fixtures/generated_on.txt` isn't today. You can check this from code
with `warn_if_stale()` (returns `True` when stale). Scam ground truth lives in
`data/eval/scam_labels.json` (`{"opp-31": true, ...}`); only two fixtures are scams
and the two borderline ones (a paid event, a free-mail contact) are labelled legit.

## Privacy

What may be sent to the LLM (Gemini / Ollama / fake):

- **Public opportunity pages and RSS feed entries** (anything fetched from the
  `sources.yaml` public sources) **MAY be sent to the LLM.** They are public
  web data, and extraction is the whole point of the ingestion pipeline.
  Notebooks run real Gemini on the synthetic samples and on the frozen live
  snapshot (`data/eval/live_snapshot.json`) so you can see real extraction
  without pointing the model at arbitrary pages.
- **User documents (CVs, certificates, portfolios) are treated as private.**
  Everything under `data/samples/` is synthetic; `data/private/` is
  git-ignored and must never be committed. Samples, fixtures and tests use
  synthetic documents only — never real personal data. When you extract your
  own CV with real Gemini, its text is sent to the configured provider for
  structuring; set `LLM_PROVIDER=fake` to keep everything on your machine
  (results are then canned, not real extractions).

The free Gemini tier may use inputs for improvement, so decide consciously
what you point it at.
