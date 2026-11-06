"""Load test: many candidates using the site at the same time.

Each simulated candidate signs in once, then keeps browsing like a real person: the job list, a job, the
"do I qualify" check, their profile and their applications, waiting 1 to 3 seconds between clicks. The test
runs in steps (for example 100, 250, 500 and 1000 people at once) and records how long every request took.

It does not call the AI (screening and interviews use Groq, whose free plan is the real limit, see the docs).

Usage (from backend/, against a LOCAL server started with RATE_LIMIT_ENABLED=false and AI_MOCK=true):
    python -m scripts.load_test setup --users 1000          # create test candidates in the database
    python -m scripts.load_test run --url http://localhost:8100 --steps 100,250,500,1000 --seconds 40
    python -m scripts.load_test cleanup                     # remove the test candidates again

Results are written to docs/load-test/ (results.json, summary.md and charts).
"""

import argparse
import asyncio
import json
import random
import statistics
import time
from pathlib import Path

import aiohttp

EMAIL = "loadtest{}@loadtest.example.com"
PASSWORD = "LoadTest123"
OUT = Path(__file__).resolve().parents[2] / "docs" / "load-test"


# --- setup / cleanup -------------------------------------------------------------------------------------
def setup(users: int) -> None:
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.database import SessionLocal
    from app.models import CandidateProfile, User
    from app.models.enums import Role

    db = SessionLocal()
    template = db.scalars(select(CandidateProfile).join(User).where(User.email == "candidate1@demo.com")).first()
    if template is None:
        raise SystemExit("Run scripts/seed.py first: the test copies the demo candidate's profile.")
    password_hash = hash_password(PASSWORD)  # hashing is slow on purpose, so do it once for everyone
    existing = set(db.scalars(select(User.email).where(User.email.like("%@loadtest.example.com"))))
    fields = [
        c.key for c in CandidateProfile.__table__.columns if c.key not in {"id", "user_id", "created_at", "updated_at"}
    ]
    added = 0
    for i in range(users):
        email = EMAIL.format(i)
        if email in existing:
            continue
        user = User(
            email=email,
            full_name=f"Load Test {i}",
            password_hash=password_hash,
            role=Role.CANDIDATE.value,
            email_verified=True,
        )
        user.profile = CandidateProfile(**{f: getattr(template, f) for f in fields})
        db.add(user)
        added += 1
        if added % 200 == 0:
            db.commit()
    db.commit()
    print(f"setup: {added} test candidates added ({len(existing)} already there)")


def cleanup() -> None:
    from sqlalchemy import delete, select

    from app.database import SessionLocal
    from app.models import CandidateProfile, User

    db = SessionLocal()
    ids = list(db.scalars(select(User.id).where(User.email.like("%@loadtest.example.com"))))
    db.execute(delete(CandidateProfile).where(CandidateProfile.user_id.in_(ids)))
    db.execute(delete(User).where(User.id.in_(ids)))
    db.commit()
    print(f"cleanup: removed {len(ids)} test candidates")


# --- the simulated candidate ---------------------------------------------------------------------------
class Recorder:
    def __init__(self) -> None:
        self.rows: list[tuple[str, int, float]] = []  # (what, status, seconds)

    async def call(
        self, client: aiohttp.ClientSession, what: str, method: str, url: str, **kw
    ) -> tuple[int, object] | None:
        start = time.perf_counter()
        try:
            async with client.request(method, url, **kw) as r:
                body = await r.json() if r.status == 200 else await r.read()
                self.rows.append((what, r.status, time.perf_counter() - start))
                return r.status, body
        except (TimeoutError, aiohttp.ClientError):
            self.rows.append((what, 0, time.perf_counter() - start))  # 0 = timed out or connection refused
            return None


async def candidate(i: int, client: aiohttp.ClientSession, rec: Recorder, until: float, start_delay: float) -> None:
    await asyncio.sleep(start_delay)
    r = await rec.call(
        client,
        "sign in",
        "POST",
        "/api/auth/login",
        json={"email": EMAIL.format(i), "password": PASSWORD, "role": "candidate"},
    )
    if r is None or r[0] != 200:
        return
    headers = {"Authorization": f"Bearer {r[1]['access_token']}"}
    job_ids: list[str] = []
    while time.perf_counter() < until:
        page = random.random()
        if not job_ids or page < 0.3:
            r = await rec.call(client, "job list", "GET", "/api/jobs", headers=headers)
            if r is not None and r[0] == 200:
                job_ids = [j["id"] for j in r[1]] or job_ids
        elif page < 0.55:
            await rec.call(client, "open a job", "GET", f"/api/jobs/{random.choice(job_ids)}", headers=headers)
        elif page < 0.7:
            await rec.call(
                client, "qualify check", "GET", f"/api/jobs/{random.choice(job_ids)}/eligibility", headers=headers
            )
        elif page < 0.85:
            await rec.call(client, "my profile", "GET", "/api/profile/me", headers=headers)
        else:
            await rec.call(client, "my applications", "GET", "/api/applications/mine", headers=headers)
        await asyncio.sleep(random.uniform(1, 3))  # reading the page


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))]


