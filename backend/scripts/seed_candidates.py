"""Demo CANDIDATES only (no recruiter, no jobs). Run from backend/:  python -m scripts.seed_candidates

Creates 8 candidate accounts with a complete profile (photo, phone, city, summary) and a resume PDF, so they can
apply to the jobs you post straight away. All use the password Demo1234. Accounts that already exist are skipped.
    python -m scripts.seed_candidates --reset    # delete these 8 accounts (and their applications) first
All names and details are invented.
"""

import argparse

from sqlalchemy import delete, select

from app import database
from app.core.security import hash_password
from app.models import Application, CandidateProfile, User
from app.services.storage import get_storage
from sample_resumes.generate import resume_pdf
from scripts.seed import avatar_jpeg

PASSWORD = "Demo1234"

CANDIDATES = [
    {
        "email": "ali.hassan@demo.com",
        "name": "Ali Hassan",
        "city": "Lahore",
        "phone": "+92 301 4567812",
        "headline": "Python backend developer",
        "about": "Backend developer who builds REST APIs with FastAPI and Django. Looking for a backend role.",
        "title": "Python Backend Developer",
        "sections": {
            "Summary": "Backend developer with 2 years of experience building REST APIs in Python, with PostgreSQL "
            "databases and Docker deployments.",
            "Skills": "Python, FastAPI, Django, PostgreSQL, SQL, Git, Docker, REST APIs, pytest, Linux",
            "Experience": [
                "Backend Developer, Systems Limited, Lahore (2023 - present, 2 years): FastAPI services for a "
                "banking client, PostgreSQL schema design, Docker images and CI pipelines.",
            ],
            "Projects": ["Online pharmacy API with FastAPI, PostgreSQL and JWT login."],
            "Education": "BS Computer Science, University of the Punjab, Lahore, 2022. CGPA 3.45/4.0",
        },
    },
    {
        "email": "fatima.zahra@demo.com",
        "name": "Fatima Zahra",
        "city": "Karachi",
        "phone": "+92 321 2345678",
        "headline": "Frontend developer (React)",
        "about": "Frontend developer who enjoys clean, accessible interfaces in React and TypeScript.",
        "title": "Frontend React Developer",
        "sections": {
            "Summary": "Frontend developer with 3 years of experience building responsive web apps with React, "
            "TypeScript and Tailwind CSS.",
            "Skills": "React, TypeScript, JavaScript, HTML, CSS, Tailwind CSS, Redux, REST APIs, Git, Jest",
            "Experience": [
                "Frontend Developer, 10Pearls, Karachi (2022 - present, 3 years): built React dashboards, "
                "reusable component libraries and wrote Jest tests.",
            ],
            "Projects": ["Food delivery web app in React and TypeScript with live order tracking."],
            "Education": "BS Software Engineering, NED University of Engineering and Technology, 2021. CGPA 3.6/4.0",
        },
    },
    {
        "email": "hassan.raza@demo.com",
        "name": "Hassan Raza",
        "city": "Islamabad",
        "phone": "+92 333 5123456",
        "headline": "Full stack developer",
        "about": "Full stack developer with Python and React. I like owning features end to end.",
        "title": "Full Stack Developer",
        "sections": {
            "Summary": "Full stack developer with 4 years of experience in Python (Django, FastAPI) and React.",
            "Skills": "Python, Django, FastAPI, React, JavaScript, PostgreSQL, SQL, Docker, Git, AWS, Redis",
            "Experience": [
                "Software Engineer, NetSol Technologies (2021 - present, 4 years): Django and FastAPI services, "
                "React front ends, AWS deployments with Docker.",
            ],
            "Projects": ["School management system with Django REST Framework and React."],
            "Education": "BS Computer Science, COMSATS University Islamabad, 2020. CGPA 3.2/4.0",
            "Certifications": "AWS Certified Developer Associate (2023)",
        },
    },
    {
        "email": "ayesha.siddiqui@demo.com",
        "name": "Ayesha Siddiqui",
        "city": "Rawalpindi",
        "phone": "+92 345 6789012",
        "headline": "Fresh graduate, data and Python",
        "about": "Fresh Computer Science graduate. Final year project on data analysis with Python.",
        "title": "Junior Data Analyst",
        "sections": {
            "Summary": "Fresh graduate with strong Python and SQL skills from university projects and a 3 month "
            "internship.",
            "Skills": "Python, SQL, pandas, Excel, Power BI, Git, Statistics",
            "Experience": [
                "Data Intern, Jazz, Islamabad (3 months, 2024): cleaned sales data with pandas and built Power BI "
                "reports.",
            ],
            "Projects": ["Final year project: predicting student results with Python and scikit-learn."],
            "Education": "BS Computer Science, Fatima Jinnah Women University, 2024. CGPA 3.7/4.0",
        },
    },
    {
        "email": "usman.ghani@demo.com",
        "name": "Usman Ghani",
        "city": "Faisalabad",
        "phone": "+92 300 7654321",
        "headline": "IT support technician",
        "about": "IT support technician. I fix Windows, printer and network problems and keep users happy.",
        "title": "IT Support Technician",
        "sections": {
            "Summary": "IT support technician with 2 years of experience looking after office computers, accounts "
            "and networks.",
            "Skills": "Windows, Networking, Troubleshooting, Excel, Active Directory, Printers, Wi-Fi, Office 365",
            "Experience": [
                "IT Support Officer, Interloop Limited, Faisalabad (2023 - present, 2 years): set up laptops, "
                "managed user accounts, fixed printer and Wi-Fi issues.",
            ],
            "Education": "Diploma of Associate Engineering (DAE) in Computer Information Technology, 2022",
        },
    },
    {
        "email": "maryam.iqbal@demo.com",
        "name": "Maryam Iqbal",
        "city": "Multan",
        "phone": "+92 312 3456789",
        "headline": "Junior web developer",
        "about": "Web developer working with JavaScript and PHP. Learning React.",
        "title": "Junior Web Developer",
        "sections": {
            "Summary": "Web developer with 1 year of experience building websites with JavaScript, PHP and MySQL.",
            "Skills": "JavaScript, HTML, CSS, PHP, MySQL, Bootstrap, Git, WordPress",
            "Experience": [
                "Web Developer, Techlogix (2024 - present, 1 year): business websites in PHP and WordPress, "
                "small JavaScript features.",
            ],
            "Education": "BS Information Technology, Bahauddin Zakariya University, Multan, 2023. CGPA 2.8/4.0",
        },
    },
    {
        "email": "bilal.ahmed@demo.com",
        "name": "Bilal Ahmed",
        "city": "Peshawar",
        "phone": "+92 334 1122334",
        "headline": "Software engineer",
        "about": "Software engineer with a Master's degree. Backend and cloud.",
        "title": "Software Engineer",
        "sections": {
            "Summary": "Software engineer with 5 years of experience in backend development with Python and Go, "
            "and cloud deployments.",
            "Skills": "Python, Go, FastAPI, PostgreSQL, SQL, Docker, Kubernetes, Git, AWS, Redis, Linux",
            "Experience": [
                "Senior Software Engineer, Arbisoft (2022 - present, 3 years): Python and Go microservices, "
                "Kubernetes, PostgreSQL tuning.",
                "Software Engineer, Ufone (2020 - 2022, 2 years): internal APIs in Python.",
            ],
            "Education": "MS Computer Science, FAST NUCES Peshawar, 2020. CGPA 3.5/4.0",
        },
    },
    {
        "email": "hira.shah@demo.com",
        "name": "Hira Shah",
        "city": "Hyderabad",
        "phone": "+92 302 9988776",
        "headline": "Marketing executive",
        "about": "Marketing executive moving into digital marketing.",
        "title": "Marketing Executive",
        "sections": {
            "Summary": "Marketing professional with 3 years of experience in social media campaigns and events.",
            "Skills": "Marketing, Social media, Content writing, Canva, Excel, Communication",
            "Experience": [
                "Marketing Executive, Engro Foods (2022 - present, 3 years): ran social media campaigns and "
                "managed event budgets.",
            ],
            "Education": "BBA Marketing, University of Sindh, 2021. CGPA 3.1/4.0",
        },
    },
]


