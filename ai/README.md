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

## Privacy

All documents under `data/samples/` are synthetic. Never commit real CVs or
personal data (`data/private/` is git-ignored). The free Gemini tier may use
inputs for improvement — only synthetic data should be sent to it.
