<p align="center">
  <img src="docs/banner.svg" alt="AI Recruitment Assistant" width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Tailwind_CSS-3-06B6D4?logo=tailwindcss&logoColor=white" alt="Tailwind CSS">
  <img src="https://img.shields.io/badge/AI-Groq-F55036" alt="Groq">
  <img src="https://img.shields.io/badge/tests-117_passed-22C55E" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-94%25-22C55E" alt="Coverage">
</p>

<p align="center">
  <b>Final Year Project</b> · BS Computer Science · Lahore Garrison University · Session 2022 to 2026
</p>

---

## About

Hiring starts with slow, repetitive work. Someone has to read every resume, compare it with the job and run the first round of interviews. **AI Recruitment Assistant** automates those first two steps and keeps the recruiter in charge of every decision.

1. A recruiter posts a job with the skills, minimum degree, CGPA, a screening threshold and a custom application form.
2. Candidates build a profile and apply with a PDF resume.
3. A large language model reads the resume and scores it against a fixed rubric.
4. Candidates who reach the threshold get an automatic invitation to a **spoken AI interview** with questions written for the job and for their own resume.
5. Every answer is transcribed, scored and explained. Full screen lockdown and webcam checks make cheating harder.
6. The recruiter gets a ranked dashboard with reasons, transcripts, recordings, an integrity report and a printable report for each candidate.

> **The AI never rejects anyone.** Scores support the recruiter's decision. No rejection email is ever sent automatically.

<p align="center">
  <img src="docs/screenshots/dashboard.jpg" alt="Recruiter job dashboard with ranked candidates" width="90%">
</p>

---

## Features

<table>
<tr>
<td width="50%" valign="top">

### For recruiters
- Post jobs with required skills, experience, degree and CGPA
- **Application form builder** with required and custom questions
- **Screening threshold** slider to control who is invited
- Ranked dashboard with filters, search, badges and charts
- Candidate page with score breakdown, matched and missing skills and AI reasoning
- Interview transcripts, audio playback and AI feedback
- **Integrity report** with episodes, attention and photo evidence
- Manual invite, shortlist, private notes, CSV and PDF export

</td>
<td width="50%" valign="top">

### For candidates
- Profile with completion check and resume upload
- Browse jobs and apply with a short form
- Clear progress steps and plain reasons on every application
- Device check and camera calibration before the interview
- Questions read aloud **and** shown on screen
- Thinking time, then automatic recording with a countdown
- Interview resumes at the right question after a reload
- Works at phone width for browsing and applying

</td>
</tr>
</table>

---

## Screenshots

| Landing page | Sign in |
|---|---|
| ![Landing](docs/screenshots/landing.jpg) | ![Sign in](docs/screenshots/login.jpg) |

| Recruiter overview | Post a job |
|---|---|
| ![Overview](docs/screenshots/overview.jpg) | ![Job form](docs/screenshots/jobform.jpg) |

| Candidate score breakdown | Job charts |
|---|---|
| ![Candidate](docs/screenshots/candidate.jpg) | ![Charts](docs/screenshots/charts.jpg) |

| Browse jobs | Job details and application form |
|---|---|
| ![Browse](docs/screenshots/browse.jpg) | ![Job detail](docs/screenshots/jobdetail.jpg) |

| My applications | Interview setup and calibration |
|---|---|
| ![My applications](docs/screenshots/myapps.jpg) | ![Setup](docs/screenshots/setup.jpg) |

| Spoken question | Answer recording |
|---|---|
| ![Question](docs/screenshots/question.jpg) | ![Recording](docs/screenshots/recording.jpg) |

| Second person detected | Phone detected |
|---|---|
| ![Two faces](docs/screenshots/twofaces.jpg) | ![Phone](docs/screenshots/phone.jpg) |

| Integrity report | Printable candidate report |
|---|---|
| ![Integrity](docs/screenshots/integrity.jpg) | ![Report](docs/screenshots/report.jpg) |

