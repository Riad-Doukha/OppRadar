# OppRadar AI — Handoff: the Chat phase (notebook 06)

> **Status: DELIVERED & MERGED** — `feature/chat` (`1e272fa`) was reviewed and
> merged into `feature/ai-pipeline` (`c0aac5e`); this document is kept as the
> plan-of-record. See [`README.md`](README.md) §6.1 for the current state.

**For:** the colleague building the conversational Q&A layer.
**Baseline:** branch `feature/ai-pipeline` @ `8c1ed2d` (Phase 7 landed) — 335 tests green on Python 3.13 *and* 3.10, `ruff` clean on both. Start here; for the overall picture, limitations and small fixes see [`README.md`](README.md).
**Notebook numbering:** 00–05 done (setup, documents, profile, discovery, extraction, matching), **06 = chat (yours)**, 07 = security (someone else), 08 = background agent (done).

---

## 1. Mission & scope

Build, in this order:

1. `ai/oppradar_ai/chat.py` — the `answer()` brain (its signature is frozen for Phase 7, see §3);
2. `ai/oppradar_ai/chat_ui.py` — the ipywidgets chat panel (same pattern as `toasts.py`);
3. `ai/notebooks/06_chat.ipynb` — the demo notebook;
4. `ai/tests/test_chat.py` — offline tests.

**Not in scope:** the `api.py` façade (it already exists from Phase 7 and lazily proxies your `answer()` — its signature is frozen, see §3) and the security notebook 07.

Everything is **free-tier only**: Gemini Flash via `google-genai` (structured output), local embeddings, disk cache, no vector DB, no Docker, no web framework.

---

## 2. What already exists (phases 1–5) — your building blocks

| Phase | Module(s) | What you reuse |
|---|---|---|
| 0/1 setup + LLM | `config.py`, `llm.py` | `Settings`/`get_settings()` (lru-cached — call `get_settings.cache_clear()` after changing env), `setup_logging()`, `forced_provider(name)` contextmanager, `prompts_dir`; `get_llm()` → fake/gemini/ollama |
| 2 documents | `documents/*`, `private_profile.py`, `scripts/build_private_profile.py` | PDF/DOCX/image reading (pymupdf, pdfplumber, python-docx, rapidocr → Gemini vision last), `Profile` building; private profile = rules-only unless `--allow-llm` consent |
| 3 ingestion | `ingestion/*` | `run_ingestion(...) -> IngestionReport` (never raises), `extract_record(text, ...) -> RawExtraction` (`.opportunity` / `.rejected_reason` / `.pending`), `clean_html(html) -> CleanedPage(url, canonical, title, text, links)`, `PageFetcher` (robots + politeness delay), `RunBudget` per-run caps, rule-first deadlines |
| 4 matching | `matching/*` | `score_user(...)`, **`check_criteria(profile, opportunity)` → MET/MISSED/UNKNOWN with evidence**, `decide_notifications(...)`, `prefs_from_settings(...)`, `phrasing_allowed(settings)` — *the cost-gate helper to copy* |
| 5 agent | `agent.py`, `dropfolder.py`, `toasts.py` | `BackgroundAgent` (demo cycles never touch the network), `ToastBoard` pattern for widgets |
| storage | `store.py` | `JsonStore`: users / opportunities / matches / notifications + **`append_chat(profile_id, ChatTurn)` and `chat_history(profile_id, limit=20)`** — your persistence already exists. Thread-safe (RLock), atomic writes, one JSON file per collection under `data/store/` |
| schemas | `schemas.py` | All Pydantic models. **The chat schemas are already designed — do not change their fields** (Phase 7 depends on them): |

```python
class Citation(BaseModel):          # one source grounding an answer
    url: str = ""; title: str = ""; quote: str = ""

class EligibilityAssessment(BaseModel):
    eligible: bool | None = None    # None = not enough info
    met: list[str] = []; gaps: list[str] = []; next_steps: list[str] = []

class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]; content: str
    at: datetime = ...              # default_factory now

class ChatAnswer(BaseModel):
    answer: str
    language: str = "en"
    citations: list[Citation] = []
    in_source: bool = True          # False => the info simply isn't in the source
    eligibility: EligibilityAssessment | None = None
    extracted_opportunity: Opportunity | None = None   # message carried a link/text/screenshot
```

