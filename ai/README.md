# OppRadar AI — README & handoff

The AI layer of OppRadar: document intake, opportunity ingestion, matching,
notifications, background agent and a grounded chat assistant — all free-tier
tools, all offline-testable with `LLM_PROVIDER=fake` (no network, no keys).

**This file is the starting point for continuing the remaining work** — it is
the single consolidated status/handoff document (the chat handoff file has been
retired into §6.1). The backend-facing contract lives in
[`../docs/ai-interface.md`](../docs/ai-interface.md); how the backend/frontend
**fetch results** (agent, store, schemas, endpoints, rendering) in
[`../docs/ai-pipeline-integration.md`](../docs/ai-pipeline-integration.md);
design rationale in [`../docs/ai-design.md`](../docs/ai-design.md).

---

## 1. Status at a glance

| Phase | Scope | State | Commit(s) |
|---|---|---|---|
| 0/1 | setup, config, schemas, LLM client (Gemini/Ollama/fake, cache, retries) | done | `da0dacb` (with 3) |
| 2 | documents: reader/OCR, extractors, profile builder, private profile | done | `da0dacb` |
| 3a–3e | discovery, fetching, extraction, gate/deadlines, Gemini reliability | done | `da0dacb` |
| 4 | matching: hard filters, criteria rules, 0–100 score, reasons, notifications | done | `fc62f80` `c598d07` `230fb2f` |
| 5 | background agent: APScheduler, drop folder, toasts, notebook 08 | done | `14f4881` `e6f0fcf` |
| 6 | chat: `chat.py`, `chat_ui.py`, `06_chat.ipynb`, `test_chat.py` | done — reviewed & merged from `feature/chat` | `1e272fa` + merge `c0aac5e` |
| 7 | `api.py` interface, feed-entry batching, evaluation notebook 09, e2e test | done | `8c1ed2d` |
| — | post-merge review of `feature/chat` + 4 follow-up fixes (below) | done | `3c46082` |
| — | backend/frontend results guide + chat contract refresh | done | `172e713` |
| — | local test rig `test_platform/` (dashboard + 15-check smoke test) | done — **local-only, git-ignored like `.env`** | never committed |
| — | security notebook 07 | unclaimed | — |

- **Notebooks:** 00–06, 08, 09 run top-to-bottom offline and are executed by
  the test suite. **07 = security (unclaimed) is the only notebook left.**
- **Tests:** 387 green on Python 3.13 *and* 3.10; `ruff` clean on both;
  every notebook runs headless offline with dummy keys.
- **Chat was delivered by a teammate** on `feature/chat`, reviewed in depth,
  merged into `feature/ai-pipeline` (`c0aac5e`), then hardened in `3c46082`:
  outputs stripped (nbstripout), notebook-06 marker prints made single-write,
  the fixtures expiry test made stamp-based (date-drift fix), and the refusal
  answer now keeps the question's language (regression test added).
- **Test rig:** `../test_platform/` (git-ignored, stdlib-only browser dashboard)
  drives the whole pipeline end to end — profile → ingestion → background agent
  → matches → notifications → chat — headless verified by
  `python ../test_platform/smoke_test.py` (15 checks, always offline).
- Branch: **`feature/ai-pipeline`** — all AI-layer work lands here (feature
  branches like `feature/chat` are merged only after review).
  **Never commit to or push `develop`** — merge only after the user verifies.

---

## 2. Quick start

```powershell
cd ai
python -m venv .venv; .venv\Scripts\Activate.ps1        # or use the conda env
pip install -e ".[dev]"
Copy-Item .env.example .env                             # LLM_PROVIDER=fake -> offline
python -m pytest                                        # full suite (~4 min, runs notebooks too)
python -m ruff check .
jupyter lab notebooks/00_setup.ipynb
```

Two interpreters must both pass before every commit:

```powershell
python -m pytest                # system Python 3.13   (~4 min)
python -m ruff check .
E:\anaconda\envs\DM_ENV_310\python.exe -m pytest       # Python 3.10 (~4.5 min)
E:\anaconda\envs\DM_ENV_310\python.exe -m ruff check .
```

Run one notebook headless (offline — always set the gate explicitly; the
`ai/.env` on this machine has `RUN_LIVE_LLM=1`, which would spend real calls):

```powershell
$env:LLM_PROVIDER='fake'; $env:RUN_LIVE_LLM='0'; $env:HF_HUB_OFFLINE='1'
python C:\Users\ADM\AppData\Local\Temp\opencode\run_notebook.py 06_chat   # from ai/
python -m nbstripout (Get-ChildItem notebooks\*.ipynb).FullName           # BEFORE commit
```

PowerShell quirks: `;` not `&&`, no heredocs, `git commit -F <file>`, write
multi-line scripts to temp files, `$env:PYTHONUTF8='1'`.

