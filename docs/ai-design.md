# AI design — extraction, matching, and evaluation

## Extraction (ingestion)

Raw web content is messy; the database is not. The pipeline is deliberately
LLM-light and deterministic where it can be:

1. **Fetch** (`fetchers.py`) — per-source adapters (RSS, JSON API, HTML list
   pages) pull raw records: title, snippet, url, and whatever structured fields
   the source exposes. HTTP with a real User-Agent, timeouts, and per-source
   rate limits. One failing source never kills the run.
2. **Extract** (`extractor.py`) — for each raw record, an LLM call converts the
   blob into the shared `Opportunity` Pydantic schema (strict JSON mode, so
   invalid output is retried once then skipped). Sources that already return
   near-structured data skip the LLM via a fast path.
3. **Dedupe** (`dedupe.py`) — canonical URL normalization first (strip tracking
   params, lowercase host), then fuzzy matching on
   `(normalized title, organization)`. Two records scoring ≥ 92 on token-set
   ratio merge; the freshest deadline and richest description win.
4. **Scam check** (`scam_check.py`) — cheap deterministic rules produce a 0–1
   risk score: asks for money/upfront payment, urgency language ("last chance",
   "send your passport now"), free-mail contact for a supposedly big org, no
   legitimate domain, salary too good to be true, all-caps / heavy emoji. Above
   threshold → `scam`, middle band → `suspicious`. An optional LLM second
   opinion runs only on the middle band.

Cost control: one LLM call per *new* record (deduped before paying), tiny
prompts, JSON mode, and a single shared client (`llm.py`) with retries.

## Matching

Two stages — never let semantics override hard constraints:

1. **Hard filters** (`filters.py`) — deadline in the future, user's mode
   preference (remote/hybrid/onsite), location/country preference, and
   opportunity-type preferences. Anything failing one of these is dropped.
2. **Soft score** (`scorer.py`) — for survivors:

   ```
   score = 0.45 · cosine(profile_embedding, opportunity_embedding)
         + 0.40 · skill_overlap          # matched requested skills / requested skills
         + 0.15 · type_preference_bonus  # user's preferred kinds of opportunity
   ```

   Embeddings come from `embeddings.py` (remote API by default, local
   sentence-transformers optional). Skill overlap is set-based on normalized
   skill names (lowercased, leet/alias table applied) so "JS" == "javascript".
3. **Reasons** (`reasons.py`) — every `MatchResult` ships 2–4 plain-language
   reasons ("Matches 4 of your skills: python, fastapi…", "Closes in 12 days",
   "Remote, matches your preference") — the frontend shows these instead of a
   bare number.

## Evaluation

The contract-first test suites live in `ai/tests/`. LLM-dependent behaviour is
evaluated on labelled sets in `ai/data/eval/`:

- **Extraction** — `extraction_test_set.jsonl`: raw source records with the
  gold `Opportunity`. Metric: exact-match on (title, organization, deadline)
  plus field-level F1.
- **Scam check** — labelled safe/scam samples. Metric: precision/recall on the
  `scam` label (recall weighted higher — false negatives are worse).
- **Matching** — `match_test_set.jsonl`: (profile, opportunity, relevance)
  triples. Metric: Precision@5 and nDCG@5 per profile.

### Results

| Eval set     | Metric            | Baseline (rules only) | Latest | Date |
| ------------ | ----------------- | --------------------- | ------ | ---- |
| Extraction   | field F1         | —                     | TBD    | TBD  |
| Scam check   | scam recall      | —                     | TBD    | TBD  |
| Matching     | Precision@5      | —                     | TBD    | TBD  |
| Matching     | nDCG@5           | —                     | TBD    | TBD  |

Run `pytest ai/tests` for the deterministic suite. The labelled evals run
against a real LLM key — see `ai/README.md`. Results get appended to this
table on every meaningful change (notebooks `you_01_extraction.ipynb` /
`ikbel_01_matching.ipynb` document the experiments behind them).