**Fixtures** (committed, offline): `ai/data/fixtures/opportunities.json` (32 records, ids `opp-01..opp-32`) and `profiles.json` (5 synthetic users — `u-amine`, `u-sara`, `u-youcef`, `u-lina`, `u-karim`; ar/fr/en, Algeria-centered, NO real personal data). `ai/data/eval/scam_labels.json` holds the scam verdicts.

**Prompts** live in `ai/oppradar_ai/prompts/*.md` (one per LLM task: `extract_cv.md`, `extract_opportunity.md`, `match_reasons.md`, …) and are loaded as the `system` argument: `(settings.prompts_dir / "answer_question.md").read_text(encoding="utf-8")`. Add yours the same way.

**LLM API you will call** (`llm.py`):

```python
llm = get_llm()                                  # provider from settings (.env)
answer = llm.structured(prompt, ChatAnswer, system=system_prompt)  # disk-cached, rate-limited
llm.is_cached(prompt, ChatAnswer, system=system) # free pre-flight check
get_llm("fake")                                  # force the offline provider (tests)
```

`structured()` raises `QuotaExhausted` (never retried — by design) or `LLMError` on failures. `FakeLLM` returns deterministic, schema-valid canned data — **offline tests never touch Gemini**; the pytest conftest forces `LLM_PROVIDER=fake` + `EMBEDDING_PROVIDER=fake` process-wide, and the notebook test harness runs every notebook headless with dummy keys, `RUN_LIVE_LLM=0`, and *fails the suite* if `generativelanguage.googleapis.com` or `api.tavily.com` appears in the output.

---

## 3. The contract you implement

```python
def answer(
    profile: Profile,
    opportunity: Opportunity | None,
    history: list[ChatTurn],
    message: str,
    *,
    settings: Settings | None = None,
) -> ChatAnswer:
```

The four positional arguments are **frozen** (Phase 7 calls them like this). Keyword-only extras are fine.

Standing rules, inherited from earlier phases:

1. **Cost gate.** The model is called only when `settings.run_live_llm and settings.llm_provider != "fake"` — reuse `matching.reasons.phrasing_allowed(settings)` or a copy of it. One chat = one `structured()` call, disk-cached. `LLM_MIN_DELAY_SECONDS` politeness applies.
2. **Privacy (the rule that shaped phase 4).** The model must **never see user documents** (CV / certificates / portfolio) **or raw profile text**. It MAY see: the public opportunity record (and optionally re-fetched public page text, behind the gate), the user's message, and the chat history. For "am I eligible?" questions, compute locally with `check_criteria(profile, opportunity)` and pass only requirement-level verdicts (see §5.4 for the nuance).
3. **Grounding / refusal.** If the source doesn't contain the answer, the reply must contain the exact phrase **"not in the source"** and set `in_source=False`. Never invent deadlines, amounts or eligibility. Citations must quote text actually present in the context you sent.
4. **Quota honesty.** On `QuotaExhausted` / `LLMError`: no retry, no crash — return a rules-only `ChatAnswer` (local criteria met/gaps + deadline from the record) with a one-line note that the model couldn't be reached. Precedent: reason phrasing keeps the rules' reasons on a 429.
5. **History.** Trim to the last N turns before prompting (add a `chat_history_turns: int = 10` knob to `Settings` if you want it configurable). Recommended: keep `answer()` **pure** (no store writes) and let the UI/notebook persist turns with `store.append_chat(...)` — much easier to test.
6. **`extracted_opportunity`.** If the message carries a URL or pasted announcement text, extract it (`clean_html` + `extract_record` for text; behind the gate + `PageFetcher`/robots for URLs) and fill the field, answering from the extracted record. Screenshot/vision path is optional backlog.

---

## 4. How to implement — recommended steps

### 4.1 `oppradar_ai/chat.py`

Keep `answer()` a thin orchestrator over small functions (<40 lines each), like the rest of the codebase:

1. `_evidence(profile, opportunity)` — the local pack: public opportunity fields (title, organizer, deadline, funding, eligibility lines, summary, url) + `check_criteria()` verdicts. No model involved.
2. `_prompt(evidence, history, message)` — render `prompts/answer_question.md` with plain `.format()` (no template engine in the project).
3. One `llm.structured(prompt, ChatAnswer, system=...)` call.
4. `_postprocess(reply, evidence)` — enforce rule 3 (`in_source` + refusal phrase), attach the **locally computed** `eligibility` (the model never has the profile, so never trust it to compute this), fill `language`.
5. `_rules_only_answer(evidence, reason)` — the failure path (rule 4).