### Regenerate fixtures before a demo

`scripts/make_fixtures.py` stamps deadlines **relative to the day it ran**;
committed fixtures drift. Refresh right before a demo:

```powershell
python scripts/make_fixtures.py    # opportunities/profiles + data/eval/scam_labels.json
python scripts/make_samples.py     # synthetic CVs/certificates/portfolios
```

It prints `WARNING: fixtures were last generated on ...` when stale
(`warn_if_stale()` from code).

---

## 3. Layout

```
oppradar_ai/
  config.py        Settings (pydantic-settings, .env), get_settings(), forced_provider()
  schemas.py       ALL Pydantic models — shared with the backend, changes need approval
  llm.py           Gemini/Ollama/fake providers, disk cache, retries, QuotaExhausted, _CANNED
  api.py           ★ Phase 7: the frozen six-function backend interface (see §5)
  private_profile.py, store.py (JsonStore incl. append_chat/chat_history), agent.py,
  dropfolder.py, toasts.py
  documents/       reader (pymupdf/rapidocr/Gemini-vision-last) -> extractors -> profile, evaluate
  ingestion/       sources.yaml, fetch (robots), rss, search (Tavily), clean,
                   extract (rule-first deadlines, is_opportunity gate), ★ batch (N entries/call),
                   budget, pipeline (run_ingestion, never raises)
  matching/        filters, criteria (MET/MISSED/UNKNOWN), score, reasons, notifications
  prompts/         one .md per LLM task (extract_cv, extract_opportunity, extract_batch, ...)
notebooks/         00-06, 08, 09 done; 07 security (unclaimed)
data/samples/      SYNTHETIC docs + ground_truth/*.json + feed/page fixtures
data/fixtures/     32 opportunities (opp-01..32) + 5 profiles (u-amine, ...)
data/eval/         live_snapshot.json (20 frozen real entries), scam_labels.json,
                   live_labels.template.json (-> live_labels.json, NOT filled yet)
data/cache/        LLM/Tavily/embedding caches (git-ignored)
data/live_feed/    drop folder (git-ignored, incl. consumed/ quarantine/)
scripts/           make_fixtures, make_samples, snapshot_live, build_private_profile
tests/             pytest (always forced offline by conftest.py)
```

---

## 4. Privacy (standing rule — do not weaken)

- **User documents (CV, certificates, portfolio) never reach a remote model
  without explicit consent.** `api.parse_documents()` is rules-only unless
  `allow_llm=True`; `scripts/build_private_profile.py` needs `--allow-llm`;
  everything under `data/private/` is git-ignored and never committed. Samples,
  fixtures and tests use synthetic documents only — never real personal data.
- **Public opportunity pages and feed entries MAY go to Gemini** when the cost
  gate is open — they are public web data.
- **The model never sees the profile/CV** in matching (only local rules) or in
  chat (only public opportunity text + requirement-level verdicts).
- **Cost gate everywhere:** live web/LLM needs `RUN_LIVE_LLM=1` AND
  `llm_provider != "fake"`. Offline runs must make zero network calls (the test
  harness fails the suite if `generativelanguage.googleapis.com` or
  `api.tavily.com` appears in offline notebook output).

---

## 5. Backend interface (done — Phase 7)

`api.py` exposes exactly six frozen functions, plain Pydantic in/out, no DB:

```python
parse_documents(files, *, user_id, kinds, allow_llm)  -> Profile
run_ingestion(sources=None, *, settings)              -> IngestionReport
extract_opportunity(url=|text=|image=, *, ...)        -> Opportunity
score_user(profile, opportunities, *, settings, today)-> list[MatchResult]
decide_notifications(matches, prefs, history, *, now) -> list[Notification]
answer(profile, opportunity, history, message, *, settings) -> ChatAnswer   # <- phase 6
```

- All expected failures are `api.ApiError` with a machine-readable `code`
  (`empty, unreadable, arguments, offline, fetch, rejected, pending, unusable,
  chat-unavailable`). Full contract, error table, batching math and examples:
  **`../docs/ai-interface.md`**.
- **`answer()`** wraps the grounded chat assistant that has landed (Phase 6,
  §6.1). It still degrades gracefully: only if the `oppradar_ai.chat` module
  were missing would calls raise `ApiError(code="chat-unavailable")` (or return
  the "not wired yet" answer) — today that code survives purely as a defensive
  path. Grounding, citation and refusal behaviour: §6.1.
- **Batching (the 20-per-day fix):** RSS entries are extracted
  `extraction_batch_size` (default 5) per Gemini call → 20 budgeted calls
  cover 100 entries/run; short or failed replies become `pending`, never
  fabricated.

---

## 6. Remaining work (in order)

