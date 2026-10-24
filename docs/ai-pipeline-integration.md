# AI Pipeline & Background Agent — Integration Guide for Backend / Frontend

**Audience:** the developer wiring OppRadar's `backend/` and `frontend/` to the AI
layer. It tells you exactly which functions to call, which files hold the agent's
results, which fields to render, and which rules are not negotiable.

**Companion documents**

| Doc | What it covers |
|---|---|
| `docs/ai-interface.md` | The frozen six-function contract (params, errors, gates) — the short reference |
| `ai/README.md` | Status of every phase, known limitations, backlog |
| **this file** | How to *fetch and display* pipeline + agent results end to end |

---

## 0. Big picture

```
 sources.yaml (RSS/search)  +  drop folder (ai/data/live_feed/)  +  user uploads (CV, cert)
            |                          |                                   |
            +---------- run_ingestion / extract_opportunity / parse_documents
                                 |                       (api.py — plain Pydantic in/out)
                                 v
                       score_user  ->  MatchResult (0-100 + reasons)
                                 |
                       decide_notifications (threshold / cap / quiet hours / dedupe)
                                 v
                          Notification (sent | pending | suppressed)
                                 |
        BackgroundAgent loop (APScheduler)  ---- writes everything ---->  JsonStore
                                 |                                  ai/data/store/*.json
                                 v                                          |
                     add_notification_callback(toast)                       v
                                                              backend endpoints -> frontend
```

Two consumption modes — **both are supported and they share the same store**:

1. **On demand (request/response):** call the six `oppradar_ai.api` functions
   inside your request handlers. They are pure: plain Pydantic in, plain
   Pydantic out, **no database writes** (only the disk cache for remote calls).
   If you want results to persist for later/other users, save them yourself with
   `JsonStore` (see §4) — or let the agent own persistence (mode 2).
2. **Autonomous (the agent):** `BackgroundAgent` runs the same pipeline on a
   schedule, persists every result into the store, and fires a callback for each
   SENT notification. Your backend just **reads the store** and serves it.

---

## 1. Setup in the backend process

```python
# Either install the package:      pip install -e ./ai
# Or put ai/ on sys.path before importing oppradar_ai.
from oppradar_ai import api                      # the six functions + ApiError
from oppradar_ai.agent import BackgroundAgent, status_rows
from oppradar_ai.store import JsonStore
from oppradar_ai.config import get_settings
from oppradar_ai.matching import prefs_from_settings
from oppradar_ai.schemas import ChatTurn, NotificationPrefs, Profile
```

- **Configuration** is read from `ai/.env` (and the repo-root `.env`) via
  pydantic-settings — the backend never hardcodes model names or keys.
  Key knobs: `LLM_PROVIDER` (`fake` = free/offline, `gemini` = live),
  `RUN_LIVE_LLM` (the master cost gate), `NOTIFY_THRESHOLD`, `daily_instant_cap`,
  `quiet_hours_start/end` (22–08), `AGENT_INTERVAL_SECONDS` (3600),
  `DEMO_INTERVAL_SECONDS` (10), `EMBEDDING_PROVIDER/MODEL`.
- **Default is safe:** with `LLM_PROVIDER=fake` / `RUN_LIVE_LLM=0` every call
  runs locally (samples, rules, canned model) — perfect for tests and dev.
- **Privacy:** `parse_documents` is rules-only (documents never reach a remote
  model) unless the caller passes `allow_llm=True`, which must be gated by
  explicit user consent in *your* UI. Public opportunity pages/feeds may go to
  the provider when the gate is open. Never log raw CV text.
- **Thread safety:** `JsonStore` uses a re-entrant lock and rewrites each JSON
  file atomically — safe to call from FastAPI/uvicorn worker threads. Always
  read through the store's methods, never by opening the files yourself.
