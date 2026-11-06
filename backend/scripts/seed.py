"""Demo data. Run from backend/:  python -m scripts.seed      (add --reset to wipe old demo data first)

Creates 1 recruiter, 6 candidates, 2 jobs, applications with the sample resumes (screened by the AI,
mock or real depending on env), and 3 completed interviews so the dashboard is full immediately.
All accounts use the password Demo1234.
"""

import argparse
import logging
import sys
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select

from app import database
from app.ai import client as ai
from app.ai import prompts
from app.ai.mock import mock_answer_eval
from app.ai.schemas import AnswerEvaluation
from app.core.security import hash_password
from app.models import AIAuditLog, Application, CandidateProfile, InterviewResponse, Job, Resume, User
from app.models.enums import Decision, SessionStatus, Stage
from app.schemas.form import DEFAULT_FORM
from app.services import evaluation
from app.services import interview as interview_svc
from app.services import profile as profile_svc
from app.services import resume as resume_svc
from app.services.application import set_stage
from app.services.storage import get_storage
from sample_resumes.generate import OUT_DIR, generate

log = logging.getLogger("seed")
PASSWORD = "Demo1234"

# Each demo candidate's profile (matches their resume). Photos are generated placeholders with initials.
PROFILES = [
    dict(
        headline="Backend developer (Python, FastAPI)",
        phone="+92 300 1112233",
        city="Lahore",
        highest_degree="bachelors",
        field_of_study="Computer Science",
        institute="Lahore Garrison University",
        cgpa=3.6,
        graduation_year=2021,
        experience_years=3,
        experience=[
            {
                "title": "Software Engineer",
                "company": "TechCorp",
                "years": 3,
                "description": "FastAPI services, PostgreSQL, Docker",
            }
        ],
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "Git", "Redis"],
        linkedin_url="https://www.linkedin.com/in/ahmed-raza-demo",
        github_url="https://github.com/ahmed-raza-demo",
    ),
    dict(
        headline="Software engineer",
        phone="+92 321 4445566",
        city="Karachi",
        highest_degree="bachelors",
        field_of_study="Software Engineering",
        institute="COMSATS University",
        cgpa=3.1,
        graduation_year=2022,
        experience_years=2,
        experience=[{"title": "Junior Developer", "company": "WebWorks", "years": 2, "description": None}],
        skills=["Python", "Django", "JavaScript", "React", "MySQL"],
        linkedin_url="https://www.linkedin.com/in/usman-tariq-demo",
    ),
    dict(
        headline="IT support technician",
        phone="+92 333 7778899",
        city="Rawalpindi",
        highest_degree="diploma",
        field_of_study="Computer Information Technology",
        institute="Govt. College of Technology",
        cgpa=None,
        graduation_year=2023,
        experience_years=1,
        experience=[{"title": "IT Support", "company": "City Computers", "years": 1, "description": None}],
        skills=["Windows", "Networking", "HTML", "Excel"],
        github_url="https://github.com/bilal-hussain-demo",
    ),
    dict(
        headline="Marketing executive",
        phone="+92 345 1212121",
        city="Islamabad",
        highest_degree="bachelors",
        field_of_study="Business Administration",
        institute="University of the Punjab",
        cgpa=3.0,
        graduation_year=2020,
        experience_years=4,
        experience=[{"title": "Marketing Executive", "company": "BrandCo", "years": 4, "description": None}],
        skills=["Marketing", "Photoshop", "Excel", "Communication"],
        linkedin_url="https://www.linkedin.com/in/sana-malik-demo",
    ),
    dict(
        headline="Fresh computer science graduate",
        phone="+92 301 9090909",
        city="Lahore",
        highest_degree="bachelors",
        field_of_study="Computer Science",
        institute="Lahore Garrison University",
        cgpa=3.8,
        graduation_year=2025,
        experience_years=0.5,
        experience=[{"title": "Intern", "company": "SoftLab", "years": 0.5, "description": "React and Python"}],
        skills=["Python", "React", "JavaScript", "SQL", "Git"],
        linkedin_url="https://www.linkedin.com/in/ayesha-noor-demo",
        github_url="https://github.com/ayesha-noor-demo",
    ),
    dict(
        headline="Python developer",
        phone="+92 302 5656565",
        city="Faisalabad",
        highest_degree="bachelors",
        field_of_study="Computer Science",
        institute="University of Agriculture",
        cgpa=3.2,
        graduation_year=2023,
        experience_years=2,
        skills=["Python", "Flask", "SQL"],
        linkedin_url="https://www.linkedin.com/in/hamza-ali-demo",
    ),
]

