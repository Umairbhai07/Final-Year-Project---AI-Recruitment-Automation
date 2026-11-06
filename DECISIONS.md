# Design decisions

Where the spec was unclear, the simplest sensible option was chosen. Each choice is listed here.

## Product / scope
- **Spec over SRS.** The SRS (`fyp 1.docx`) mentions a React Native mobile app, GPT-4o and push notifications.
  The project spec says *web only* with Groq, so we followed the spec. Candidate pages are responsive and
  work in phone browsers instead of a separate mobile app.
- **AI provider.** The `openai` SDK is pointed at Groq (`llama-3.3-70b-versatile` and `whisper-large-v3`). The base URL, key
  and models are env vars, so switching to OpenAI GPT-4o and Whisper (as in the SRS) needs no code change.

## AI
- **Mock mode turns on automatically when `LLM_API_KEY` is empty** as well as when `AI_MOCK=true`. This way a fresh
  checkout runs end to end with no key. A warning is logged at startup so mock mode is never silent. Mock
  results are labelled `[Mock AI]` in summaries and feedback.
- **The mock goes through the real code path.** The service passes a `mock` function to `chat_json()`, and its output is
  still JSON-parsed, validated, clamped and written to the audit log. Tests therefore exercise the real pipeline.
- **The audit log is written in its own DB session** so a row survives even if the caller's transaction rolls
  back. Every *attempt* is logged, including failed or retried ones. A Postgres trigger (migration `0002`) blocks
  UPDATE and DELETE on `ai_audit_log`. SQLite (tests only) has no trigger.
- **The answer score is recomputed on the server** as `0.5·accuracy + 0.3·relevance + 0.2·clarity`. The model's own
  `score` field is ignored.
- **Empty or very short transcripts** (fewer than 3 words) are scored 0 without calling the LLM, with the feedback
  "No meaningful answer detected."
- **Wrong question count** from the LLM triggers a retry through the same tenacity loop (an `extra_check` hook).
- **Per-call timeout** is `AI_TIMEOUT_SECONDS` (default 30s). The frontend waits up to 90s for the answer
  upload. On AI failure the API returns **502** and saves nothing, so the candidate can press "Retry submit"
  and their recording is kept in the browser.

## Screening & stages
- **Re-screening** is allowed only from `screening_failed` (as the spec says). A successful re-screen clears
  the manual-review flag.
- **Not-qualified applications cannot be re-screened.** A recruiter can still view them and shortlist manually through
  the decision buttons, because the AI never makes the final decision.
- **The stage machine** lives in `services/application.py → set_stage()`. Every stage change goes through it.

## Interview
- **The countdown runs while recording**, not while reading the question. The candidate presses *Start recording*
  when ready and has `seconds_per_question` to answer. At 0 the recording stops and is submitted automatically.
  This avoids submitting empty audio when a candidate is still reading, and keeps re-record fair because the
  timer resets.
- **Re-record once** is enforced in the browser. The server enforces "each question answered once, in order".
- **Closing a job** archives its applications and blocks unfinished interviews (409).

## Security
- **Login lockout:** 10 *failed* logins per IP in 15 minutes returns 429, tracked in the `login_attempts` table
  so it persists across restarts and workers. slowapi additionally limits login (30/min) and register
  (20/min). Behind Render's proxy the client IP is the **last** `X-Forwarded-For` entry, because earlier entries
  can be spoofed.
- **Refresh tokens** are random strings. Only their SHA-256 hash is stored. Each refresh rotates the token, and
  logout revokes it.
- **Tokens are kept in `localStorage`** for simplicity (common in student projects). An httpOnly-cookie design would be
  stronger against XSS and is noted as future work.
- **Ownership violations return 404**, so other users' resources are not revealed. Wrong role returns 403.
- **Files** (resumes, audio) are never public. They are streamed only by authenticated endpoints after an
  ownership check, from local disk or a private Supabase bucket.
- **Emails HTML-escape** all user-provided text.

## Data
- Score columns are floats (rounded to 1 decimal), because interview scores like 27.9 need decimals.
- The recruiter's "company" shown to candidates is the recruiter's full name (the spec has no company field).
- Dashboard "rank" is always the position by composite score, even when the table is sorted by name or date.