async def run_step(url: str, users: int, seconds: int) -> dict:
    rec = Recorder()
    ramp = seconds / 2  # people arrive over the first half of the step, then all of them stay active
    # aiohttp, not httpx: in a first try the httpx client itself topped out near 200 requests per second
    connector = aiohttp.TCPConnector(limit=users + 50)
    async with aiohttp.ClientSession(url, connector=connector, timeout=aiohttp.ClientTimeout(total=30)) as client:
        start = time.perf_counter()
        until = start + seconds
        await asyncio.gather(*(candidate(i, client, rec, until, random.uniform(0, ramp)) for i in range(users)))
        elapsed = time.perf_counter() - start
    ok = [t for _, s, t in rec.rows if 200 <= s < 400]
    errors = [s for _, s, _ in rec.rows if not 200 <= s < 400]
    by_kind = {}
    for what in sorted({w for w, _, _ in rec.rows}):
        ts = [t for w, s, t in rec.rows if w == what and 200 <= s < 400]
        by_kind[what] = {
            "count": sum(1 for w, _, _ in rec.rows if w == what),
            "p50_ms": round(pct(ts, 50) * 1000),
            "p95_ms": round(pct(ts, 95) * 1000),
        }
    return {
        "users": users,
        "seconds": round(elapsed, 1),
        "requests": len(rec.rows),
        "per_second": round(len(rec.rows) / elapsed, 1),
        "errors": len(errors),
        "error_rate": round(100 * len(errors) / max(1, len(rec.rows)), 2),
        "error_codes": {str(c): errors.count(c) for c in sorted(set(errors))},
        "p50_ms": round(pct(ok, 50) * 1000),
        "p95_ms": round(pct(ok, 95) * 1000),
        "p99_ms": round(pct(ok, 99) * 1000),
        "mean_ms": round(statistics.mean(ok) * 1000) if ok else 0,
        "by_request": by_kind,
    }


def charts(results: list[dict], title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    users = [r["users"] for r in results]
    labels = [str(u) for u in users]
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

    fig, ax = plt.subplots(figsize=(7, 4))
    for key, label, color in (
        ("p50_ms", "Median", "#4f46e5"),
        ("p95_ms", "95th percentile", "#d97706"),
        ("p99_ms", "99th percentile", "#e11d48"),
    ):
        ax.plot(labels, [r[key] for r in results], marker="o", label=label, color=color, linewidth=2)
    ax.set_xlabel("Candidates using the site at the same time")
    ax.set_ylabel("Response time (ms)")
    ax.set_title(f"Response time as users grow\n{title}", fontsize=11)
    ax.grid(axis="y", color="#e2e8f0")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "response-time.png", dpi=160)
    plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(7, 4))
    ax1.bar(labels, [r["per_second"] for r in results], color="#4f46e5", width=0.5, label="Requests per second")
    ax1.set_xlabel("Candidates using the site at the same time")
    ax1.set_ylabel("Requests per second")
    ax2 = ax1.twinx()
    ax2.plot(labels, [r["error_rate"] for r in results], color="#e11d48", marker="o", linewidth=2, label="Errors (%)")
    ax2.set_ylabel("Failed requests (%)")
    ax2.set_ylim(0, max(5, max(r["error_rate"] for r in results) * 1.3))
    ax2.spines["top"].set_visible(False)
    ax1.set_title(f"Throughput and errors\n{title}", fontsize=11)
    fig.legend(loc="upper left", bbox_to_anchor=(0.12, 0.88), frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "throughput-errors.png", dpi=160)
    plt.close(fig)


def summary(results: list[dict], title: str) -> str:
    lines = [
        f"# Load test results\n\n{title}\n",
        "| Users at once | Requests | Per second | Median | 95% | 99% | Failed |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r['users']} | {r['requests']} | {r['per_second']} | {r['p50_ms']} ms | {r['p95_ms']} ms | "
            f"{r['p99_ms']} ms | {r['error_rate']}% |"
        )
    lines.append("\n## Per request type at the largest step\n")
    lines.append("| Request | Count | Median | 95% |\n|---|---:|---:|---:|")
    for what, v in results[-1]["by_request"].items():
        lines.append(f"| {what} | {v['count']} | {v['p50_ms']} ms | {v['p95_ms']} ms |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup")
    s.add_argument("--users", type=int, default=1000)
    sub.add_parser("cleanup")
    r = sub.add_parser("run")
    r.add_argument("--url", default="http://localhost:8100")
    r.add_argument("--steps", default="100,250,500")
    r.add_argument("--seconds", type=int, default=40)
    r.add_argument("--title", default="Local test: FastAPI with 4 workers and PostgreSQL on one 4-core machine")
    args = ap.parse_args()
    if args.cmd == "setup":
        setup(args.users)
    elif args.cmd == "cleanup":
        cleanup()
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        results = []
        for users in [int(x) for x in args.steps.split(",")]:
            print(f"step: {users} users for {args.seconds}s ...", flush=True)
            res = asyncio.run(run_step(args.url, users, args.seconds))
            print(
                f"  {res['requests']} requests, {res['per_second']}/s, median {res['p50_ms']} ms, "
                f"p95 {res['p95_ms']} ms, failed {res['error_rate']}% {res['error_codes']}",
                flush=True,
            )
            results.append(res)
            time.sleep(3)
        (OUT / "results.json").write_text(json.dumps({"title": args.title, "steps": results}, indent=2))
        (OUT / "summary.md").write_text(summary(results, args.title))
        charts(results, args.title)
        print(f"written to {OUT}")


if __name__ == "__main__":
    main()
