"""Generate 6 realistic FAKE resumes as PDFs (ReportLab). Run: python -m sample_resumes.generate

1 strong match, 2 medium, 3 weak, 4 unrelated field, 5 fresh graduate, 6 image-only (no text -> manual review).
All names and details are invented.
"""

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT_DIR = Path(__file__).parent

RESUMES = {
    "1_strong_ahmed_raza.pdf": {
        "name": "Ahmed Raza",
        "title": "Python Backend Developer",
        "contact": "ahmed.raza@example.com · Lahore, Pakistan · github.com/ahmedraza-dev",
        "sections": {
            "Summary": "Backend developer with 3 years of experience designing and shipping REST APIs in Python. "
            "Comfortable owning a service end to end: data modelling, API design, testing, Docker "
            "deployment and monitoring.",
            "Skills": "Python, FastAPI, Django, PostgreSQL, SQL, SQLAlchemy, Git, Docker, Redis, Celery, pytest, "
            "Linux, GitHub Actions, AWS",
            "Experience": [
                "Software Engineer, CloudNova Solutions (2022 - present, 2 years): built 6 FastAPI microservices "
                "for an e-commerce platform serving 40k daily users; cut p95 latency from 900ms to 180ms with "
                "query optimisation and Redis caching; introduced pytest suites raising coverage to 85%.",
                "Junior Developer, Softech Lahore (2021 - 2022, 1 year): Django REST APIs, PostgreSQL schema "
                "design and migrations, Dockerised legacy services.",
            ],
            "Projects": [
                "Clinic appointment API (FastAPI, PostgreSQL, Docker) with JWT auth and role-based access.",
                "Open-source contributor to a SQLAlchemy utilities library (merged 5 PRs).",
            ],
            "Education": "Bachelor of Science in Computer Science (BSCS), Lahore Garrison University, 2021. CGPA 3.6",
            "Certifications": "AWS Certified Cloud Practitioner (2023)",
        },
    },
    "2_medium_usman_tariq.pdf": {
        "name": "Usman Tariq",
        "title": "Junior Web Developer",
        "contact": "usman.tariq@example.com · Islamabad, Pakistan",
        "sections": {
            "Summary": "Web developer with 2 years of experience building small business websites and internal "
            "tools with Python Flask and SQL databases.",
            "Skills": "Python, Flask, SQL, MySQL, Git, HTML, CSS, JavaScript, Bootstrap",
            "Experience": [
                "Web Developer, PixelCraft Studio (2022 - 2024, 2 years): built Flask applications for clients, "
                "wrote SQL reports, maintained Git repositories and deployed apps on shared hosting.",
            ],
            "Projects": [
                "Inventory tracker for a local shop (Flask, MySQL).",
                "Personal blog with a Markdown editor.",
            ],
            "Education": "Bachelor of Science in Software Engineering, COMSATS University, 2022",
        },
    },
    "3_weak_bilal_hussain.pdf": {
        "name": "Bilal Hussain",
        "title": "IT Support Assistant",
        "contact": "bilal.hussain@example.com · Karachi, Pakistan",
        "sections": {
            "Summary": "IT support assistant with some exposure to web pages and version control, looking to move "
            "into software development.",
            "Skills": "HTML, CSS, Git, Windows administration, networking basics, MS Office",
            "Experience": [
                "IT Support Assistant, Metro Traders (6 months): set up office PCs, printers and Wi-Fi; "
                "updated the company web page using HTML and CSS.",
            ],
            "Education": "Diploma of Associate Engineering (DAE) in Computer Information Technology, 2023",
        },
    },
    "4_unrelated_sana_malik.pdf": {
        "name": "Sana Malik",
        "title": "Marketing Executive",
        "contact": "sana.malik@example.com · Lahore, Pakistan",
        "sections": {
            "Summary": "Marketing professional with 4 years of experience planning social media campaigns, "
            "managing budgets and growing brand awareness for consumer brands.",
            "Skills": "Marketing, Social media strategy, Photoshop, Excel, Communication, Sales, Copywriting",
            "Experience": [
                "Marketing Executive, BrandHive (2020 - 2024, 4 years): ran 30+ campaigns, increased Instagram "
                "followers by 120%, managed a PKR 5M annual ad budget.",
            ],
            "Education": "Bachelor of Business Administration (BBA), University of the Punjab, 2020",
        },
    },
    "5_fresh_graduate_ayesha_noor.pdf": {
        "name": "Ayesha Noor",
        "title": "Computer Science Graduate",
        "contact": "ayesha.noor@example.com · Rawalpindi, Pakistan · github.com/ayesha-codes",
        "sections": {
            "Summary": "Fresh Computer Science graduate who enjoys building full-stack web apps. Strong "
            "fundamentals in data structures, databases and modern JavaScript frameworks.",
            "Skills": "Python, FastAPI, SQL, PostgreSQL, Git, React, JavaScript, TypeScript, HTML, CSS, Tailwind",
            "Projects": [
                "Final year project: AI study planner - React + TypeScript frontend, FastAPI backend, "
                "PostgreSQL database, deployed on Vercel and Render.",
                "Hackathon winner (NASTP 2024): real-time bus tracker built with React and Node.js.",
                "Course project: library management system with SQL stored procedures.",
            ],
            "Experience": ["Summer intern, CodeBridge (3 months): built React components and REST API endpoints."],
            "Education": "Bachelor of Science in Computer Science (BSCS), Lahore Garrison University, 2025. CGPA 3.8",
        },
    },
}


def _text_resume(path: Path, data: dict) -> None:
    path.write_bytes(resume_pdf(data))


def resume_pdf(data: dict) -> bytes:
    """A one-page text resume: name, title, contact line, then each section."""
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], alignment=0, fontSize=20, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=styles["Normal"], textColor=colors.HexColor("#4f46e5"), fontSize=11)
    small = ParagraphStyle("small", parent=styles["Normal"], textColor=colors.grey, fontSize=9)
    h2 = ParagraphStyle("h2", parent=styles["Heading3"], textColor=colors.HexColor("#111827"), spaceBefore=10)
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14)
    story = [Paragraph(data["name"], h1), Paragraph(data["title"], sub), Paragraph(data["contact"], small)]
    for heading, content in data["sections"].items():
        story.append(Paragraph(heading.upper(), h2))
        for item in content if isinstance(content, list) else [content]:
            story.append(Paragraph(("• " if isinstance(content, list) else "") + item, body))
            story.append(Spacer(1, 3))
    buf = BytesIO()
    SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        title=f"{data['name']} - Resume",
    ).build(story)
    return buf.getvalue()


def _image_only_resume(path: Path) -> None:
    """Simulates a scanned resume: only shapes, no extractable text."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFillColor(colors.HexColor("#e5e7eb"))
    c.rect(2 * cm, 24 * cm, 8 * cm, 2 * cm, fill=1, stroke=0)
    for i in range(18):
        c.rect(2 * cm, (22 - i) * cm, (12 + (i % 4)) * cm, 0.35 * cm, fill=1, stroke=0)
    c.showPage()
    c.save()
    path.write_bytes(buf.getvalue())


def generate(out_dir: Path = OUT_DIR) -> list[Path]:
    paths = []
    for filename, data in RESUMES.items():
        p = out_dir / filename
        _text_resume(p, data)
        paths.append(p)
    p = out_dir / "6_scanned_image_only_hamza_ali.pdf"
    _image_only_resume(p)
    paths.append(p)
    return paths


if __name__ == "__main__":
    for p in generate():
        print("wrote", p)
