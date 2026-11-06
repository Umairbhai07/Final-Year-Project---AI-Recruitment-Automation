# How it works (viva guide)

This file explains each part of the project in simple English, in the order it was built.
Every section says **what it does**, **how it works**, and **where the code is**. A few likely viva
questions with short answers are at the end.

---

## The big picture

```
 Browser (React)  ──HTTPS/JSON──▶  FastAPI backend  ──SQL──▶  PostgreSQL (Supabase)
   recruiter + candidate pages       auth, rules, AI          users, jobs, applications,
   mic recording (MediaRecorder)     pipeline                 scores, interviews, audit log
                                        │
                                        ├──▶ Groq LLM (Llama 3.3 70B): resume scoring, questions, answer scoring
                                        ├──▶ Groq Whisper: speech → text
                                        ├──▶ File storage (local disk / Supabase private bucket): PDFs, audio
                                        └──▶ Email (console / Resend)
```

It is a **three-tier architecture**: the presentation tier (React), the application tier (FastAPI) and the data tier
(PostgreSQL + file storage). The browser never talks to the AI directly. All AI keys stay on the server.

**Composite score (out of 100)** = skills (40) + experience (20) + education (10) from the resume, plus
interview (30) from the voice interview.

---

## Module 1: Project setup, config, database, migrations

**What:** The skeleton of the backend. It reads settings, connects to the database and defines the tables.

**How:**
- `app/config.py` uses **pydantic-settings** to read environment variables (from `.env`). Nothing secret is
  written in the code.
- `app/database.py` creates the **SQLAlchemy** engine and a `get_db()` dependency. FastAPI gives each request its
  own DB session and closes it afterwards. The same code works with **SQLite** (quick local run) and **PostgreSQL**
  (Supabase). For Supabase's connection pooler, psycopg's prepared statements are turned off (`prepare_threshold=None`).
- `scripts/check_setup.py` (`python -m scripts.check_setup`) tests the configuration before running: it connects to
  the database, checks the tables exist, calls the AI model, uploads and deletes a test file in the storage bucket,
  checks the email key and warns about a weak JWT secret. It prints plain-language fixes (e.g. "wrong database password").
- `app/models/` holds one Python class per table: `User`, `RefreshToken`, `LoginAttempt`, `Job`, `Application`,
  `Resume`, `EvaluationScore`, `InterviewSession`, `InterviewResponse`, `AIAuditLog`. All use **UUID** primary keys
  and `created_at`/`updated_at` timestamps.
- **Alembic** migrations (`alembic/versions/`) create the tables. Migration `0002` adds a **Postgres trigger**
  that raises an error on any UPDATE or DELETE of `ai_audit_log`, so the AI history can never be changed.
- `GET /health` returns `{"status": "ok"}`, which Render uses to check the server is alive.

**Key constraint:** `UNIQUE(job_id, candidate_id)` on applications means the *database itself* prevents
duplicate applications, even if two requests arrive at the same time.

---

## Module 2: Authentication and roles

**What:** Register, login, refresh, logout and "who am I". There are two roles: recruiter and candidate.

**How:**
- Passwords are hashed with **bcrypt (12 rounds)** in `core/security.py`. We never store or log the real password.
- On login the server returns two tokens:
  - an **access token** (JWT, valid 24h) that the browser sends as `Authorization: Bearer …` on every request;
  - a **refresh token** (random string, valid 7 days). Only its **SHA-256 hash** is stored in `refresh_tokens`.
- `POST /auth/refresh` **rotates** the token: the old one is revoked and a new pair is issued. Logout revokes the
  refresh token.
- `core/deps.py` has `get_current_user` (decodes the JWT) and `require_role(...)`. A candidate calling a
  recruiter endpoint gets **403 Forbidden**.
- **Portal-checked login:** the sign-in page has Candidate / Recruiter tabs and sends the chosen `role`. If the
  password is right but the account has the other role, the server answers **403** with "This is a recruiter account.
  Switch to Recruiter to sign in." This does not count as a failed attempt.
- **Brute-force protection:** every failed login is stored in `login_attempts`. After **10 failures from one IP in
  15 minutes** login returns **429**. slowapi adds a general request rate limit too.
- Validation: email must be valid and unique (stored in lowercase); the password needs at least 8 characters and one number.

---

## Module 3: Jobs

**What:** Recruiters create and manage job posts. Candidates browse active jobs.

**How (`services/job.py`, `routers/jobs.py`):**
- A job has a title, description, required skills (list), minimum experience, education level, deadline,
  **screening threshold (0–70)**, number of interview questions (5–8) and seconds per question.
