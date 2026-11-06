"""CSV and PDF exports of a job's ranked candidates (recruiter only)."""

import csv
import io
from datetime import UTC, datetime

from app.models import Job

CSV_HEADER = [
    "Rank",
    "Name",
    "Email",
    "Stage",
    "Decision",
    "Skills /40",
    "Experience /20",
    "Education /10",
    "Resume /70",
    "Interview /30",
    "Composite /100",
    "Incomplete",
    "Manual review",
    "Applied at",
    "Interview integrity",
]
INTEGRITY_TEXT = {"clean": "No issues", "warning": "Check", "high": "Suspicious", None: ""}


def _fmt(v) -> str:
    return "" if v is None else (f"{v:g}" if isinstance(v, float) else str(v))


def _values(r: dict) -> list[str]:
    return [
        str(r["rank"]),
        r["full_name"],
        r["email"],
        r["stage"],
        r["decision"],
        _fmt(r["skill_score"]),
        _fmt(r["experience_score"]),
        _fmt(r["education_score"]),
        _fmt(r["resume_total"]),
        _fmt(r["interview_score"]),
        _fmt(r["composite_score"]),
        "yes" if r["incomplete"] else "no",
        "yes" if r["needs_manual_review"] else "no",
        r["applied_at"].strftime("%Y-%m-%d"),
        INTEGRITY_TEXT.get(r.get("integrity_level"), ""),
    ]


def to_csv(job: Job, rows: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([f"Job: {job.title}"])
    form = job.application_form or []
    writer.writerow(CSV_HEADER + [q["label"] for q in form])
    for r in rows:
        answers = {a["id"]: a["answer"] for a in r.get("form_answers") or []}
        writer.writerow(_values(r) + [answers.get(q["id"], "") for q in form])
    return buf.getvalue().encode("utf-8-sig")  # BOM so Excel opens UTF-8 correctly


def to_pdf(job: Job, rows: list[dict], only_shortlisted: bool) -> bytes:
    # reportlab is imported here so it does not slow down starting the API.
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title=f"Candidates - {job.title}",
    )
    styles = getSampleStyleSheet()
    small = styles["BodyText"].clone("small", fontSize=8, leading=10)
    story = [
        Paragraph(f"Candidate report: {job.title}", styles["Title"]),
        Paragraph(
            f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC · "
            f"{'Shortlisted candidates only' if only_shortlisted else 'All candidates'} · "
            f"Required skills: {', '.join(job.required_skills)}",
            small,
        ),
        Spacer(1, 10),
    ]
    header = ["#", "Name", "Email", "Stage", "Decision", "Skill", "Exp", "Edu", "Resume", "Interview", "Composite"]
    data = [header] + [[Paragraph(c, small) if i in (1, 2) else c for i, c in enumerate(_values(r)[:11])] for r in rows]
    if not rows:
        data.append(["", "No candidates", "", "", "", "", "", "", "", "", ""])
    table = Table(data, repeatRows=1, colWidths=[1 * cm, 4.5 * cm, 5.5 * cm, 3.5 * cm, 2.5 * cm] + [1.8 * cm] * 6)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d1d5db")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f7")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buf.getvalue()