<p align="center">
  <img src="docs/screenshots/mobile.jpg" alt="Candidate portal at phone width" width="260">
</p>

---

## How scoring works

All the maths runs on the server. The AI only gives the part scores, and the server keeps each one inside its range and adds them up.

| Part | Marks | How it is worked out |
|---|---:|---|
| Skills | 40 | 40 × (required skills matched ÷ required skills), using meaning, not exact words |
| Experience | 20 | Full marks at the required years, a share of 20 below that |
| Education | 10 | 10 for the required degree in a related field, lower for an unrelated field or a lower level |
| **Resume total** | **70** | Compared with the job's **screening threshold** to decide who is invited |
| Interview | 30 | Each answer = 0.5 × accuracy + 0.3 × relevance + 0.2 × clarity (out of 10), then the average × 3 |
| **Final score** | **100** | Resume total + interview |

The threshold does not change anyone's marks. It is a cut off for the interview that the recruiter sets for each job (0 to 70, default 40).

---

## AI inside the system

| Task | Model | Runs on |
|---|---|---|
| Resume screening | Llama 3.3 70B | Groq API |
| Interview questions and live follow ups | Llama 3.3 70B | Groq API |
| Answer scoring and feedback | Llama 3.3 70B | Groq API |
| Speech to text | Whisper large v3 | Groq API |
| Face, head and eye tracking | MediaPipe Face Landmarker | Candidate's browser |
| Phone, notes, screen and person detection | EfficientDet Lite0 | Candidate's browser |

<p align="center">
  <img src="docs/diagrams/ai_pipeline.png" alt="Controlled AI evaluation pipeline" width="80%">
</p>

**How the AI is kept safe and reliable**
- Structured JSON output at temperature 0, checked with Pydantic schemas
- Every score clamped to its range, and totals worked out by the server
- Retries with exponential backoff and an ordered list of **fallback models** for free tier limits
- Guards against hidden instructions in resumes (prompt injection) and against using protected attributes
- An **insert only audit log** of every AI request, enforced by a PostgreSQL trigger
- A **mock AI mode** so the full app and all tests run without a key or internet

---

## Interview integrity

<p align="center">
  <img src="docs/diagrams/integrity.png" alt="Integrity monitoring flow" width="80%">
</p>

- Full screen lockdown: leaving the window, switching tabs or reloading counts as a warning, and **three warnings end the interview**
- Copy, paste, right click and developer tool shortcuts are blocked and logged
- Webcam tracking calibrated to each candidate: no face, more than one face, head turned away and eyes off the screen
- Object detection for a **mobile phone**, a book or notes, another screen or another person
- Each interview is locked to **one device**, and a second tab is detected
- Video never leaves the browser. Only events and a few small photos are stored as evidence

---

## Architecture

<p align="center">
  <img src="docs/diagrams/architecture.png" alt="Three tier architecture" width="85%">
</p>

The browser only displays things and gathers evidence. The server owns every rule, score, timer and access check.

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, TypeScript, Tailwind CSS, React Router, TanStack Query, Axios, react-hook-form, zod, Recharts |
| Browser media | Web Speech API, MediaRecorder, MediaPipe Tasks Vision |
| Backend | Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, pdfplumber, tenacity, ReportLab |
| Security | JWT access and refresh tokens, bcrypt, SlowAPI rate limiting, role and ownership checks |
| Database and files | PostgreSQL (Supabase) and private object storage, SQLite for local tests |
| AI | Groq through the OpenAI compatible SDK |
| Hosting | Vercel (web and API), Supabase, Resend or Gmail SMTP for email |

<details>
<summary><b>More diagrams</b></summary>

<br>

**Use case diagram**

<img src="docs/diagrams/usecase.png" alt="Use case diagram" width="85%">

**Entity relationship diagram**

<img src="docs/diagrams/er.png" alt="ER diagram" width="85%">

**Application state machine**

<img src="docs/diagrams/state.png" alt="State machine" width="85%">

</details>

