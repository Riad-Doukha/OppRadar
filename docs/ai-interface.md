# AI ↔ Backend interface

The backend imports the `oppradar_ai` package directly (editable install via
`backend/requirements.txt`). **Six functions are the entire contract** —
everything else inside the AI package is free to change as long as these
signatures and schemas hold. All referenced schemas live in
`ai/oppradar_ai/schemas.py` (shared — changes need approval from both sides).

```python
from oppradar_ai import api
from oppradar_ai.api import ApiError
```

There is **no database and no web framework** in the AI layer: every function
takes plain Pydantic objects (or plain lists of them) and returns plain Pydantic
objects. Persisting them is the backend's job.

---

## 1. `parse_documents` — the user's files → one `Profile`

```python
profile: Profile = api.parse_documents(
    files: list[str | Path],
    *,
    user_id: str = "local-user",
    kinds: list[str] | None = None,     # "cv" | "certificate" | "portfolio" per file
    allow_llm: bool = False,
) -> Profile
```

Reads PDF / DOCX / TXT / image files (native text layer first, local rapidocr
OCR for scans) and merges every document into one `Profile` with completeness,
conflict and per-field confidence reporting.

- **Default route is rules-only** (regex contact extraction): documents are
  *never* sent to a remote model, whatever `.env` says. This is the privacy
  contract for personal data.
- `allow_llm=True` runs the configured provider over every document — only pass
  it when the backend has collected the user's **explicit consent** (store the
  consent with the profile).
- `kinds` labels the uploads; without it a coarse text heuristic is used
  (`api.detect_kind`).
- One unreadable file is logged and skipped; only if *no* file yields anything
  does the call raise.

Raises `ApiError`: `empty` (no files), `arguments` (unknown kind),
`unreadable` (no file produced text).

## 2. `run_ingestion` — web sources → `IngestionReport`

```python
report: IngestionReport = api.run_ingestion(
    sources: list[Source] | None = None,   # None -> data/sources.yaml
    *,
    settings: Settings | None = None,
) -> IngestionReport
```

One pass: fetch (RSS feeds, pages, Tavily search) → clean → extract → dedupe by
URL. The report carries the validated `Opportunity` rows, per-source stats,
rejected items (`is_opportunity=false`: listicles, news, advice), items pending
a working LLM, deadline provenance (`rule`/`llm`/`null`), remote-call usage and
failures. **Never raises**: a failing source/page/LLM call becomes a failure or
pending entry in the report.

**Batching (the free-tier fix):** RSS feed entries are extracted
`extraction_batch_size` per single Gemini call (default 5). One run's
`max_extractions_per_run` budget of 20 calls therefore covers
**20 × 5 = 100 feed entries** instead of 20; disk-cache hits are free. A failed
or short reply makes only its chunk `pending` — nothing is ever fabricated, and
pending items are retried on the next run.

## 3. `extract_opportunity` — one URL / text / image → `Opportunity`

```python
opportunity: Opportunity = api.extract_opportunity(
    url: str | None = None,
    text: str | None = None,               # plain text OR raw HTML (cleaned first)
    image: str | Path | None = None,       # screenshot/photo, OCR'd locally
    *,
    source_name: str = "manual",
    settings: Settings | None = None,
) -> Opportunity
```

Exactly one source must be given. The same rules as ingestion apply: explicit
`Deadline:` lines beat the model, deadlines are never invented, listicles are
rejected.

- `url=` fetches the page live (robots.txt + rate limit honored) and therefore
  requires the cost gate: `RUN_LIVE_LLM=1` in `ai/.env` **and** a real
  provider. Offline the call fails loudly instead of fetching.
- `image=` uses local OCR; the Gemini vision fallback only activates with a
  configured provider + key.

Raises `ApiError`: `arguments`, `offline` (live fetch refused), `fetch`
(download failed), `rejected` (text is not an opportunity — message carries the
reason), `pending` (no LLM answer: budget/quota/provider), `unusable` (no
usable title/organizer).

## 4. `score_user` — profile × opportunities → ranked matches

```python
matches: list[MatchResult] = api.score_user(
    profile: Profile,
    opportunities: list[Opportunity],
    *,
    settings: Settings | None = None,
    today: date | None = None,             # pin this in tests for reproducibility
) -> list[MatchResult]
```

Hard filters first (expired, scam-flagged, against declared preferences — each
drop carries a human-readable reason; *missing data never filters*), then a
soft score `0–100` = `0.5 × semantic similarity + 0.35 × criteria ratio +
0.15 × bonus`. Results are sorted best-first; each `MatchResult` carries
`score`, `semantic_similarity`, MET/MISSED/UNKNOWN `criteria` with evidence,
1–3 `top_reasons` and `unmet_requirements`. Embeddings are local
(`sentence-transformers`); the model may only reword the rules' reasons, and
never sees the profile.