### 4.2 FakeLLM canned answer

`llm.py` keeps a `_CANNED` dict keyed by **schema class name** and falls back to generic defaults (`_default_for`) for unknown schemas. A `"ChatAnswer"` entry (deterministic text, `in_source=True`, one `Citation`) **already exists** — keep it in sync with your prompt/schema so offline tests and the offline notebook assert stable values. If you touch `_CANNED`, keep the "listicle" special rule for `OpportunityExtraction` intact (tests depend on it).

### 4.3 `oppradar_ai/chat_ui.py`

Copy the `toasts.py` pattern exactly: **pure render functions** (testable headless, no kernel needed) + a widget class that imports ipywidgets *inside* `__init__`. Suggested `ChatPanel`: scrollable message list (HTML), a text input + Send button, a citations block with links, an eligibility box. It calls `chat.answer()` and `store.append_chat(...)` only — **no business logic in the widget**. Wrap every callback in try/except (lesson from the agent phase: a dead widget must never take anything down).

### 4.4 `ai/notebooks/06_chat.ipynb`

- Bootstrap: copy the cost-gate header cell from notebook 05/08 verbatim (`RUN_LIVE_LLM`/`LLM_PROVIDER` resolution + `get_settings.cache_clear()` + `setup_logging`).
- Independent demo: build its own throwaway store like notebook 08 does — `JsonStore(root=settings.data_dir / 'store_chat_demo')`, `.reset()`, seed with the fixtures. Notebooks never depend on each other's outputs (only auto-filled shared dirs).
- Suggested steps: offline Q&A (fake provider) → **grounded refusal demo** (ask something the record doesn't contain → "not in the source") → eligibility demo (fixture profile × fixture opportunity via `check_criteria`) → history persistence round-trip → URL/pasted-text demo (offline-safe: local HTML string; the live fetch is gated) → live cell behind `RUN_LIVE_LLM=1` → `ChatPanel` widget.
- Must run top-to-bottom offline with `LLM_PROVIDER=fake`, zero network (the pytest harness executes it headless). No `%autoreload` — restart + Run All semantics.
- Register its offline markers in `tests/test_notebooks.py` → `OFFLINE_MARKERS` (e.g. the refusal phrase and `provider: fake` lines you print).

### 4.5 `ai/tests/test_chat.py`

All offline (fake provider/embedder), all deterministic:

- schema validation of every `answer()` branch;
- refusal question → `"not in the source"` in the text + `in_source=False`;
- **privacy spy**: wrap/monkeypatch `llm.structured` and assert the prompt contains **no** CV text and no raw profile fields (summary, education entries…) — only public opportunity data + requirement-level verdicts;
- quota fallback: a fake provider raising `QuotaExhausted` → rules-only answer, no exception;
- history trimming (30 turns in → only the last N reach the prompt);
- cache (same question twice → `stats.cached` increments / `llm.is_cached` is true);
- URL/pasted-text path → `extracted_opportunity` filled (fetch monkeypatched, no network);
- store round-trip (`append_chat` + `chat_history`);
- language: `ChatAnswer.language` honored by your canned fake.

### 4.6 Conventions & workflow (enforced by ruff + review)

- Full type hints; Pydantic at module boundaries; functions < 40 lines; docstring with a doctest-style example; 2–3 line purpose comment at the top of every file; `logging` not prints; no dead code; ruff line-length 100.
- Run on **both** interpreters before every commit: `python -m pytest` (~3 min, executes the notebooks too) and `E:\anaconda\envs\DM_ENV_310\python.exe -m pytest`; `python -m ruff check .`.
- Strip notebook outputs before commit: `python -m nbstripout (Get-ChildItem ai\notebooks\*.ipynb).FullName`.
- Git: branch **`feature/chat` off `feature/ai-pipeline`**; **never commit to or push `develop`**; merge only after the user verifies. PowerShell quirks: `;` not `&&`, no heredocs, `git commit -F <file>`, write multi-line scripts to temp files; `PYTHONUTF8=1`.
- After each slice, report in one short message: **(a)** what was built **(b)** exact test commands **(c)** expected output **(d)** limitations — then **STOP** and wait. Do not call real Gemini in tests, ever.

---

## 5. Limitations & known problems — improve these if you can

1. **The primary embedding model is broken in this environment.** `BAAI/bge-m3` fails on *both* project envs (torch < 2.6 CVE restriction on `.bin` weights; a Pooling-signature error on 3.13) and silently falls back to `paraphrase-multilingual-MiniLM-L12-v2` (dim 384, cached, works). Options: set `EMBEDDING_MODEL` to the fallback in `ai/.env` to skip the doomed attempt, or evaluate a safetensors-only multilingual model (e.g. `intfloat/multilingual-e5-*`) as the new primary. Chat only feels this via matching-derived eligibility, but every notebook pays the failed-attempt latency.
2. **Free-tier Gemini = 5 calls/minute**, shared by ingestion, phrasing and now chat. Chat is user-triggered (1 call/question), disk-cached, never retried on quota — but a 429 mid-conversation must degrade per rule 4. A "thinking" pause indicator in the UI helps the UX.
3. **Noisy 429 logging.** `ingestion/extract.py` logs the *entire* Gemini error dict at INFO inside `pending LLM ... quota exhausted:` lines (hundreds of chars — this is what made notebook 08 look "broken" to the user). Trim to ~120 chars + the retry-after hint. Small, safe, high value; add a test if you do it.
4. **The real design question — profile privacy vs answer quality.** `check_criteria()` evidence lines can quote profile content (e.g. a university name), and phase 4 already sends rule-reason lines (skills/languages) to the model. Options: **(a)** send only requirement-level met/gaps, no evidence quotes (recommended for v1); **(b)** abstract fields (skills/languages yes, education org names no); **(c)** a per-field consent flag on `Profile`. Whatever you pick, write it down in the prompt file and enforce it with the privacy-spy test.
5. **No "read/marked-as-seen" state.** Chatting about an opportunity does not suppress its notifications; `Notification` has no `read_at`. If you believe it belongs, that changes phase-4 tested behavior (`decide_notifications` dedupe) — coordinate before touching it.
6. **PENDING notifications have no delivery path yet.** Quiet-hours/cap-deferred rows wait for a future digest mechanism. The chat panel could cheaply surface them ("2 queued for tomorrow") — nice demo, honest about the current state.
7. **The store is JSON files.** Single-process safe (RLock + atomic writes), **not** multi-process safe; fine for the notebook product. The interface was designed so a real DB can replace `store.py` alone.
8. **`Opportunity.is_expired` uses `date.today()`** while the scoring pipeline accepts a pinned `today` for tests. Minor inconsistency if you re-test expiry inside chat.
9. **FakeLLM canned data is keyed by schema class name.** Rename `ChatAnswer` → your canned answer silently degrades to generic defaults (`_default_for`), which can hide a missing fixture. Keep the `_CANNED["ChatAnswer"]` entry in sync.
10. **Screenshot/vision in a chat loop is untested.** OCR (rapidocr) → Gemini vision-last exists for documents; message-attached images are backlog unless you want them.
11. **Multilingual UX is unproven.** Fixture profiles speak ar/fr/en; all prompts are English; `ChatAnswer.language` exists. If you add language handling, do it via the prompt + that field, and test with the canned fake.
12. **Page re-fetch duplication.** Chat re-fetching an announcement repeats work ingestion already did; the LLM answer is cached but the HTML fetch is not. Consider caching cleaned page text in `data/cache/` (gitignored) keyed by URL.
13. **Digest/phrasing caps interact with chat volume.** `MAX_PHRASES_PER_RUN` caps rephrasing per scoring run; chat has no cap beyond 1 call/question — consider a per-session guard if you add auto-answers (e.g. answering *about* a list of matches).

---

## 6. Definition of done — verification checklist

```
cd ai
python -m ruff check .
python -m pytest tests\test_chat.py -q
python -m pytest                                   # full suite, incl. every notebook headless
E:\anaconda\envs\DM_ENV_310\python.exe -m pytest   # same on 3.10
python -m nbstripout (Get-ChildItem ai\notebooks\*.ipynb).FullName
```

- [ ] `answer()` matches §3 exactly (Phase 7 will call it).
- [ ] Notebook 06 runs top-to-bottom **offline** (fake provider) *and* with the real `ai/.env` (`LLM_PROVIDER=gemini`, `RUN_LIVE_LLM=1`).
- [ ] Offline markers registered; no `api.tavily.com` / `generativelanguage.googleapis.com` in offline output.
- [ ] Refusal phrase + privacy-spy tests green.
- [ ] Pushed to `feature/chat` (never `develop`); report (a)–(d) sent; STOP for review.