CANDIDATES = [
    ("candidate1@demo.com", "Ahmed Raza", "1_strong_ahmed_raza.pdf"),
    ("candidate2@demo.com", "Usman Tariq", "2_medium_usman_tariq.pdf"),
    ("candidate3@demo.com", "Bilal Hussain", "3_weak_bilal_hussain.pdf"),
    ("candidate4@demo.com", "Sana Malik", "4_unrelated_sana_malik.pdf"),
    ("candidate5@demo.com", "Ayesha Noor", "5_fresh_graduate_ayesha_noor.pdf"),
    ("candidate6@demo.com", "Hamza Ali", "6_scanned_image_only_hamza_ali.pdf"),
]

JOBS = [
    {
        "title": "Junior Python Backend Developer",
        "description": "We are looking for a Junior Python Backend Developer to build and maintain REST APIs for our "
        "recruitment platform. You will design endpoints with FastAPI, model data in PostgreSQL, write "
        "tests, and ship services in Docker containers. You will work with senior engineers in code "
        "reviews and help improve reliability and performance.\n\nResponsibilities:\n- Build REST APIs "
        "with FastAPI\n- Write SQL queries and migrations\n- Containerise services with Docker\n- Use Git "
        "and pull requests daily",
        "required_skills": ["Python", "FastAPI", "SQL", "Git", "Docker"],
        "min_experience_years": 0,
        "education_level": "bachelors",
        "min_cgpa": 2.5,
        "screening_threshold": 40,
        "num_questions": 6,
        "seconds_per_question": 120,
    },
    {
        "title": "Frontend React Developer",
        "description": "Join our product team as a Frontend React Developer. You will build responsive, accessible "
        "user interfaces in React and TypeScript, integrate REST APIs, and collaborate closely with "
        "designers.\n\nResponsibilities:\n- Build reusable React components\n- Write clean TypeScript\n"
        "- Style with modern CSS / Tailwind\n- Review code and use Git workflows",
        "required_skills": ["React", "TypeScript", "JavaScript", "HTML", "CSS", "Git"],
        "min_experience_years": 0,
        "education_level": "bachelors",
        "min_cgpa": 3.0,
        "screening_threshold": 45,
        "num_questions": 5,
        "seconds_per_question": 90,
    },
    {
        "title": "IT Support Associate",
        "description": "Help our office staff with computers, accounts and the network. You will set up laptops, "
        "fix Windows and printer problems, look after Wi-Fi and keep simple records in Excel. Good for "
        "diploma holders who enjoy solving everyday technical problems.",
        "required_skills": ["Windows", "Networking", "Excel", "Troubleshooting"],
        "min_experience_years": 0,
        "education_level": "diploma",
        "screening_threshold": 30,
        "num_questions": 5,
        "seconds_per_question": 90,
    },
]

# Bilal has a Diploma, so the two Bachelor's jobs stopped him before he could apply (shown as "stopped by
# requirements" on those jobs). He applied to the IT Support job instead.
BLOCKED = {0: 1, 1: 1}  # job index -> candidates stopped by the minimum requirements

# (candidate index, job index). Ayesha (fresh graduate) is left INVITED for the React job, for a live demo.
APPLICATIONS = [(0, 0), (1, 0), (3, 0), (4, 0), (5, 0), (1, 1), (4, 1), (2, 2)]
COMPLETE_INTERVIEWS = {0: "strong", 1: "medium", 4: "mixed"}  # candidate index -> answer quality (job 0)

ANSWERS = {
    "strong": "In my current role I built several services with {focus}. For example, I designed the "
    "endpoints, added validation with Pydantic, wrote pytest tests for each route and measured "
    "performance before optimising. We fixed a slow query by adding an index and caching results "
    "in Redis, which cut response time a lot. I learned to keep functions small and to document "
    "decisions because the whole team maintains the code.",
    "medium": "I have used {focus} in my projects at work. Mostly I followed the existing structure in "
    "the project and added new features when the client asked. I think it is important to test "
    "things before deploying, so I usually check manually and sometimes write tests.",
    "mixed": "In my final year project I used {focus} with a small team. I built the main part and "
    "learned a lot from the documentation, although I am still improving on the advanced topics.",
}