- **Keep the interface frozen:** import only `api`, `agent`, `store`,
  `schemas`, `config`, `matching.prefs_from_settings`. Do not add routes,
  database calls or ORM models inside `ai/`.

---

## 2. The functions you call (pipeline results on demand)

### 2.1 Uploads → profile

```python
profile: Profile = api.parse_documents(
    files,                      # list[str | Path] of uploaded files
    *, user_id: str = "local-user",
    kinds: list[str] | None = None,     # "cv" | "certificate" | "portfolio" (else heuristic)
    allow_llm: bool = False,            # consent-gated model fill; False = local rules only
)
```
- **Returns:** one merged `Profile` (see §5.6). Unreadable files are reported
  in `profile.completeness_suggestions` / they degrade gracefully — one broken
  file never kills the batch.
- **Raises `ApiError`:** `empty` (no files), `arguments` (unknown kind),
  `unreadable` (no file produced text).

### 2.2 Sources → opportunities

```python
report: IngestionReport = api.run_ingestion(sources=None)   # None = data/sources.yaml
```
- **Returns:** new `report.opportunities` (list) + counters + per-source stats
  + free-tier usage (`report.searches` / `report.extractions`, each a
  `CallUsage`). A failing source is `report.failures[]`, never an exception.
- **Persist yourself** (the agent does this for you if it runs the cycle):
  `JsonStore().save_opportunities(report.opportunities)`.

```python
opp: Opportunity = api.extract_opportunity(url=...)   # or text=... or image=...
```
- Exactly one source. `text` may be pasted HTML; `image` is OCR'd locally;
  `url` fetches live and therefore needs the gate.
- **Raises `ApiError`:** `arguments`, `offline` (gate closed), `fetch`,
  `rejected` (not an opportunity), `pending` (no model answer), `unusable`
  (no title/organizer).

### 2.3 Profile × opportunities → matches

```python
matches: list[MatchResult] = api.score_user(profile, opportunities, *, settings=None, today=None)
```
- Hard filters first (expired opportunities and `application_fee`-flagged
  records are **dropped before scoring** — they can never appear in matches or
  notifications), then a 0–100 score with 1–3 reasons, best first.

### 2.4 Matches → delivery decisions

```python
prefs: NotificationPrefs = prefs_from_settings(profile_id)   # reads NOTIFY_THRESHOLD etc.
notes: list[Notification] = api.decide_notifications(matches, prefs, history, *, now=None)
```
- `history` = `store.notification_history(profile_id)` — needed for dedupe and
  the daily cap. Rows below the threshold are *not* notifications at all.
  Persist with `store.add_notifications(notes)`.

### 2.5 Chat

```python
reply: ChatAnswer = api.answer(profile, opportunity, history, message, *, settings=None)
```
- `history` = `store.chat_history(profile_id)` (`list[ChatTurn]`). Persist both
  turns after answering: `store.append_chat(profile_id, ChatTurn(role=..., content=...))`.
- `reply.in_source=False` means the record simply does not say — the frontend
  must show that verbatim instead of guessing.

### 2.6 Error contract → HTTP mapping

`ApiError` always carries a machine-readable `.code`:

| `ApiError.code` | Meaning | Suggested HTTP |
|---|---|---|
| `empty` / `arguments` | bad request (no files, wrong args) | 400 |
| `unreadable` / `unusable` | payload can't be parsed | 422 |
| `offline` | live call refused by the gate | 503 |
| `fetch` | remote download failed | 502 |
| `rejected` / `pending` | extraction outcome (show the message) | 422 |
| `chat-unavailable` | chat module not present | 503 |
| `api_error` | anything unexpected | 500 |

```python
try:
    ...
except api.ApiError as exc:
    return JSONResponse({"error": str(exc), "code": exc.code}, status_code=MAP[exc.code])
```

---

## 3. The background agent (autonomous results)

