# OppRadar — STRIDE threat model

**Date:** 25 October 2026 · **Scope:** branch `feature/web-foundations` (web app, API, Supabase schema, the API's use of the AI package) · **Method:** code review of every trust boundary against the six STRIDE categories, with each finding verified in the code; the fixes are covered by tests in `backend/tests/test_security.py`.

## 1. Summary

The app's foundations are sound:

- Every request is authenticated with a verified Supabase JWT.
- Only Supabase can grant the admin role.
- Row-level security is on for every table, and a test enforces it.
- The service-role key never reaches the browser.

The review found **11 issues**:

- **5 are fixed in this change.** One of them, F1, also needs migration **0009** applied in Supabase.
- **2 are configuration tasks** for deployment.
- **4 low-risk ones are accepted for launch**, each with a follow-up.

| # | Finding | STRIDE | Risk | Status |
|---|---|---|---|---|
| F1 | Users could write their own rows directly through Supabase's REST API, bypassing the API's checks. This included the shared demo account. | T, E | **High** | Fixed: migration `0009` (**apply it**) |
| F2 | Links pasted in chat were fetched by the server without checking where they point (SSRF) | I, E | **Medium** | Fixed (redirects: see F2 follow-up) |
| F3 | The rate-limit client IP could be spoofed with an `X-Forwarded-For` header | D | Medium | Fixed; set `CLIENT_IP_HEADER` when deploying |
| F4 | A 5 MB PDF with thousands of pages was OCR'd page by page on our single API instance | D | Medium | Fixed: 10-page limit |
| F5 | Chat and application history were never deleted, although `/privacy` promises it | I (privacy) | Medium | Fixed: retention purge in the scheduled cycle |
| F6 | The unsubscribe-link secret falls back to other secrets | S | Low | Config: set `EMAIL_SECRET` |
| F7 | No DMARC record for the sending domain | S | Low | Config: DNS at deploy |
| F8 | Ingested opportunities are published automatically, so a page with injected instructions or a scam reaches users labelled rather than blocked | T | Low | Accepted, with a follow-up |
| F9 | Admin edits and deletes leave no audit trail | R | Low | Accepted, with a follow-up |
| F10 | AI errors return internal detail (`str(exc)`) to the client | I | Low | Accepted, with a follow-up |
| F11 | No `script-src` Content Security Policy (defence in depth against XSS) | T, E | Low | Accepted, with a follow-up |

## 2. System and trust boundaries

```
Browser (Next.js on Vercel) ──JWT──▶ API (FastAPI on Render, service-role key) ──▶ Supabase Postgres + Storage
   │  Supabase Auth (anon key)          │ Socket.IO (JWT on connect)              ▲
   └────────────────────────────────────┼─────────────────────────────────────────┘ (anon key + user JWT
                                        ├──▶ Gemini API (extraction, chat, matching reasons)   = direct REST access)
                                        ├──▶ Opportunity sources and pasted links (HTTP fetch)
                                        └──▶ Resend (alert emails)
```

**Assets.** The highest-value assets are:

- Students' profiles: personal data, CVs, and the goals they write down.
- Their consents.
- The integrity of published opportunities, because students act on them.
- The admin role.
- The Gemini and Resend API budgets.
- The service-role key, which bypasses RLS.

**Trust boundaries:**

1. The browser and the API.
2. The browser and Supabase directly. This exists because the anon key is public by design.
3. The API and third-party content: source pages, pasted links and pasted text, all of which reach the LLM.
4. The API and the outside services it calls: Gemini, Resend and Supabase.

## 3. Findings by STRIDE category

### S — Spoofing (pretending to be someone else)

**In place:**

- **API access tokens.** The API verifies the Supabase JWT signature (ES256/RS256 via JWKS, or HS256) and its audience on every request (`backend/app/auth.py`). Tokens are short-lived, refreshed by Supabase Auth.
- **Socket.IO.** Connections must present a valid token, and each one joins only the `user:<id>` room taken from that token (`backend/app/sockets/events.py`).
- **Unsubscribe links.** They are HMAC-SHA256-signed and compared in constant time (`mailer.valid_unsubscribe`).
- **Demo password.** It stays on the server; the browser only ever receives a session.

**F6 — Unsubscribe secret fallback (Low, config).** When `EMAIL_SECRET` is unset, the signing key falls back to the JWT secret, then the service-role key, then the literal `"dev"`.
- *Fix:* set a dedicated random `EMAIL_SECRET` in production. Then a leak of one secret does not compromise the other, and rotating it only invalidates old unsubscribe links.

**F7 — Email spoofing (Low, config).** Alerts are sent from our domain through Resend. Verifying the domain in Resend sets up SPF and DKIM.
- *Fix:* also add a DMARC record (start with `p=none`, then move to `quarantine`), so nobody else can send mail that looks like an OppRadar alert.

### T — Tampering (changing data without permission)

**In place:**

- **Validated writes.** All writes go through the API, which validates them with Pydantic models (lengths, ranges, enums).
- **Read-only demo.** The `Writer` dependency blocks the shared demo account from writing.
- **Reviewed submissions.** Organisation submissions arrive as `pending` and need admin approval.
- **Escaped output.** React escapes all text, including AI output. The only raw HTML is the fixed theme script. AI text in emails is HTML-escaped (tested).

**F1 — Direct REST writes bypassed the API (High, fixed by migration 0009).** Migrations 0001–0006 gave signed-in users `for all` policies on their own rows: profile, skills, documents, chat, applications, consents and storage files.
- **Why it mattered:** the browser never uses these policies, but anyone can combine the public anon key with their own access token and call Supabase's REST API directly. That skips every API check: field limits, consent rules, and the read-only demo.
- **Worst case:** the shared demo session is handed to every visitor, so anyone could deface the demo profile that all visitors see. They could also insert arbitrary `consents` rows into what is meant to be an audit log.
- **Fix:** `supabase/migrations/0009_read_only_client_access.sql` keeps read access to one's own rows and removes all client writes. The API uses the service role, so the app's behaviour does not change.
- **Action: apply 0009 in the SQL editor** (dev now, prod at deploy).

**F8 — Ingested content is auto-published (Low, accepted).** Opportunities found by the scheduled ingestion are stored as `approved` (the column default), so they appear to users without review.
- **Mitigations:**
  - Scam detection sets `trust_level` and `scam_flags`, and the UI labels suspicious listings and "asks for a fee".
  - The LLM only fills a fixed schema, so a page cannot inject actions.
  - The UI always sends users to the official page, and nothing is ever submitted for them.
- *Follow-up:* send `suspicious` or `scam` results to the admin review queue instead of publishing them.

**F11 — No script-src CSP (Low, accepted).** Phase D added `frame-ancestors`, `base-uri`, `form-action`, `object-src`, `nosniff` and HSTS. A `script-src` policy would need nonces for Next.js's inline scripts and our theme script.
- *Follow-up:* a nonce-based CSP via middleware, after launch.

### R — Repudiation (denying an action because there's no record)

**In place:**

- **Consents.** They are kept as an append-only log (no update or delete policy; after 0009, written only by the API).
- **Reviews.** Each review records `reviewed_by` and `reviewed_at`.
- **Ingestion runs.** Each run is stored with `triggered_by`.
- **Emails.** Every email sent is stamped `emailed_at` on its notification.

**F9 — No audit trail for admin edits and deletes (Low, accepted).** Editing or deleting an opportunity in `/admin` changes the row and records nothing about who did it.
- *Follow-up:* an `admin_audit` table (who, what, when, before/after) written by `routers/admin.py`.

### I — Information disclosure (data reaching the wrong people)

**In place:**

- **Per-user scoping.** RLS restricts every user table to its owner, and the API filters by the token's user ID.
- **CV storage.** CVs live in a private bucket under `<user_id>/` (PDF only, 5 MB).
- **Consent-gated AI.** The LLM reads CVs only with the CV-processing consent, and profiles are scored only with the matching consent.
- **Keys.** The service-role key and the demo password exist only on the server. The browser gets only `NEXT_PUBLIC_*` values (`frontend/next.config.mjs`).
- **Account deletion.** Deleting an account removes the auth user, the files and, via cascade, every row.
- **Server errors.** The 500 handler returns a generic message.

**F2 — SSRF through pasted links (Medium, fixed).**
- **What happened:** when a chat message contains an unknown link, the API fetches that page so the AI can read the announcement. Nothing checked the destination, so `http://127.0.0.1:8000/…`, private-network hosts or cloud metadata addresses would have been fetched from inside our network. The page's text would then come back to the user through the extracted fields.
- **Fix:** `backend/app/netguard.py` allows only http(s) on the default ports. It requires every address the host resolves to to be a public one, and checks this before the fetch.
- **Follow-up for the AI package (owner: AI developer):** `PageFetcher` follows redirects, so a public URL that redirects to a private address is not caught. It should re-check each redirect hop (or cap redirects and check the final address), which would also close the DNS-rebinding gap. Until then, the remaining risk is limited: the fetch needs the live AI gate on, uses the AI budget per user, and returns only the schema fields.

**F5 — Retention promised but not enforced (Medium, fixed).** The privacy page says chat history is kept for 90 days and application records follow the user's retention setting, but nothing deleted them.
- **Fix:** `agent.purge()` runs at the end of every scheduled cycle. It deletes chat older than 90 days, and applications untouched for 12 months for users on the "12 months" setting.
- **Note:** this needs `AGENT_SCHEDULER=1` on the one Render instance, which is already part of the deploy plan.

**F10 — AI error detail returned to clients (Low, accepted).** The `AIError` handler returns `str(exc)`, which can include a fetch error or an upstream message.
- *Follow-up:* return a fixed message for each `code` and log the detail on the server.

### D — Denial of service (exhausting the app or its budgets)

**In place:**

- **AI and ingestion limits.** Manual ingestion has a 15-minute cooldown, and each user gets 20 AI chat answers a day.
- **Rate limits.** `/auth/demo`, `/opportunities` and `/chat` have per-IP limits.
- **Uploads.** They are capped at 5 MB with a PDF signature check.
- **Bounded ingestion.** It has limits on extractions and detail-page fetches per run, plus fetch timeouts.
- **Single scheduler.** Only one scheduler runs, guarded by a cycle lock.

**F3 — Spoofable rate-limit IP (Medium, fixed).**
- **What happened:** to read the real client IP behind Render's proxy, Phase D started uvicorn with `--forwarded-allow-ips "*"`. With `*`, uvicorn trusts the **leftmost** `X-Forwarded-For` entry, which the client controls. Anyone could send a new fake IP with each request and never hit a limit.
- **Fix:** `ratelimit.client_ip()` reads the IP from one configured source, `CLIENT_IP_HEADER`. With `x-forwarded-for` it takes the **last** entry, the one the platform's proxy appended. Otherwise it uses a single-value header set by the proxy, or the TCP peer. The uvicorn flag is removed.
- **Action at deploy:** check which header Render provides and set `CLIENT_IP_HEADER` to match. To check, sign in as an admin, go to **Admin → Ingest → Client IP check** and press **Check** from two different networks (e.g. Wi-Fi and mobile data): `used` must differ between them and match each network's real IP.

**F4 — PDF page bomb (Medium, fixed).** Text extraction falls back to OCR at 220 dpi per page, and the upload limit was in bytes only. A small PDF with thousands of blank pages would have tied up the single API instance.
- **Fix:** uploads with more than 10 pages are refused with a 413 (`UPLOAD_MAX_PAGES`).

**Accepted limits:**
- **In-memory counters.** Rate limits, the cooldown and the chat quota are held in memory. That is correct only while the API runs as one instance, which it does on Render. Moving to more than one instance needs a shared store such as Redis.
- **Shared demo quota.** The demo account shares one daily AI quota across all its visitors, so heavy use can use up the demo's answers for the day. Only the demo is affected.

### E — Elevation of privilege (gaining rights you shouldn't have)

**In place:**

- **Admin role.** It is read from the token's `app_metadata.role`. Users cannot edit this field; only the service role can (`scripts/make_admin.py`).
- **Server-side checks.** Admin routes depend on `require_admin`, and the database also checks `private.is_admin()` for opportunities and ingestion runs.
- **Read-only demo.** The API enforces it, and after F1 so does the database.
- **CORS.** It is limited to the configured origin(s).
- **No CSRF exposure.** The API uses bearer tokens, not cookies, so CSRF does not apply to it.
- **No open redirect.** Auth redirects only accept same-origin paths (`safeNext`, prefixed with the origin).

Two findings above also involve elevation:
- **F1:** writing through the REST API to get around the read-only demo.
- **F2:** using the server's network position to reach internal addresses.

## 4. Before launch

1. **Apply migration 0009** in Supabase: dev now, prod at deploy.
2. **Production environment variables:**
   - `EMAIL_SECRET`: random, 32+ bytes.
   - `CLIENT_IP_HEADER`: check which header Render provides first.
   - `CORS_ORIGINS`: the production domain only.
   - `AGENT_SCHEDULER=1` on the single instance.
3. **DNS:** the SPF/DKIM records from Resend, plus DMARC.
4. **Supabase Auth:**
   - Turn on leaked-password protection.
   - Turn on email confirmation and custom SMTP.
   - Keep only the production redirect URLs.
5. **AI developer:** re-check each redirect hop in `PageFetcher` (F2 follow-up).
6. **Legal:** have the terms and privacy drafts reviewed. The retention they describe is now enforced (F5).

## 5. Follow-ups after launch

- F8: route `suspicious` and `scam` ingestion results to the review queue.
- F9: add an admin audit log.
- F10: return generic AI error messages.
- F11: add a nonce-based `script-src` CSP.
- Run a dependency vulnerability scan in CI: `pip-audit` and `npm audit`.
- Re-run this review whenever a new trust boundary appears, for example Telegram alerts or Premium payments.