## 5. `decide_notifications` — matches → delivery decisions

```python
notes: list[Notification] = api.decide_notifications(
    matches: list[MatchResult],
    prefs: NotificationPrefs,              # e.g. matching.prefs_from_settings(profile_id)
    history: list[Notification],           # rows you already delivered/queued
    *,
    now: datetime | None = None,
) -> list[Notification]
```

Pure rules, in order: below `threshold` → not a notification at all; already
SENT/QUEUED for that opportunity → `suppressed`; digest mode → `pending`;
quiet hours (22–08 by default) → `pending`; daily cap (5/day) → `pending`;
otherwise `sent`. Rows keep the match order and include a
`suppressed_reason`, so the UI can always explain itself. Pass the rows you
stored back as `history` — that is how "never twice for the same opportunity"
and the daily cap are enforced across calls.

## 6. `answer` — one chat message → grounded `ChatAnswer`

```python
reply: ChatAnswer = api.answer(
    profile: Profile,
    opportunity: Opportunity | None,
    history: list[ChatTurn],
    message: str,
    *,
    settings: Settings | None = None,
) -> ChatAnswer
```

The chat module is being built on the `feature/chat` branch. Until it lands,
this raises `ApiError(code="chat-unavailable")` — the wrapper never pretends to
answer. Frozen behaviour once available: the model never sees the CV (only
public opportunity text, the message, history and locally computed
eligibility verdicts), and answers it cannot ground say the exact phrase
**"not in the source"** (`in_source=False`).

---

## Error contract

| code | raised by | meaning |
|---|---|---|
| `empty` | `parse_documents` | no documents given |
| `unreadable` | `parse_documents` | no file produced any text |
| `arguments` | `parse_documents`, `extract_opportunity` | bad `kinds`, or ≠ 1 of url/text/image |
| `offline` | `extract_opportunity` | live fetch refused (gate closed) |
| `fetch` | `extract_opportunity` | page download failed |
| `rejected` | `extract_opportunity` | the text is not an opportunity |
| `pending` | `extract_opportunity` | no LLM answer (budget/quota/provider) |
| `unusable` | `extract_opportunity` | extraction had no usable title/organizer |
| `chat-unavailable` | `answer` | chat module not landed / signature drift |

- All expected failures are `oppradar_ai.api.ApiError` with a machine-readable
  `code` (HTTP mapping is the backend's choice, e.g. `rejected` → 422).
- Anything else is a bug — the backend may 500 on it.
- `run_ingestion` and `score_user`/`decide_notifications` never raise for bad
  *data*; empty inputs return empty results.

## Cost, privacy and configuration gates

- Everything is configured through `ai/.env` (pydantic-settings); every
  function accepts an optional `settings=` override — the backend may build its
  own `Settings(...)`.
- **Live web/LLM calls need `RUN_LIVE_LLM=1` plus a real provider**; with
  `LLM_PROVIDER=fake` (the default) every function works offline on canned
  data — that is what the tests and notebooks run on.
- **User documents** go to a remote model only with `allow_llm=True` (explicit
  consent). **Public** opportunity pages/feeds may go to Gemini when the gate
  is open. The model never sees the profile/CV in matching or chat.
- Free tier: 5 Gemini calls/min, `max_extractions_per_run=20`,
  `tavily_max_searches_per_run=5`; disk-cache hits never consume quota; a 429
  flips the run to pending instead of retrying.

## End-to-end example

```python
from oppradar_ai import api
from oppradar_ai.api import ApiError
from oppradar_ai.matching import prefs_from_settings

profile = api.parse_documents(["cv.pdf", "cert.pdf"], user_id="u-riad", allow_llm=True)
report = api.run_ingestion()                       # never raises; read report.failures
matches = api.score_user(profile, report.opportunities)
prefs = prefs_from_settings(profile.user_id)
notes = api.decide_notifications(matches, prefs, history=stored_rows)
# backend persists report.opportunities / matches / notes (plain JSON), then:
try:
    reply = api.answer(profile, report.opportunities[0], stored_turns, "What is the deadline?")
except ApiError as exc:
    ...  # exc.code: "chat-unavailable" until feature/chat lands
```

Evaluation numbers (extraction accuracy, deadline rules, batching call-math,
threshold sweep, notification guarantees) live in
`ai/notebooks/09_evaluation.ipynb`; design rationale in `docs/ai-design.md`.