BEHAVIOURAL = {
    "strong": "In my last project a teammate wanted to rewrite our API in a new framework two weeks before a "
    "release. I disagreed, but first I listened to his reasons. Then I suggested we measure the actual "
    "problem. We found one slow endpoint, fixed it with an index, and planned the bigger change for the "
    "next sprint. We shipped on time and he led the later migration, which I learned a lot from.",
    "medium": "Once a teammate and I disagreed about how to name things in our database. We talked about it "
    "and asked our team lead, and then we followed the team lead's suggestion. It worked out fine.",
    "mixed": "In my final year project my group member and I disagreed on the design. We discussed it and "
    "chose his idea because it was faster to build, and we finished the project on time.",
}


AVATAR_COLOURS = [(10, 10, 10), (38, 38, 38), (64, 64, 64), (82, 82, 82), (23, 23, 23), (115, 115, 115)]


def avatar_jpeg(name: str) -> bytes:
    """A plain placeholder profile picture with the person's initials (demo accounts only)."""
    import io

    from PIL import Image, ImageDraw, ImageFont

    colour = AVATAR_COLOURS[sum(map(ord, name)) % len(AVATAR_COLOURS)]
    img = Image.new("RGB", (320, 320), colour)
    draw = ImageDraw.Draw(img)
    initials = "".join(p[0] for p in name.split()[:2]).upper()
    font = None
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):  # Linux, Windows, macOS
        try:
            font = ImageFont.truetype(name, 120)
            break
        except OSError:
            continue
    if font is None:
        try:
            font = ImageFont.load_default(size=120)
        except TypeError:  # Pillow older than 10.1
            font = ImageFont.load_default()
    draw.text((160, 160), initials, fill=(255, 255, 255), font=font, anchor="mm")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def _integrity_demo(session) -> None:
    """Usman's interview: a tab switch, looking away and a phone on camera, spread over the interview."""
    start = session.started_at or datetime.now(UTC)
    plan = [
        (40, "tab_hidden", 1, True),
        (95, "looking_away", 2, False),
        (130, "eyes_away", 2, False),
        (210, "phone_detected", 3, True),
        (300, "looking_away", 4, False),
    ]
    session.integrity_events = [
        {
            "type": t,
            "at": (start + timedelta(seconds=s)).isoformat(),
            "question_index": q,
            "detail": None,
            "value": None,
            "strike": strike,
        }
        for s, t, q, strike in plan
    ] + [
        {
            "type": "attention",
            "at": (start + timedelta(seconds=60 * (i + 1))).isoformat(),
            "question_index": i,
            "detail": None,
            "value": v,
            "strike": False,
        }
        for i, v in enumerate([92, 71, 64, 58, 80, 88])
    ]


def _reset(db) -> None:
    demo_users = list(db.scalars(select(User).where(User.email.like("%@demo.com"))))
    ids = [u.id for u in demo_users]
    if not ids:
        return
    log.info("Removing %d existing demo users and their data", len(ids))
    for job in db.scalars(select(Job).where(Job.recruiter_id.in_(ids))):
        db.delete(job)
    for app_ in db.scalars(select(Application).where(Application.candidate_id.in_(ids))):
        db.delete(app_)
    db.flush()
    db.execute(delete(User).where(User.id.in_(ids)))
    db.commit()


def _complete_interview(db, application: Application, quality: str) -> None:
    session = application.interview
    job = application.job
    interview_svc.start(db, session)
    for q in session.questions:
        focus = q.get("focus") or "this technology"
        if focus.lower().startswith(("behaviour", "behavior", "motivation")):
            transcript = BEHAVIOURAL[quality]
        else:
            transcript = ANSWERS[quality].format(focus=focus.removeprefix("Resume: "))
        if quality == "mixed" and q["index"] % 3 == 2:
            transcript = "Sorry, I am not sure about this one. I would need to look it up."
        result = ai.chat_json(
            prompts.ANSWER_EVAL_SYSTEM,
            prompts.answer_eval_user(job, q, transcript),
            AnswerEvaluation,
            db=db,
            kind="answer_eval",
            application_id=application.id,
            mock=lambda q=q, t=transcript: mock_answer_eval(job, q, t),
        )
        db.add(
            InterviewResponse(
                session_id=session.id,
                question_index=q["index"],
                audio_key=None,
                transcript=transcript,
                accuracy=result.accuracy,
                relevance=result.relevance,
                clarity=result.clarity,
                score=evaluation.answer_score(result.accuracy, result.relevance, result.clarity),
                feedback=result.feedback,
            )
        )
        session.current_index = q["index"] + 1
    db.flush()
    db.refresh(session)
    ev = application.evaluation
    ev.interview_score = evaluation.interview_score([r.score for r in session.responses])
    ev.composite_score = evaluation.composite_score(ev.resume_total, ev.interview_score)
    ev.incomplete = False
    session.status = SessionStatus.COMPLETED.value
    session.completed_at = datetime.now(UTC)
    set_stage(application, Stage.EVALUATED)
    db.commit()