```python
agent = BackgroundAgent(settings=get_settings(), store=JsonStore(), sources=None)
agent.add_notification_callback(on_sent)      # def on_sent(note: Notification, match: MatchResult | None)
agent.start(mode="agent")                     # or "demo"
```

| Method | Effect (all are safe to call in any state) |
|---|---|
| `start(mode="demo"\|"agent")` | Starts the loop. **Twice = no-op**, never an error |
| `pause()` / `resume()` | Pauses/resumes ticks, schedule kept |
| `stop()` | Stops for good; a later `start()` builds a fresh scheduler |
| `status() -> AgentStatus` | Snapshot of the status table (below) |
| `run_cycle(mode=...)` | Runs one cycle **now** (synchronous) and returns its report |

**Mode matrix**

| | `demo` | `agent` |
|---|---|---|
| Interval | `DEMO_INTERVAL_SECONDS` (10 s) | `AGENT_INTERVAL_SECONDS` (1 h) |
| Network | **never** (no feeds, no model) | only if `RUN_LIVE_LLM=1` + real provider |
| Matching phrasing | rules only | honors the gate |
| Use for | UI/dev loops, tests | production |

**One cycle =** drop folder scan → (maybe) `run_ingestion` → `score_user` per
stored profile → `decide_notifications` → `store.add_notifications` → callback
for each SENT. Every stage is wrapped: a broken source/file/toast lands in the
report's `errors[]` and the loop survives — the process can never be taken down.

### 3.1 `AgentStatus` — what to show on a status page

| Field | Type | Meaning |
|---|---|---|
| `state` | `stopped \| running \| paused` | badge |
| `mode` | `demo \| agent` | current cadence |
| `interval_seconds` | float | tick length |
| `started_at`, `last_run`, `next_run` | datetime\|None | countdown ("next run in …") |
| `items_found` / `matches` / `notifications` | int | **last cycle's** numbers |
| `cycles_run` | int | total |
| `last_error` | str | red banner when non-empty |

Handy: `status_rows(status)` returns ready-made `(label, value)` pairs for a
table (that is what the test platform and notebook 08 render).

### 3.2 `AgentCycleReport` — what to log/expose after `run_cycle()`

`mode`, `started_at`, `finished_at`, `drop` (folder scan: scanned/consumed/
quarantined), `ingestion` (an `IngestionReport`, `None` when skipped),
`ingestion_skipped` (why), `items_found`, `matches` (≥ threshold count),
`notifications_sent` / `notifications_pending` / `notifications_suppressed`,
`errors[]`.

> Lifecycle recipe: create **one** agent at app startup (module-level singleton),
> register the toast callback (push it to your websocket/queue), `start("agent")`,
> and `stop()` on shutdown. Manual cycles from an admin button:
> `report = agent.run_cycle(mode="demo")`.

---

## 4. Fetching results — the store

Everything the agent produces lands in **`ai/data/store/`** (git-ignored):

| File | Written by | Read for |
|---|---|---|
| `users.json` | your upload endpoint (`save_user`) | profile screens, agent input |
| `opportunities.json` | ingestion/drop/extract (`save_opportunities`) | opportunity list/cards |
| `matches.json` | agent or your score call (`save_matches`) | "your matches" + reasons |
| `notifications.json` | agent (`add_notifications`) | notification centre |
| `chat.json` | your chat endpoint (`append_chat`) | chat transcript |

```python
store = JsonStore()                                  # defaults to ai/data/store
profiles      = store.list_users()
opportunities = store.list_opportunities()
matches       = store.get_matches("u-amine")         # saved MatchResults for one profile
notes         = store.notification_history("u-amine", limit=50)
sent_today    = store.sent_count_today("u-amine")    # for "5/day" UI
history       = store.chat_history("u-amine", limit=20)

# Serialize for HTTP — every schema is Pydantic:
return [m.model_dump(mode="json") for m in matches]
```

- **Polling:** while the agent is running, poll the backend every 3–10 s
  (that is what the test platform does); otherwise fetch on page load. Reads are
  cheap (small local JSON under a lock).