### 6.1 Chat — Phase 6, notebook 06 — DONE (merged from `feature/chat`)

Delivered and reviewed (`1e272fa`, merged `c0aac5e`): `oppradar_ai/chat.py`
(pure, grounded `answer()` — local evidence → `prompts/answer_question.md` →
one structured call behind the cost gate → contract enforcement), `chat_ui.py`
(`ChatPanel` + HTML-escaped renderers, ipywidgets imported inside `__init__`),
`notebooks/06_chat.ipynb` (own throwaway store, 12 offline markers) and
`tests/test_chat.py` (50 tests: refusal phrase, privacy spy, quota fallback,
history trimming, cache, extraction round-trip, XSS escaping). The refusal
contract, no-profile-text rule, gate and purity requirements all hold;
`api.answer()` now proxies the real module (`chat-unavailable` survives only
as a defensive error for a missing module / signature drift).

Review follow-ups applied on merge: notebook outputs stripped (nbstripout),
marker prints hardened to single-write f-strings, and the fixtures test made
stamp-based (a `days=2` deadline had drifted past today).

### 6.2 Security notebook 07 (unclaimed)

Threat-model demo notebook (prompt injection from a hostile page, secret
handling, what the model is/isn't allowed to see). No module work assumed —
a notebook + tests proving the gates hold.

### 6.3 Scam detector (schema exists, detector missing)

`Opportunity.scam_flags` / `trust_level` and the matching filter that drops
them all exist — **nothing sets them automatically.** Build the rule detector
from `docs/ai-design.md` §4 (money requested, urgency, free-mail organizer,
domain mismatch, …) → writes `ScamFlagDetail` rows + `TrustLevel`, and add a
scam section to `notebooks/09_evaluation.ipynb` scoring against
`data/eval/scam_labels.json` (30 safe / 2 scam, hand-labelled).

### 6.4 Evaluation labels (to make notebook 09 honest)

- Fill `data/eval/live_labels.json` from the shipped template (20 entries,
  ~10 min of hand-labelling) → add gate precision/recall for
  `is_opportunity` to notebook 09.
- Add relevance labels (which fixtures fit which profile) → implement the
  `Precision@5` / `nDCG@5` table from `docs/ai-design.md` (currently TBD;
  the threshold sweep is the stand-in).

### 6.5 PENDING notification delivery (digest)

`decide_notifications` defers over-cap/quiet-hours rows to `pending`, but
**nothing ever delivers them**. Build the digest step (read `pending` rows →
send in one batch → mark `sent`), or surface them in the chat panel
("2 queued for tomorrow"). Coordinate: this touches Phase-4 tested behavior.

### 6.6 Backlog (lower priority)

- 4 harder sample documents + ground truth; real French CV extraction fixes.
- Screenshot/vision path in chat (message-attached images) — untested backlog.
- Multilingual chat UX (`ChatAnswer.language` exists; prompts are English).
- Page-text cache keyed by URL (chat re-fetches what ingestion already fetched).

---

## 7. Limitations (consolidated — known, deliberate, or fixable)

### A. Environment & free tier

1. **`BAAI/bge-m3` is broken in both project envs** (torch < 2.6 CVE block /
   Pooling-signature error) and silently falls back to
   `paraphrase-multilingual-MiniLM-L12-v2` (dim 384, cached, works) — every
   notebook pays the failed-attempt latency. *Fix in §8.2.*
2. **Gemini free tier = 5 calls/min**, shared by ingestion, phrasing, chat.
   All call sites respect the budget/cache; a 429 degrades to `pending` or
   rules-only output instead of retrying.
3. **`extraction_batch_size` is capped in practice by
   `gemini_max_output_tokens` (2048)** — a batch reply must fit. 5 is safe;
   raising it risks truncated replies (→ items go `pending`, never garbage,
   but wasteful).
4. **Noisy 429 logging** in `ingestion/extract.py` dumps the whole Gemini
   error dict at INFO (made notebook 08 look "broken" once). *Fix §8.1.*

### B. Correctness & consistency

5. **`Opportunity.is_expired` uses `date.today()`** while scoring accepts a
   pinned `today` — inconsistent if you re-test expiry in chat/eval.
6. **`api.parse_documents` has no `settings=`** keyword (unlike the other
   five) — nothing in that path reads settings today; add it if that changes.
7. **FakeLLM canned data is keyed by schema class name** — rename a schema and
   its canned entry silently degrades to generic defaults. The batch canned
   rule is additionally coupled to the `=== ITEM n ===` markers in
   `prompts/extract_batch.md`, and the chat canned rule to `chat._prompt()`'s
   section labels (`Opportunity record:`, `Question:`, `Reply language hint:`)
   — rename either set and the offline answers degrade silently.
8. **JSON store is single-process only** (RLock + atomic writes, fine for the
   notebook product; a real DB would replace `store.py` alone).
9. **Page re-fetch duplication**: LLM answers are cached, HTML fetches are not.

### C. Missing product behavior

10. **Language detection is a cheap ar/fr/en heuristic** (`chat.detect_language`)
    — every other language falls back to the `en` hint. The hint only steers
    the offline fake and short real-model prompts; a real model mostly decides
    for itself.
11. **No scam detector** → scam rows only drop when flags are set manually (§6.3).
12. **PENDING notifications have no delivery path** (§6.5).
13. **No read/marked-as-seen state** — chatting about an opportunity does not
    suppress its notifications; `Notification` has no `read_at`. Changing this
    touches Phase-4 dedupe tests — coordinate first.
14. **Digest/phrasing interaction**: `MAX_PHRASES_PER_RUN` caps rephrasing;
    chat has no cap beyond 1 call/question — add a per-session guard if you
    ever auto-answer over lists.

### D. Evaluation gaps

15. **Offline notebook numbers grade the fake harness**, not the real
    extractor — notebook 09 prints this loudly; real accuracy only with
    `RUN_LIVE_LLM=1` (one live run of section A scored **0.97 across 29
    fields**).
16. **`live_labels.json` unfilled** → the `is_opportunity` gate has no
    precision/recall number (§6.4).
17. **No relevance labels** → no `Precision@5`/`nDCG@5` yet (§6.4).
18. **Thin document corpus**: 1 scanned CV (OCR recall = 1 data point), no
    hard French scans (§6.6).

---

## 8. Small fixes wanted (concrete, ordered by value/effort)

1. **Trim the 429 log line** — `ingestion/extract.py` quota message: cut the
   error dump to ~120 chars + the retry-after hint. Add a test.
2. **Fix the embedding attempt** — set `EMBEDDING_MODEL` to
   `paraphrase-multilingual-MiniLM-L12-v2` in `ai/.env` (skip the doomed
   bge-m3 load), or evaluate a safetensors-only multilingual model
   (`intfloat/multilingual-e5-*`) as the new primary.
3. **`is_expired(..., today=)`** — thread the pinned date through, like
   scoring does.
4. **Guard `extraction_batch_size`** — validate it against
   `gemini_max_output_tokens` in `config.py` (field validator warning), so
   nobody bumps it to 20 and silently truncates.
5. **Page-text cache** — store cleaned `page.text` in `data/cache/` keyed by
   URL so chat/detail-fetch stops re-paying fetches.
6. **`settings=` on `parse_documents`** — only if document settings ever
   matter; otherwise leave and keep the doc as-is.
7. Scam detector, labels, digest delivery — see §6.3–6.5 (the bigger items).

---

## 9. Conventions & workflow (enforced by ruff + review)

- Full type hints; Pydantic at module boundaries; **functions < 40 lines**;
  docstring with a doctest-style example; 2–3 line purpose comment at the top
  of every file; `logging` never prints; **no dead code**; ruff `line-length 100`.
- Prompts live in `oppradar_ai/prompts/*.md`, never inline in Python.
- Tests: pytest, offline (conftest forces fake provider + fake embedder),
  schema validation of public outputs, never call real Gemini.
- Notebooks: independent demos (no cross-notebook dependencies), restart +
  Run All semantics (no `%autoreload`), headless-offline markers registered in
  `tests/test_notebooks.py`, **strip outputs before commit**.
- **Git:** all AI work lands on **`feature/ai-pipeline`** (feature branches
  like `feature/chat` are merged only after review); **never push `develop`**;
  merge only after the user verifies. `test_platform/` is git-ignored —
  local-only; never commit or push it.
- **Phase rhythm:** work in slices; after each slice report in ONE short
  message — **(a)** what was built **(b)** exact test commands **(c)** expected
  output **(d)** limitations — then **STOP** and wait for "continue".

### Definition of done (any remaining task)

```powershell
cd ai
python -m ruff check .
python -m pytest                                    # incl. every notebook headless, offline
E:\anaconda\envs\DM_ENV_310\python.exe -m pytest
E:\anaconda\envs\DM_ENV_310\python.exe -m ruff check .
python -m nbstripout (Get-ChildItem notebooks\*.ipynb).FullName
git push origin feature/ai-pipeline                   # NEVER develop
```

- [ ] Offline: suite green on 3.13 and 3.10; no network strings in offline output.
- [ ] New notebook runs top-to-bottom offline *and* with the real `ai/.env`.
- [ ] `docs/ai-interface.md` still matches reality if you touched a signature.
- [ ] Limitations you added/removed are reflected in §7 of this file.
- [ ] Report (a)–(d) sent; STOP for review.
