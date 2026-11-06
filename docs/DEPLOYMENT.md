# Putting the project online (free)

There are two ways. **Option A needs no Git at all**: you upload both parts from your PC with one command each.
Option B (GitLab + Render + Vercel) is further down, in case you ever want automatic deploys from Git.

| Part | Option A (no Git) | Option B |
|---|---|---|
| Database + files | Supabase | Supabase |
| Backend (FastAPI) | **Vercel** (serverless) | Render (Docker, sleeps after 15 min) |
| Frontend (React) | **Vercel** | Vercel |

---

# Option A: everything on Vercel, uploaded from your PC

You need: Supabase working on your PC (`check_setup` says **All good!**), Node.js (you have it), and a free Vercel
account (<https://vercel.com/signup>, sign up with your email).

### A1. Install the Vercel tool and log in (once)

```bat
npm install -g vercel
vercel login
```

Choose **Continue with Email** and click the link Vercel emails you.

### A2. Upload the backend

```bat
cd C:\Users\dell\Downloads\ai-recruiter\ai-recruiter\backend
vercel
```

Answer the questions:

| Question | Answer |
|---|---|
| Set up and deploy? | **Y** |
| Which scope? | your account (press Enter) |
| Link to existing project? | **N** |
| Project name? | `ai-recruiter-api` |
| In which directory is your code located? | `./` (press Enter) |
| Want to modify these settings? | **N** |

Your `backend\.env` is uploaded with the code (set `APP_ENV=production` in it first). If you prefer to keep it off Vercel, add `.env` to `backend\.vercelignore` and enter the settings in the dashboard instead:

1. Open <https://vercel.com/dashboard> → **ai-recruiter-api** → **Settings** → **Environment Variables**.
2. Open your `backend\.env` in VS Code, select everything (Ctrl+A), copy, and **paste it into the "Key" box**.
   Vercel splits it into separate variables by itself.
3. Change these values before saving:
   - `APP_ENV` = `production`
   - `CORS_ORIGINS` and `FRONTEND_URL`: leave as they are for now (changed in A4)
4. Click **Save**.

Then upload again, this time as the live version:

```bat
vercel --prod
```

**Check:** open `https://ai-recruiter-api.vercel.app/health` (Vercel prints your exact address). It should show
`{"status":"ok","ai_mock":false}`. If it shows an error, open the project → **Logs** and send me what it says.

**Speed:** `vercel.json` runs the backend in Vercel's Mumbai region (`bom1`), next to the Supabase database
(`aws-0-ap-south-1`). If your Supabase project is in another region, change `regions` to the closest Vercel
region; a far-away database makes every page slow because each query crosses the world.

For the live site, use Supabase's **transaction pooler** (port `6543`) in `DATABASE_URL`: same address as before,
only `:5432` changed to `:6543`. It handles the short-lived Vercel functions better than the session pooler.

### A3. Upload the frontend

```bat
cd ..\web
vercel
```

Same answers as before, but name the project `ai-recruiter`. Then in the dashboard → **ai-recruiter** → **Settings** →
**Environment Variables**, add:

- `VITE_API_URL` = your backend address from A2, e.g. `https://ai-recruiter-api.vercel.app` (no `/` at the end)
- `VITE_SHOW_DEMO` = `true` (only if you want the "Fill demo account" buttons for the viva)

Then:

```bat
vercel --prod
```

**Check:** your site opens at `https://ai-recruiter.vercel.app` (or the address Vercel prints).

### A4. Connect the two

In the dashboard → **ai-recruiter-api** → **Settings** → **Environment Variables**, edit:

- `CORS_ORIGINS` = your frontend address, e.g. `https://ai-recruiter.vercel.app`
- `FRONTEND_URL` = the same address

Then upload the backend once more so it uses them:

```bat
cd ..\backend
vercel --prod
```

**Check:** sign in on the live site as `recruiter@demo.com` / `Demo1234`.

### Updating later

After changing code on your PC, run `vercel --prod` in the folder you changed (`backend` or `web`). If you add a
database migration, run `alembic upgrade head` on your PC first (it updates Supabase directly).

### Good to know about Option A

- The backend runs "serverless": it starts on demand, so the first request after a quiet period takes a few seconds.
- Resume screening happens while the candidate waits after pressing Apply (a few seconds), because serverless
  functions can't keep working after they answer.
- Vercel accepts uploads up to about 4.5 MB per request, so very large PDF resumes (over 4.5 MB) are refused.

---

# Option B: GitLab + Render + Vercel


## B1. Supabase on your own PC first

Follow [SUPABASE_SETUP.md](SUPABASE_SETUP.md) (connection string, bucket `recruiter-files`, secret key), then in the
`backend` folder:

```bat
python -m scripts.check_setup
alembic upgrade head
python -m scripts.seed --reset
uvicorn app.main:app --port 8000
```

**Check:** `check_setup` ends with **All good!**, the app works on <http://localhost:5173>, and Supabase
**Table Editor** shows the `users`, `jobs` and `applications` tables.

## B2. Put the code on GitLab

1. Sign up at <https://gitlab.com> (free). **New project → Create blank project**, name `ai-recruiter`,
   visibility **Private**, untick "Initialize repository with a README".
2. Install Git for Windows if you don't have it: <https://git-scm.com/download/win>.
3. In VS Code's terminal, in the `ai-recruiter` folder (the one with `backend` and `web`):

   ```bat
   git init
   git add .
   git status
   ```

   **Check:** `git status` must **not** list `backend/.env` or `web/.env`. They contain your keys and are ignored on
   purpose. If you see them, stop and ask.

   ```bat
   git commit -m "AI Recruitment Assistant"
   git branch -M main
   git remote add origin https://gitlab.com/YOUR-USERNAME/ai-recruiter.git
   git push -u origin main
   ```

   When Git asks for a password, use a GitLab **access token** (GitLab → your avatar → Preferences → Access tokens →
   scope `write_repository`), not your account password.

## B3. Backend on Render

1. Sign up at <https://render.com> with your GitLab account.
2. **New → Web Service** → pick the `ai-recruiter` repo.
3. Settings:
   - **Language / Runtime:** Docker
   - **Root Directory:** `backend`
   - **Instance type:** Free
   - **Health Check Path:** `/health` (under Advanced)
4. **Environment variables** (Advanced → Add environment variable). Copy the values from your `backend\.env`:

   | Key | Value |
   |---|---|
   | `APP_ENV` | `production` |
   | `DATABASE_URL` | your Supabase `postgresql+psycopg://...` URL |
   | `JWT_SECRET` | a new long random value (click **Generate**) |
   | `LLM_API_KEY` | your Groq key |
   | `STT_API_KEY` | your Groq key |
   | `AI_MOCK` | `false` |
   | `STORAGE_BACKEND` | `supabase` |
   | `SUPABASE_URL` | `https://xxxx.supabase.co` |
   | `SUPABASE_SERVICE_KEY` | your secret key |
   | `SUPABASE_BUCKET` | `recruiter-files` |
   | `EMAIL_BACKEND` | `console` (emails then appear in Render's **Logs**) |
   | `CORS_ORIGINS` | `http://localhost:5173` for now (changed in step 5) |
   | `FRONTEND_URL` | `http://localhost:5173` for now |

5. **Create Web Service** and wait for "Live" (the first build takes a few minutes).

**Check:** open `https://YOUR-API.onrender.com/health`. It should show `{"status":"ok","ai_mock":false}`.
If the deploy fails with "Unsafe production settings", the message says which variable to fix.

## B4. Frontend on Vercel

1. Sign up at <https://vercel.com> with your GitLab account.
2. **Add New → Project** → import `ai-recruiter`.
3. **Root Directory:** `web` (click Edit). Framework preset: **Vite** (detected automatically).
4. Environment variables:
   - `VITE_API_URL` = `https://YOUR-API.onrender.com` (no `/` at the end)
   - `VITE_SHOW_DEMO` = `true` only if you want the "Fill demo account" buttons on the live site (handy for the viva).
     Leave it out for a clean, real login page.
5. **Deploy**.

**Check:** the site opens at `https://YOUR-SITE.vercel.app` and the logo and login page show.

## B5. Connect the two

In Render → your service → **Environment**, change:

- `CORS_ORIGINS` = `https://YOUR-SITE.vercel.app`
- `FRONTEND_URL` = `https://YOUR-SITE.vercel.app`

Save (Render redeploys by itself).

**Check:** sign in on the Vercel site as `recruiter@demo.com` / `Demo1234` (added in step 1, because the live site
uses the same Supabase database).

## Before the demo or viva

- Open the Render URL `/health` about a minute before you present, so the free server is awake.
- Do one full run: register a new candidate, apply with a PDF from `backend/sample_resumes`, do the interview in
  Chrome (allow microphone and camera), then check the recruiter dashboard.
- Change the demo passwords if the site will stay public (sign in → **Change password**).

## Updating the live site later (Option B)

Make your change on your PC, then:

```bat
git add .
git commit -m "describe the change"
git push
```

Render and Vercel both redeploy automatically. Database changes (new migrations) are applied by the backend on start.

## Emails (forgot password, confirm email, interview invitations)

With `EMAIL_BACKEND=console`, emails are only printed in the server logs, not sent. Password codes (forgot
password and change password) need real emails, so set up one of these.

**Easiest: Gmail (no domain needed, about 500 emails a day).**

1. On the Gmail account that will send the emails, turn on 2-Step Verification
   (Google Account, Security, 2-Step Verification).
2. Open <https://myaccount.google.com/apppasswords>, make an App password called "RecruitAI" and copy the
   16 letters.
3. In Vercel (project ai-recruiter-api, Settings, Environment Variables) add `EMAIL_BACKEND=smtp`,
   `SMTP_USER=<that gmail address>`, `SMTP_PASSWORD=<the 16 letters, no spaces>` and
   `FRONTEND_URL=<your live frontend address>`. `SMTP_HOST` and `SMTP_PORT` already default to Gmail.
4. Redeploy the backend (`vercel --prod` in `backend`).

**Or Resend:**

1. Make a free account at <https://resend.com> and create an API key.
2. In the backend settings (Vercel: Project, Settings, Environment Variables) set `EMAIL_BACKEND=resend`,
   `RESEND_API_KEY=<your key>` and `FRONTEND_URL=<your live frontend address>` (the links in emails use it).
3. Without your own domain, Resend only delivers to the email you signed up with. That is enough for the viva.
   To send to anyone, add a domain in Resend (Domains, Add domain), add the DNS records it shows at your domain
   seller, wait for "Verified", then set `EMAIL_FROM=RecruitAI <no-reply@your-domain.com>`.
4. Redeploy the backend (`vercel --prod` in `backend`).

**Confirm email:** every new account gets a "Confirm your email" link. By default people can still use the site
before confirming (`REQUIRE_EMAIL_VERIFICATION=false`), because without a verified domain most people would never
get the email. Once your domain is verified, set `REQUIRE_EMAIL_VERIFICATION=true`: then people must confirm before
they can apply or post jobs. Accounts that existed before this update count as confirmed.

**One account per email:** an email address can only be used once (capital letters don't matter).

## Settings added in the supervisor update

| Setting | Default | What it does |
|---|---|---|
| `REQUIRE_EMAIL_VERIFICATION` | `false` | Must confirm email before applying or posting jobs |
| `RATE_LIMIT_ENABLED` | `true` | Limits on sign in, sign up, apply and uploads per IP. Only turn off for a local load test |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | `10`, `10` | Database connections per server process (not used on Vercel) |

After pulling this update, run `alembic upgrade head` once from `backend` (it adds candidate profiles, minimum
CGPA, the device lock and the other new columns to Supabase).

## Load test

See [load-test/summary.md](load-test/summary.md). 500 candidates using the site at the same time: no failed
requests, median 11 ms, 95% of requests under 45 ms.

## Common problems

| Problem | Fix |
|---|---|
| Login on the live site says "Cannot reach the server" | `VITE_API_URL` on Vercel is wrong, or Render is still waking up. After changing it, **Redeploy** on Vercel. |
| Browser console shows a CORS error | `CORS_ORIGINS` on Render must be exactly your Vercel URL, with `https://` and no `/` at the end. |
| Refreshing a page on Vercel shows 404 | The Root Directory must be `web` (it contains `vercel.json`). |
| Microphone or camera don't work | Use the `https://` Vercel address in Chrome or Edge, and allow both when asked. |
| Supabase project "paused" | Free projects pause after a week without use. Open the Supabase dashboard and click **Restore**. |

## Demo candidates

`python -m scripts.seed_candidates` (run in `backend`) adds 8 candidate accounts with a photo, phone, city and a
resume, ready to apply to the jobs you post. It does not add a recruiter or jobs. All use the password `Demo1234`:
ali.hassan, fatima.zahra, hassan.raza, ayesha.siddiqui, usman.ghani, maryam.iqbal, bilal.ahmed and hira.shah, each
`@demo.com`. Running it again skips accounts that exist; `--reset` deletes these 8 first.

## Start again with empty data

`python -m scripts.wipe` (from `backend`) deletes **everything** in the database and storage that `backend\.env`
points to: all accounts, jobs, applications, interviews, the AI log, and every resume, photo, recording and
snapshot. It shows where it will delete and asks you to type `DELETE` first. The tables stay, so the site keeps
working, empty. `python -m scripts.seed` adds the demo accounts again if you want them
(`python -m scripts.seed --reset` only replaces the `@demo.com` demo data and leaves other accounts alone).
