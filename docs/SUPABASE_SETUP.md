# Connecting a real database (Supabase)

By default the app runs on a local SQLite file, so it works with nothing set up. For the real version (and for
deployment) use **Supabase**. It is free, and it gives you a PostgreSQL database plus private file storage for resumes and
interview audio.

You never need to send your keys to anyone. They only go into **`backend/.env`** on your own computer (that file is
ignored by git) and later into Render's environment settings.

---

## 1. Create the project (about 3 minutes)

1. Sign up at <https://supabase.com> and click **New project**.
2. Give it a name (e.g. `ai-recruiter`), pick the region closest to you (e.g. *Mumbai / ap-south-1* for Pakistan),
   and set a **database password**. Use letters and numbers only, to avoid special characters breaking the URL.
   **Write the password down.**
3. Wait until the project says it's ready.

## 2. Copy the database connection string

1. In the project, click **Connect** (top of the page).
2. Choose **Session pooler**. It works on every network (the "Direct connection" needs IPv6, which most home internet
   connections don't have).
3. Copy the URI. It looks like this:

   ```
   postgresql://postgres.abcdefghijk:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
   ```

4. Make two changes:
   - change the start from `postgresql://` to **`postgresql+psycopg://`**
   - replace `[YOUR-PASSWORD]` with your password (remove the brackets too)

   ```
   postgresql+psycopg://postgres.abcdefghijk:MyPassw0rd@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
   ```

## 3. Create the private storage bucket

1. Left menu → **Storage** → **New bucket**.
2. Name: **`recruiter-files`**. Keep **Public bucket turned OFF**. The app streams files only to logged-in users who are
   allowed to see them.

## 4. Copy the project URL and the secret key

1. Left menu → **Project Settings** (gear icon) → **Data API**: copy the **Project URL**
   (`https://abcdefghijk.supabase.co`). It is also shown on the project home page with a **Copy** button.
2. **Project Settings → API Keys**. Use either one, both work:
   - **Secret keys** tab → copy the **secret** key (`sb_secret_...`, click the eye icon to show it), or
   - **Legacy API keys** tab → copy the **`service_role`** key (`eyJ...`).

   Do **not** use the *publishable* / *anon* key. The secret key is used only by the backend and must never go into
   the `web/` folder or into git.

## 5. Put the values in `backend/.env`

Open `backend/.env` (create it from `backend/.env.example` if it doesn't exist) and set:

```ini
DATABASE_URL=postgresql+psycopg://postgres.abcdefghijk:MyPassw0rd@aws-0-ap-south-1.pooler.supabase.com:5432/postgres

STORAGE_BACKEND=supabase
SUPABASE_URL=https://abcdefghijk.supabase.co
SUPABASE_SERVICE_KEY=sb_secret_...   # or the legacy service_role key eyJ...
SUPABASE_BUCKET=recruiter-files

# a long random secret for login tokens:  openssl rand -hex 32
JWT_SECRET=paste-the-64-character-value-here
```

Optional, for real AI instead of mock AI (free key from <https://console.groq.com/keys>):

```ini
LLM_API_KEY=gsk_...
STT_API_KEY=gsk_...          # the same Groq key works for both
AI_MOCK=false
```

## 6. Check it, then start

**Easiest:** run `./start.sh` again. When the database isn't SQLite it first runs the setup checker, then creates the
tables and adds the demo accounts to Supabase automatically.

**Or by hand** (in `backend/`, with the venv active):

```bash
python -m scripts.check_setup     # tests the database, AI keys, storage bucket, email and JWT secret
alembic upgrade head              # creates the tables in Supabase
python -m scripts.seed --reset    # adds the demo accounts (only touches @demo.com data)
uvicorn app.main:app --port 8000
```

A good check looks like this:

```
Database
  using postgresql+psycopg://postgres.abcdefghijk:****@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
  ✔ Connected
  ✔ Tables exist (migrations applied)
  ✔ 7 users in the database
File storage
  ✔ Supabase bucket 'recruiter-files' upload/download works
All good!
```

You can now see the data in Supabase: **Table Editor** shows `users`, `jobs`, `applications` and so on, and
**Storage → recruiter-files** shows the uploaded resumes and audio.

## Common problems

| Message from `check_setup` | Fix |
|---|---|
| `password authentication failed` | Wrong password in the URL. Reset it in **Project Settings → Database**, then update `.env`. |
| `could not translate host name` / `Network is unreachable` / timeout | You used the *Direct connection* URL. Use the **Session pooler** URL from step 2. |
| `The URL must start with postgresql+psycopg://` | Change the start of the URL as shown in step 2. |
| `Tables are missing` | Run `alembic upgrade head` (start.sh does this for you). |
| `Supabase storage failed ... Bucket not found` | Create the bucket `recruiter-files` (step 3), or fix `SUPABASE_BUCKET`. |
| `Supabase storage failed ... 401/403` | You copied the *publishable/anon* key. Use the **secret** (or legacy **service_role**) key. |
| Project paused | Free projects pause after a week with no activity. Open the Supabase dashboard and click **Restore**. |

## For deployment (Render)

Use the same values as environment variables in Render (see the *Deployment* section of the README). The Session pooler
URL works there too.