- **Status machine:** active ⇄ paused, and active/paused → closed. **Closed is final.** Closing a job marks all its
  applications as `archived`.
- Candidates only see **active** jobs whose deadline has not passed. Search works on title or skill.
- A recruiter can only see and edit **their own** jobs. Another recruiter's job returns **404** (we don't even
  admit it exists).

---

## Module 4: Applying and file storage

**What:** A candidate uploads a PDF resume to apply.

**How (`services/application.py`, `services/storage.py`):**
- The file is checked three ways: the **extension** is `.pdf`, the **MIME type** is `application/pdf`, and the first
  bytes are the **`%PDF` magic number** (so a renamed .exe is rejected). Otherwise the server returns **415**.
- The maximum size is **5 MB**, otherwise **413**. The server reads at most 5 MB + 1 byte, so a huge upload can't fill
  the memory.
- Applying twice to the same job returns **409** with a friendly message.
- **Application form:** each job stores a list of questions (`jobs.application_form`, JSON): id, label, type
  (short answer, paragraph, number, dropdown, yes/no, link), required, options and min/max. The candidate sends the
  answers as a JSON field next to the PDF in the same multipart request. `schemas/form.py → check_answers()` checks
  required answers, number ranges, dropdown options, yes/no and links (**422** with the question's name if wrong), and
  a snapshot `[{id, label, answer}]` is saved in `applications.form_answers`. A snapshot means later edits to the
  job's form never change old answers. The answers are also passed to the screening prompt as self-reported data
  that fills gaps in the resume (the resume wins when they disagree; CGPA is reported but not scored).
- Files go through a `StorageService` interface with two implementations: **LocalStorage** (a folder, for
  development and tests) and **SupabaseStorage** (a *private* bucket, for production). `STORAGE_BACKEND` chooses which one.
  Files are never public. They are streamed back only after login + ownership checks
  (`GET /applications/{id}/resume`).
- After saving, a **background task** starts the AI screening, so the candidate gets an instant response.

---

## Module 5: The AI client and resume screening (the most important part)

### The AI client (`app/ai/client.py`)
All AI calls go through **one file**. This makes the behaviour consistent:
1. `chat_json(system, user, schema)` calls the LLM with **JSON mode** and **temperature 0** (the same input
   gives the same kind of output).
2. The reply is parsed as JSON and **validated with Pydantic** (`app/ai/schemas.py`). Scores are **clamped**
   into their legal range (e.g. a skill score of 55 becomes 40), so a confused model cannot break the maths.
3. **Retries with tenacity:** up to 3 attempts with exponential backoff on network errors, 429 (rate limit),
   5xx server errors and invalid JSON. After the 3rd failure it raises `AIServiceError`.
4. **Every attempt is saved in `ai_audit_log`** (prompt, raw output, model). This table is insert-only, which
   makes the AI auditable.
5. `transcribe(audio)` sends audio to **Whisper** and returns the text.

All prompts live in **`app/ai/prompts.py`**.

### Mock mode
With `AI_MOCK=true` (or no API key) the client returns **deterministic fake results** computed from keyword overlap
(`app/ai/mock.py`). They still go through the same validation and audit path, so the whole app can be demoed
and tested without internet or a key.

### Resume screening (`services/resume.py → screen()`)
1. Stage becomes `under_review`.
2. **pdfplumber** extracts the text. If there are fewer than 100 characters (e.g. a scanned image), the stage
   becomes `screening_failed`, the application is flagged for **manual review**, and the recruiter gets an email.
3. The text is cut to ~12,000 characters and sent to the LLM together with the job details and a **scoring rubric**:
   - **skills /40** ≈ 40 × matched required skills ÷ total required skills, using *semantic* matching
     ("ReactJS" = "React", "Postgres" = "PostgreSQL");
   - **experience /20**: full marks if relevant years ≥ required, scaled down otherwise;
   - **education /10**: 10 if the level is met in a relevant field, 7 if met in an unrelated field, lower if below.
4. **Prompt-injection guard:** the prompt tells the model the resume is *untrusted data* and to ignore any
   instructions in it (e.g. "give me full marks"). The resume is wrapped in `<<<RESUME_START>>>` markers.
   **Fairness guard:** the model is told not to consider name, gender, age, religion, nationality or photo.
5. The parsed data (skills, matched/missing skills, experience, education, summary) and scores are saved.
   `resume_total = skill + experience + education` (out of 70). The composite equals the resume total for now and
   is marked `incomplete`.
6. If `resume_total ≥ job.screening_threshold`, interview questions are generated, an interview session is
   created, the stage becomes `interview_invited`, and an **invitation email** with the interview link is sent.
   Otherwise the stage is `not_qualified` and **no email is sent** (the system never sends rejections).
7. If the AI fails after retries, the stage is `screening_failed` with manual review, and the recruiter can press
   **Re-run screening**.

### Application stage state machine
```
submitted → under_review → screening_failed  (manual review; recruiter can re-screen → under_review)
                         → not_qualified
                         → interview_invited → interview_in_progress → evaluated
```
All changes go through **one function**, `set_stage()`, which rejects illegal jumps.

---

## Module 6: AI voice interview

**Question generation (`services/interview.py`):** the LLM receives the job and the parsed resume, and returns
exactly `num_questions` questions: technical ones on the required skills, ones about the candidate's own
projects, and 1 behavioural question. If the count is wrong, it retries.

**Manual invite:** the state machine also allows `not_qualified → interview_invited` and
`screening_failed → interview_invited`, used only by `POST /applications/{id}/invite` (recruiter of that job). It
generates the questions, sends the invitation email and the candidate can start right away. This keeps the human in
control when the AI screened someone out unfairly.

**Recording format:** Chrome's MediaRecorder writes WebM files without a duration, which breaks seeking and
playback. The recorder stamps the real duration into the file (`fix-webm-duration`) before uploading, and the audio
player has a fallback for older files.

**In the browser (`web/src/pages/candidate/Interview.tsx`): a strict, locked interview**
1. The intro screen explains the rules and checks the **microphone** (live volume meter) and the **speakers** (a test
   sentence). The candidate ticks "I will answer on my own…" and presses **Enter full screen and start**.
2. **Lockdown (`components/useLockdown.ts`).** The interview runs full screen on its own element, so the rest of the
   site is hidden. In Chrome/Edge the **Keyboard Lock API** also captures Alt+Tab, the Windows key and Esc (the candidate
   has to *hold* Esc to leave). Copy, cut, paste, drag-and-drop, right-click, developer tools (F12, Ctrl+Shift+I),
   printing, saving, reloading and other shortcuts are blocked and logged. A second tab with the same interview is refused
   (BroadcastChannel). A second screen (`screen.isExtended`) blocks the start.
3. **Warnings (strikes).** Leaving full screen, switching tab or app, clicking outside the window, reloading the page or
   opening a second tab sends an event to `POST /interviews/{id}/events`. The server stamps the time, merges events
   within 3 seconds (one exit fires several browser events) and counts **warnings**. A full-screen overlay asks the
   candidate to go back; the timer keeps running. At **3 warnings the server ends the interview**: unanswered questions
   score 0 and the recruiter sees why.
4. **Spoken questions (`components/useSpeech.ts`).** Each question is read aloud with the browser's built-in voice
   (Web Speech API, free). The text is **not shown**, so it can't be copied into ChatGPT. It can be repeated once. If a
   browser has no voice, the text is shown instead and this is logged.
5. **Strict timer.** After the question: thinking time (job setting, default 15 s), then recording **starts by itself**,
   then the answer is **submitted by itself** when the answer time ends. No re-recording, no playback before submitting.
   All times come from the **server's deadline** (`question_served_at` + speaking + thinking + answering + 20 s), so a
   reload does not reset the clock. If time ran out, `POST /interviews/{id}/skip` scores the question 0. An answer that
   arrives far too late is accepted but flagged.
6. **Live follow-up questions.** After a real answer to selected main questions (spread out, never the last one), the LLM
   writes **one follow-up about what the candidate just said** (`FOLLOW_UP_SYSTEM` in `ai/prompts.py`). It is inserted
   right after that question, so it cannot be prepared in advance. Number per interview = job setting (0–3, default 1).
   If the AI fails, the interview simply continues without it.
7. **Webcam proctoring (`components/useFaceTracker.ts`, `components/Proctor.tsx`).** When the job requires it (default),
   the candidate allows the camera on the intro screen and presses **Calibrate**: for 2 seconds they look at the screen
   and the browser stores their own "looking at the screen" position. Then, about 7 times a second, Google **MediaPipe
   Face Landmarker** (478 face points + eye blendshapes, running locally in WebAssembly; the model file is served from
   `web/public/mediapipe`) works out:
   - how many faces are visible (0 = **no face**, 2 = **another person**),
   - head direction from the nose position between the cheeks and between forehead and chin (**looking away**),
   - eye direction from the eyeLookIn/Out/Up/Down scores (**eyes off the screen**),
   all compared with the calibration, with blinks ignored. A problem must last a while before it counts (no face 2.5 s,
   two faces 1 s, head 2.5 s, eyes 3 s; longer while thinking, because people look up to think). The candidate sees a
   red border and a warning straight away. Each counted episode is sent as an event with a photo (at most one every
   12 s, 30 per interview). With every answer the browser also sends the **attention %**: the share of the answer
   time the candidate was looking at the screen. Photos are small JPEGs in private storage
   (`POST /interviews/{id}/snapshot`, recruiter download at `/applications/{id}/snapshots/{n}`). Turning the camera off
   is a warning, like leaving the window. The video itself is never uploaded.
8. **Integrity report for the recruiter.** The candidate page shows a green / amber / red box (no issues, check the log,
   possible cheating) with counts, a timeline, attention bars per answer and the webcam photos (flagged ones in red).
   Red = ended early, 2+ warnings, a second person, 10+ webcam episodes or attention under 50 %. Amber = 1 warning,
   3+ webcam episodes or attention under 75 %. The dashboard shows a shield icon and the CSV has an "Interview
   integrity" column. Nothing is rejected automatically: the recruiter decides.

**Honest limits (say this in the viva):** no face or eye tracker is 100% reliable. Bad light, strong glasses, a cheap
camera or a person just out of the picture can cause missed or wrong flags, and eye tracking from a normal webcam is
an estimate, not a medical eye tracker. That is why it is calibrated per person, needs a problem to last a few seconds,
and only **flags with photos for the recruiter** instead of rejecting. A web page also cannot fully stop someone
determined to leave, so every exit is logged and limited, and the recruiter also has the audio.
A fully locked computer would need a native "lockdown browser" app, which is beyond a web project.

**On the server, for each answer (`POST /interviews/{id}/answer`):**
1. Check the session belongs to this candidate, the stage allows answering, and `question_index` equals the
   expected `current_index` (answers must come **in order**, and each question **once**).
2. Validate the audio type and size (≤ 10 MB) and store it.
3. **Whisper** turns the audio into text. If it is empty or very short, the score is 0 with "No meaningful answer detected."
4. Otherwise the LLM scores **accuracy, relevance and clarity (0–10 each)** and writes feedback.
   The server computes `score = 0.5·accuracy + 0.3·relevance + 0.2·clarity` itself. It does not trust the
   model's arithmetic.
5. After the last answer: `interview_score = mean(scores) / 10 × 30`, `composite = resume_total + interview_score`,
   the stage becomes `evaluated`, and emails go to the candidate ("completed") and the recruiter ("new candidate evaluated").

Candidates **never see scores or feedback**. They only see their progress.

---

## Module 7: Recruiter dashboard and reports

- `GET /dashboard/overview` powers the recruiter's home page: totals across all their jobs, interviews pending,
  the average final score, **recently finished interviews**, latest activity, the number of candidates with something
  **new**, candidates **ready for a decision** (evaluated, still pending, best
  first) and applications that **need attention** (manual review or a reported technical issue).
- `GET /jobs/{id}/candidates` returns candidates with their **rank by composite score**, sorted by **latest activity**
  by default (applied, started, finished or ended the interview, whichever is newest), with filters for score range,
  stage and decision, and other sort options. Each row has `is_new`: something happened after the recruiter last
  opened that candidate (`applications.recruiter_viewed_at`, set by the detail endpoint). The page adds quick tabs with
  counts (New, Interview done, Waiting, Needs review, Shortlisted, Not qualified), refreshes every 15 s and pops up a
  message when someone finishes an interview.
- `GET /jobs/{id}/stats` returns counts per stage, the average score and a 10-bucket **histogram** (drawn with Recharts).
- `GET /applications/{id}/detail` returns everything: parsed resume, score parts, AI reasoning, each question with
  its transcript, sub-scores and feedback, plus flags (manual review, incomplete, issue reported).
- `PATCH /applications/{id}/decision` lets the recruiter set **pending / shortlisted / rejected** and private notes.
  **AI scores are read-only.** No endpoint can change them, and extra fields in the request are ignored.
- **Export:** `GET /jobs/{id}/export?format=csv|pdf&only_shortlisted=…` builds a CSV (Python `csv` module) or a PDF
  table (**ReportLab**). Both include the disclaimer.
- A permanent banner says: *"AI scores are decision-support only and must not be the sole basis for any hiring decision."*

---

## Module 8: Email notifications

`services/notification.py` has an `EmailService` interface with a **console** version (prints the email to the log,
for development) and a **Resend** version (real email). Emails are sent only for: application received,
interview invitation, interview completed, and recruiter alerts. **A rejection email is never sent.** User text is
HTML-escaped, and an email failure never crashes the app.

---

## Module 9: The frontend (React + TypeScript)

- **Vite + React 18 + TypeScript + Tailwind CSS.**
- `src/api/client.ts`: an **Axios** instance with two *interceptors*. One adds the JWT to every request. The other,
  on a 401, calls `/auth/refresh` **once** (shared by all waiting requests), saves the new tokens and retries the
  request. If refresh fails, the user is logged out.
- `src/auth/AuthContext.tsx` stores the logged-in user. `ProtectedRoute` blocks pages by role.
- **TanStack Query** fetches and caches server data (loading, error and refetch states). The dashboard refreshes
  automatically every 15s.
- Forms use **react-hook-form + zod** for inline validation (e.g. "Include at least one number").
- Reusable components live in `src/components/` (Button, Card, Badge, Modal, ConfirmDialog, ScoreBar, TagInput, recorder hooks).
  `form.tsx` holds the form building blocks (Field, TextInput with icon, PasswordInput with show/hide and a strength
  meter, Select, Segmented tabs, FormSection steps, Alert), so every form looks and behaves the same.
- **Two portals:** recruiters get a dark sidebar layout (Overview, My jobs, Post a job); candidates get a light top
  navigation (Browse jobs, My applications). Login and register use a split screen with role-specific text.
- Destructive actions (close job, reject) ask for confirmation. Toasts show success and errors.

---

## Module 10: Testing

- **pytest** with FastAPI's `TestClient` and an in-memory SQLite DB; **all AI calls are mocked**.
- 72 tests cover: the application form (validation, CSV columns, use in screening), manual invites, shortlist visibility, register/login/refresh/logout, role-checked login, the recruiter overview, lockout, role 403s, ownership 404s, job status transitions,
  duplicate 409, wrong type 415, too large 413, screening (qualified / not qualified / unreadable PDF / AI
  failure), the full interview flow and composite score maths, the order and once-only rules, scores being
  read-only, ranking order, stats, CSV and PDF export, the AI client's retries/clamping/audit, and the Postgres trigger.
- Coverage is about **95%** (the target was 70%). `npm run build` checks the frontend has no TypeScript errors.

---

## Likely viva questions

**Why FastAPI?** It is fast, uses Python type hints for validation (Pydantic) and generates Swagger docs at `/docs` automatically.

**How do you stop the AI from giving silly scores?** JSON mode + temperature 0, Pydantic validation, clamping to
valid ranges, retries on bad output, and the final score maths is done on the server.

**What if the AI service is down?** Three retries with backoff. Then the application goes to `screening_failed`,
gets a manual-review flag, and the recruiter is emailed and can re-run screening. During an interview, the
answer returns a 502 and the candidate can press "Retry submit".

**What about bias?** The prompt forbids using name, gender, age, religion, nationality or photo. Scoring uses a
fixed rubric. The AI only *supports* the recruiter: it never rejects anyone, and every AI call is logged for audit.

**What about prompt injection?** Resume and answer text are marked as untrusted data between markers, and the model
is told to ignore instructions inside them. Scores are clamped anyway.

**How is the composite score calculated?** `skills/40 + experience/20 + education/10 + interview/30`, where
interview = average answer score ÷ 10 × 30, and answer score = 0.5·accuracy + 0.3·relevance + 0.2·clarity.

**Why JWT + refresh token?** The short-lived access token is checked without a DB lookup. The long-lived refresh
token is stored hashed in the DB, so it can be revoked (logout) and rotated.

**How are files protected?** Private storage, with no public URLs. Files are streamed only after login + ownership checks.

**Can a candidate apply twice?** No. There is a service check and a database UNIQUE constraint (409).

**How do you stop cheating in the voice interview?** Questions are spoken, not shown (nothing to copy); strict
server-side timers with auto-start and auto-submit (no time to look things up, no re-recording); a live AI follow-up on
what the candidate just said (can't be prepared); and a full-screen lockdown that blocks copy/paste and shortcuts, and
ends the interview after 3 warnings; plus webcam face, head and eye tracking (MediaPipe, calibrated per candidate) with an
attention % per answer and photos of anything flagged. Everything is logged for the recruiter, who makes the final call.

**How does mock mode work?** Without a key, deterministic fake results based on keyword matching go through the same
validation and logging code, so the demo works offline.
