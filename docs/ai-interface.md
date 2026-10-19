# AI ↔ Backend interface

The backend imports the `oppradar_ai` package directly (editable install via
`backend/requirements.txt`). Five functions are the entire contract — everything
else inside the AI package is free to change as long as these signatures and
schemas hold.

All schemas referenced here live in `ai/oppradar_ai/schemas.py` (shared —
changes need approval from both AI owners).

---

## 1. Ingest everything

```python
from oppradar_ai.ingestion import run_pipeline

opportunities: list[Opportunity] = run_pipeline(sources: list[str] | None = None) -> list[Opportunity]
```

Runs the full ingestion pipeline for the enabled sources in
`ingestion/sources.yaml`: fetch → LLM extraction → de-duplication → scam check.
Returns validated, de-duplicated `Opportunity` objects, each carrying a
`ScamVerdict`. Failures on a single source are logged and skipped — the call
never raises for one bad source. The backend persists the returned rows.

## 2. Parse a CV

```python
from oppradar_ai.profile import parse_cv

profile: Profile = parse_cv(path: str | Path) -> Profile
```

Accepts a PDF, DOCX or TXT file path and returns a structured `Profile`
(skills, education, experience, languages, preferences). Raises
`CVParseError` if the file cannot be read or contains no extractable text.

## 3. Match a profile to opportunities

```python
from oppradar_ai.matching import score_matches

matches: list[MatchResult] = score_matches(
    profile: Profile,
    opportunities: list[Opportunity],
    *,
    top_k: int = 20,
) -> list[MatchResult]
```

Applies hard filters (deadline, mode, location, opportunity type), then a soft
score (embedding similarity + skill overlap + type-preference bonus). Returns
`MatchResult`s sorted best-first, each with `score` (0–1), component
sub-scores, and a non-empty `reasons` list for the UI. Opportunities that fail
hard filters are dropped, not returned with score 0.

## 4. Score an opportunity for scam risk

```python
from oppradar_ai.ingestion import scam_check

verdict: ScamVerdict = scam_check.check(opportunity: Opportunity) -> ScamVerdict
```

Rule-based red-flag detection (money requested, urgency, free-mail contacts,
missing organization site, …) with an optional LLM second opinion. Returns a
`ScamVerdict` with `label` (`safe` | `suspicious` | `scam`), a 0–1 `score`, and
`reasons`. Deterministic and offline (the LLM part is only used when
configured).

## 5. Ask the assistant

```python
from oppradar_ai.chat import ask

answer: ChatResponse = ask(
    question: str,
    history: list[ChatMessage] = [],
    profile: Profile | None = None,
) -> ChatResponse
```

Retrieves the top-k opportunities relevant to the question (biased toward the
profile when given), and generates a grounded answer citing the opportunity
URLs it used. Returns a `ChatResponse` with `answer` text and `sources`
(the retrieved opportunities). Never invents opportunities that are not in the
retrieved set.

---

### Error contract

- Expected failures raise subclasses of `oppradar_ai.errors.AIRuntimeError`
  (`FetchError`, `ExtractionError`, `CVParseError`, `LLMError`).
- Anything else is a bug — the backend may 500 on it.
- All functions are safe to call without `LLM_API_KEY` set, except 1 and 5,
  which then raise `LLMError` immediately instead of hanging.