- **Resetting demo data:** `store.reset()` wipes all five collections — guard it
  behind an admin/dev endpoint only.
- The agent writes the store **itself**; if you bypass the agent with raw
  `api.*` calls, persist explicitly or the next cycle won't see your data.

---

## 5. Result schemas — what the frontend renders

### 5.1 `MatchResult` (a match card)

| Field | Type | Render |
|---|---|---|
| `score` | float 0–100 | score bar; highlight when ≥ `notify_threshold` |
| `top_reasons` | list[str], 1–3 | "Why you're seeing this" bullets |
| `unmet_requirements` | list[str] | amber "still missing" bullets |
| `reasons_source` | `rules` \| `llm` | optional footnote ("phrased by AI") |
| `criteria[]` | `{text, status, evidence}` | expandable eligibility checklist |
| `semantic_similarity` | float 0–1 | debug/tooltip only |
| `opportunity` | `Opportunity` | the card body (§5.2) |

### 5.2 `Opportunity` (an opportunity card)

`id`, `title`, `organizer`, `type` (`scholarship`/`internship`/…), `mode`
(`remote|hybrid|onsite`), `country`, `language`, `deadline` (date|None),
`deadline_source` (`rule|llm|none` — show "no deadline" when `none`, never
invent one), `funding`, `eligibility[]`, `benefits[]`, `summary`, `url`,
`source`, `trust_level`, `scam_flags[]` (`{flag, detail}` — includes
`application_fee`), `field_confidences[]` / `review_notes[]` ("needs review"
chips).

- **`is_expired` is a property** (`deadline < today`) — serialize it as
  `opp.model_dump(mode="json")` plus `{"is_expired": opp.is_expired}` if you
  need it in JSON; expired records are already excluded from matches.
- Hard filters drop expired and application-fee records *before* scoring, so a
  match is by construction clean; still show `scam_flags`/`trust_level` on the
  raw opportunity list.

### 5.3 `Notification` (the notification centre)

| Field | Type | Render |
|---|---|---|
| `status` | `sent` \| `pending` \| `suppressed` | badge: green / amber / grey |
| `suppressed_reason` | str\|None | the "why not" tooltip — e.g. *"already notified for this opportunity"* |
| `title`, `url` | str | link to the source |
| `score`, `reason` | float, str | "72 — Funding is offered" |
| `deadline` | date\|None | countdown |
| `created_at` | datetime | relative time |
| `mode` | `instant` \| `digest` | pending rows explain the next digest |

Semantics to surface: **pending** = held by quiet hours (22–08) or the daily cap
(5/day); **suppressed** = dedupe (never notified twice) — the row exists purely
so the user can see *why* nothing arrived.

### 5.4 `IngestionReport` (the "sync" screen)

`items_fetched` / `items_new` / `items_duplicate` / `items_rejected` /
`items_list_pages` counters, `deadline_from_rule|llm|mismatches|null` provenance
stats, `failures[]` (red list), `rejected[]` + `pending_llm[]` (review queue),
and `searches` / `extractions` (`CallUsage`: `made`, `cached`, `skipped`,
`failed_attempts`, `limit`) — display these as your **free-tier budget meter**.

### 5.5 `ChatAnswer`

`answer` (string — render with escaping/`pre-wrap`), `language`,
`citations[]` (`url`, `title`, `quote` — show as "source" chips under the
answer), `in_source` (when `False`, display the answer as *"not in the source"*
rather than a fact), `eligibility` (`{eligible, met[], gaps[], next_steps[]}` —
render as a checklist when present), `extracted_opportunity` (rare: the message
carried a link the model parsed).

### 5.6 `Profile` (the profile screen)

