# Load test results

Local test: FastAPI with 4 workers and PostgreSQL on one 4-core machine

| Users at once | Requests | Per second | Median | 95% | 99% | Failed |
|---:|---:|---:|---:|---:|---:|---:|
| 50 | 1185 | 18.9 | 9 ms | 22 ms | 87 ms | 0.0% |
| 100 | 2375 | 37.8 | 9 ms | 24 ms | 86 ms | 0.0% |
| 250 | 5948 | 94.5 | 8 ms | 19 ms | 83 ms | 0.0% |
| 500 | 11912 | 189.4 | 11 ms | 43 ms | 103 ms | 0.0% |

## Per request type at the largest step

| Request | Count | Median | 95% |
|---|---:|---:|---:|
| job list | 3858 | 12 ms | 29 ms |
| my applications | 1621 | 8 ms | 22 ms |
| my profile | 1663 | 8 ms | 24 ms |
| open a job | 2701 | 12 ms | 31 ms |
| qualify check | 1569 | 9 ms | 26 ms |
| sign in | 500 | 88 ms | 139 ms |

## How the test works

`backend/scripts/load_test.py` creates test candidates, then simulates each one: sign in once, then keep clicking
through the job list, a job, the "do I qualify" check, their profile and their applications, waiting 1 to 3
seconds between clicks (like a person reading). People arrive over the first 30 seconds of each 60 second step,
then all of them stay active. The AI is switched off (`AI_MOCK=true`) because the test measures our server, not Groq.

## Problems the test found and fixed

1. **Sign in held a database connection while checking the password.** Password checking (bcrypt) is slow on
   purpose, so many sign-ins at once used up all connections. The connection is now handed back first.
2. **The server could freeze under heavy load.** FastAPI ran up to 40 requests at once per process but there were
   only 15 database connections, so threads waited for connections that could never be released. Now a process
   runs only as many requests at once as it has connections; the rest wait their turn instead of freezing.
3. **Connection pool size** is now a setting (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`) and a request gives up after
   10 seconds instead of 30 when the database is overloaded.

## What this means for the live site

- This was one 4-core machine running the server, the database and the 500 simulated users together. The live
  site on Vercel starts more copies of the backend automatically when traffic grows, so the server itself is not
  the limit.
- The real limits on the free plans are **Supabase connections** (the pooler allows a few hundred) and **Groq**:
  the free plan allows about 30 AI requests per minute. 500 people browsing is fine; 500 people applying or being
  interviewed in the same minute would queue. Answers are never lost: if the AI is busy, the answer is saved and
  scored a little later. A paid Groq plan raises the limit for a real launch.
