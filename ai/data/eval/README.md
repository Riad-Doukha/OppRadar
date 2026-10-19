# Eval sets

Labelled data for measuring the AI parts. Everything here is **synthetic** —
no real user data belongs in this folder.

## Files

| File | Used by | Contents |
| ---- | ------- | -------- |
| `extraction_test_set.jsonl` | `tests/ingestion/test_extractor.py`, `notebooks/you_01_extraction.ipynb` | One JSON per line: `{id, raw: <fetched record>, expected: <gold Opportunity fields or null>}`. `expected: null` means "not an opportunity — extractor must drop it". |
| `match_test_set.jsonl` | `tests/matching/`, `notebooks/ikbel_01_matching.ipynb` | `{profile_id, opportunity_id, relevance: 0-3, note}` triples. Relevance: 3 = apply, 2 = relevant, 1 = marginal, 0 = irrelevant/never-surface. |
| `profiles/synthetic_profile_1.json` | both | Amine — MSc data science, wants remote ML internships/research. |
| `profiles/synthetic_profile_2.json` | both | Sara — frontend dev, wants hybrid frontend jobs in Algeria. |

The opportunities referenced by `opportunity_id` live in
`../fixtures/opportunities.json` (`opp-01` … `opp-30`).

## Metrics

- **Extraction**: field-level F1 + exact match on (title, organization, deadline).
- **Scam check**: precision/recall on the `scam` label (recall weighted higher).
- **Matching**: Precision@5 and nDCG@5 per profile.

Current results are tracked in [`../../docs/ai-design.md`](../../docs/ai-design.md).