---

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── ai/            # Groq client, prompts, output schemas, mock AI
│   │   ├── core/          # security, dependencies, rate limiter
│   │   ├── models/        # SQLAlchemy models
│   │   ├── routers/       # REST endpoints
│   │   ├── schemas/       # request and response schemas
│   │   ├── services/      # business rules: screening, interview, integrity, scoring
│   │   └── main.py
│   ├── alembic/           # 7 database migrations
│   ├── scripts/           # seed data, setup check, load test
│   ├── sample_resumes/    # 6 sample PDF resumes for demos
│   └── tests/             # 118 automated tests
├── web/
│   └── src/
│       ├── api/           # API client and types
│       ├── auth/          # auth context and protected routes
│       ├── components/    # UI, charts, proctoring hooks
│       └── pages/         # auth, recruiter and candidate pages
├── docs/                  # guides, diagrams, screenshots, load test results
└── .github/workflows/     # CI: lint, tests, migrations, frontend build
```

---

## Getting started

You need **Python 3.11** and **Node.js 20**. No AI key is needed to try it: without one, the app runs in mock AI mode.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env             # Windows: copy .env.example .env
alembic upgrade head             # create tables and the audit log trigger
python -m scripts.seed --reset   # demo data (deletes existing data in that database)
uvicorn app.main:app --reload    # http://localhost:8000/docs
```

### Frontend

```bash
cd web
cp .env.example .env             # VITE_API_URL=http://localhost:8000
npm install
npm run dev                      # http://localhost:5173
```

On Linux or macOS, `./start.sh` does all of this in one step with SQLite and mock AI.

### Real AI

Create a free key at [console.groq.com](https://console.groq.com/keys). In `backend/.env` set `LLM_API_KEY`, `STT_API_KEY` and `AI_MOCK=false`, then restart the backend. Check everything with:

```bash
python -m scripts.check_setup
```

### Demo accounts

After seeding, every password is `Demo1234`.

| Account | Shows |
|---|---|
| `recruiter@demo.com` | Jobs with ranked candidates |
| `candidate1@demo.com` | Strong match, interview done |
| `candidate2@demo.com` | Medium match, interview done |
| `candidate3@demo.com` | Weak match |
| `candidate4@demo.com` | Unrelated field, not qualified |
| `candidate5@demo.com` | Invited, ready for a live interview |
| `candidate6@demo.com` | Scanned PDF, flagged for manual review |

---

## Testing and results

```bash
cd backend
pytest --cov=app                 # 118 tests, AI mocked
ruff check . && black --check .  # lint and format
cd ../web && npm run build       # type check and production build
```

| Check | Result |
|---|---|
| Automated backend tests | 117 passed, 1 skipped |
| Statement coverage | 94% |
| System test cases | 28 of 28 passed |
| Load test, 500 users at once | 0 failed requests, 95th percentile 43 ms |
| Non functional requirements | 18 of 18 met |

<p align="center">
  <img src="docs/load-test/response-time.png" alt="Response time under load" width="48%">
  <img src="docs/load-test/throughput-errors.png" alt="Throughput and errors" width="48%">
</p>

---

## Deployment

Step by step guides:
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md): deploy the backend and frontend
- [docs/SUPABASE_SETUP.md](docs/SUPABASE_SETUP.md): database and private file storage
- [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md): every module explained in simple English
- [DECISIONS.md](DECISIONS.md): design choices

---

## Security

- API keys stay on the server and never reach the browser
- `.env` files are never committed. Only `.env.example` files with empty values are included
- Passwords hashed with bcrypt, refresh tokens stored hashed, lockout after repeated failed sign ins
- Role and ownership checked on every endpoint
- Resumes, recordings and photos are private and streamed only after sign in

---

## Future work

- Measure agreement between AI scores and expert recruiters
- Regular fairness audits
- OCR for scanned resumes
- More languages, including Urdu
- Job board and HR system integrations

---

<p align="center">
  Made by <a href="https://github.com/Umairbhai07">@Umairbhai07</a>
</p>