def seed(reset: bool = False) -> None:
    generate()
    db = database.SessionLocal()
    try:
        if reset:
            _reset(db)
        if db.scalar(select(User).where(User.email == "recruiter@demo.com")):
            log.error("Demo data already exists. Run with --reset to recreate it.")
            sys.exit(1)

        pw = hash_password(PASSWORD)
        recruiter = User(
            full_name="Demo Recruiter (TechHire)", email="recruiter@demo.com", password_hash=pw, role="recruiter"
        )
        candidates = [
            User(full_name=n, email=e, password_hash=pw, role="candidate", email_verified=True)
            for e, n, _ in CANDIDATES
        ]
        recruiter.email_verified = True
        db.add_all([recruiter, *candidates])
        db.flush()
        storage = get_storage()
        for user, data, (_, _, resume_file) in zip(candidates, PROFILES, CANDIDATES, strict=True):
            photo_key = f"profiles/{user.id}/photo-demo.jpg"
            storage.save(photo_key, avatar_jpeg(user.full_name), "image/jpeg")
            resume_key = f"profiles/{user.id}/resume-demo.pdf"
            storage.save(resume_key, (OUT_DIR / resume_file).read_bytes(), "application/pdf")
            user.profile = CandidateProfile(
                user_id=user.id, photo_key=photo_key, resume_key=resume_key, resume_filename=resume_file, **data
            )
        db.flush()
        jobs = [
            Job(
                recruiter_id=recruiter.id,
                deadline=date.today() + timedelta(days=30),
                application_form=DEFAULT_FORM,
                blocked_applications=BLOCKED.get(i, 0),
                **j,
            )
            for i, j in enumerate(JOBS)
        ]
        db.add_all(jobs)
        db.commit()

        created: dict[tuple[int, int], Application] = {}
        for ci, ji in APPLICATIONS:
            filename = CANDIDATES[ci][2]
            app_ = Application(
                job_id=jobs[ji].id,
                candidate_id=candidates[ci].id,
                form_answers=[],
                profile_snapshot=profile_svc.snapshot(candidates[ci]),
            )
            db.add(app_)
            db.flush()
            key = f"resumes/{jobs[ji].id}/{app_.id}.pdf"
            storage.save(key, (OUT_DIR / filename).read_bytes(), "application/pdf")
            db.add(Resume(application_id=app_.id, file_key=key, original_filename=filename))
            db.commit()
            log.info("Screening %s -> %s", CANDIDATES[ci][1], jobs[ji].title)
            resume_svc.screen(app_.id)  # same pipeline as a real application (mock or real AI)
            created[(ci, ji)] = app_

        for ci, quality in COMPLETE_INTERVIEWS.items():
            app_ = db.get(Application, created[(ci, 0)].id)
            db.refresh(app_)
            if app_.stage != Stage.INTERVIEW_INVITED:
                log.warning("%s was not invited (stage=%s); skipping seeded interview", CANDIDATES[ci][1], app_.stage)
                continue
            log.info("Seeding completed interview for %s (%s answers)", CANDIDATES[ci][1], quality)
            _complete_interview(db, app_, quality)
            if ci == 1:
                _integrity_demo(app_.interview)
                db.commit()

        first = db.get(Application, created[(0, 0)].id)
        first.recruiter_decision = Decision.SHORTLISTED.value
        first.recruiter_notes = "Excellent FastAPI depth. Invite to on-site technical round."
        db.commit()

        log.info("Done. %d audit rows written so far.", db.query(AIAuditLog).count())
        print("\nDemo accounts (password Demo1234):")
        print("  recruiter@demo.com")
        for e, n, _ in CANDIDATES:
            print(f"  {e}  ({n})")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Seed demo data")
    parser.add_argument("--reset", action="store_true", help="delete existing @demo.com data first")
    parser.add_argument(
        "--real-ai",
        action="store_true",
        help="screen the demo candidates with the real AI (slow on Groq's free tier; uses your token quota)",
    )
    args = parser.parse_args()
    if not args.real_ai:
        # Demo data is always built with the built-in simulated AI: fast, the same every time, and it does not use up
        # the Groq free-tier token limit. Real applications made in the app still use the real AI.
        from app.config import settings

        settings.AI_MOCK = True
    logging.getLogger("httpx").setLevel(logging.WARNING)
    seed(args.reset)