def _reset(db) -> None:
    emails = [c["email"] for c in CANDIDATES]
    ids = list(db.scalars(select(User.id).where(User.email.in_(emails))))
    if not ids:
        return
    for a in db.scalars(select(Application).where(Application.candidate_id.in_(ids))):
        db.delete(a)
    db.flush()
    db.execute(delete(User).where(User.id.in_(ids)))
    db.commit()
    print(f"Removed {len(ids)} demo candidates")


def seed_candidates(reset: bool = False) -> None:
    db = database.SessionLocal()
    storage = get_storage()
    try:
        if reset:
            _reset(db)
        pw = hash_password(PASSWORD)
        made = 0
        for c in CANDIDATES:
            if db.scalar(select(User).where(User.email == c["email"])):
                continue
            user = User(full_name=c["name"], email=c["email"], password_hash=pw, role="candidate", email_verified=True)
            db.add(user)
            db.flush()
            photo_key = f"profiles/{user.id}/photo-demo.jpg"
            storage.save(photo_key, avatar_jpeg(c["name"]), "image/jpeg")
            pdf = resume_pdf(
                {
                    "name": c["name"],
                    "title": c["title"],
                    "contact": f"{c['email'].replace('@demo.com', '@example.com')} · {c['phone']} · "
                    f"{c['city']}, Pakistan",
                    "sections": c["sections"],
                }
            )
            resume_key = f"profiles/{user.id}/resume-demo.pdf"
            storage.save(resume_key, pdf, "application/pdf")
            filename = c["name"].lower().replace(" ", "_") + "_resume.pdf"
            db.add(
                CandidateProfile(
                    user_id=user.id,
                    headline=c["headline"],
                    phone=c["phone"],
                    city=c["city"],
                    about=c["about"],
                    photo_key=photo_key,
                    resume_key=resume_key,
                    resume_filename=filename,
                )
            )
            db.commit()
            made += 1
        print(f"Created {made} demo candidates (password {PASSWORD}):")
        for c in CANDIDATES:
            print(f"  {c['email']:<28} {c['name']:<16} {c['title']}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create demo candidate accounts")
    parser.add_argument("--reset", action="store_true", help="delete these demo candidates first")
    seed_candidates(parser.parse_args().reset)