`full_name`, `headline`, `email`, `phone`, `country`, `skills[]`,
`education[]`, `experience[]`, `projects[]`, `certificates[]`, `languages[]`,
`interests[]`, `links[]`, `preferences`, `completeness` (0–1 → progress bar),
`completeness_suggestions[]` ("Add your full_name" — actionable TODOs),
`field_confidences[]` with `needs_review` (verification chips), `source_files[]`
(what they uploaded).

---

## 6. Suggested backend endpoints

Thin wrappers — function/store call, nothing else:

| Endpoint | Call | Response |
|---|---|---|
| `POST /api/profile` (multipart) | `parse_documents(files, user_id=..., allow_llm=consent)` → `store.save_user` | `Profile` JSON |
| `GET  /api/profile/{id}` | `store.get_user(id)` | `Profile` JSON |
| `POST /api/ingest` | `r = api.run_ingestion()` → `store.save_opportunities(r.opportunities)` | `IngestionReport` JSON |
| `POST /api/opportunity/extract` | `api.extract_opportunity(text/url/image)` → `save_opportunities` | `Opportunity` JSON |
| `GET  /api/results/matches?user_id=` | `store.get_matches(user_id)` | `[MatchResult]` |
| `GET  /api/results/notifications?user_id=` | `store.notification_history(...)` + `sent_count_today` | `[Notification]` + `{sent_today, cap}` |
| `POST /api/agent/start\|pause\|resume\|stop` | `agent.<method>(...)` | `AgentStatus` (`status_rows` rows are fine) |
| `GET  /api/agent/status` | `agent.status()` | `AgentStatus` JSON |
| `POST /api/agent/cycle` | `agent.run_cycle(mode=...)` | `AgentCycleReport` JSON |
| `POST /api/chat` | `api.answer(...)` → `append_chat(user + assistant turns)` | `ChatAnswer` JSON |
| `GET  /api/config` | `get_settings()` subset | `{notify_threshold, daily_cap, quiet_hours, mode}` — the UI needs the threshold line |
| `POST /api/agent/callback`/websocket | `agent.add_notification_callback(...)` (register once at startup) | push `Notification` + `MatchResult` on SENT |

Run **one** agent instance per backend process (singleton); the store makes
multiple readers safe.

---

## 7. Frontend checklist

- [ ] Score bar for matches with a visible **threshold marker** (from `/api/config`).
- [ ] "Why" bullets = `top_reasons`; amber list = `unmet_requirements`.
- [ ] Notification badges: green `sent`, amber `pending` (+ quiet-hours/cap
      explanation), grey `suppressed` + `suppressed_reason` tooltip.
- [ ] Expired / application-fee / `trust_level` chips on opportunity cards;
      `deadline_source="none"` renders as "rolling / no deadline", never a made-up date.
- [ ] Chat: citation chips under every answer; `in_source=False` → the
      *"not in the source"* chip; never fabricate filler.
- [ ] Escape all AI-generated text (XSS): `top_reasons`, `answer`, `summary`,
      `suppressed_reason` — treat every string from the pipeline as untrusted.
- [ ] Poll agent status 3–10 s while running (`next_run` drives the countdown);
      refresh matches/notifications after every cycle.
- [ ] Never render raw CV text — only the parsed `Profile` fields.

---

## 8. Hard rules

1. `ai/` stays a pure, framework-free package: **no DB, no routes, no Docker**;
   the interface (`api.py` six functions) is frozen — extend by adding, not by
   changing signatures.
2. Never commit secrets, `data/cache/`, `data/store/` or real personal data —
   `.env` stays local (so does the private `test_platform/` rig).
3. Remote calls are free-tier only and always gated: don't loop `run_ingestion`
   or `answer()` tighter than the cadence above; respect `CallUsage.limit`.
4. User documents go to a model **only** behind `allow_llm=True` (explicit
   consent); public opportunity text may go to the provider when the gate is open.
5. Tests run offline: `LLM_PROVIDER=fake`, `RUN_LIVE_LLM=0` — never make CI
   depend on live keys.
