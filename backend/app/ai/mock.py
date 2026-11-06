"""Deterministic fake AI used when AI_MOCK=true (or no API key). Based on simple keyword overlap,
so results are realistic enough for demos and fully repeatable for tests."""

import hashlib
import re

from app.models.enums import EDUCATION_RANK, EducationLevel

SYNONYMS: dict[str, list[str]] = {
    "javascript": ["js", "javascript", "ecmascript"],
    "typescript": ["ts", "typescript"],
    "react": ["react", "reactjs", "react.js"],
    "postgresql": ["postgres", "postgresql", "psql"],
    "sql": ["sql", "mysql", "postgres", "postgresql", "sqlite"],
    "machine learning": ["ml", "machine learning"],
    "docker": ["docker", "containers", "containerization"],
    "git": ["git", "github", "gitlab"],
    "fastapi": ["fastapi"],
    "python": ["python"],
    "node.js": ["node", "nodejs", "node.js"],
    "css": ["css", "tailwind", "tailwindcss", "sass"],
    "html": ["html", "html5"],
    "rest api": ["rest", "rest api", "restful"],
}

VOCAB = [
    "python",
    "fastapi",
    "django",
    "flask",
    "sql",
    "postgresql",
    "mysql",
    "mongodb",
    "git",
    "docker",
    "kubernetes",
    "aws",
    "linux",
    "react",
    "typescript",
    "javascript",
    "html",
    "css",
    "tailwind",
    "node.js",
    "redux",
    "next.js",
    "java",
    "spring",
    "c++",
    "pandas",
    "numpy",
    "machine learning",
    "excel",
    "figma",
    "rest api",
    "graphql",
    "redis",
    "celery",
    "pytest",
    "jest",
    "vite",
    "accounting",
    "marketing",
    "photoshop",
    "communication",
    "sales",
]


def _variants(skill: str) -> list[str]:
    key = skill.lower().strip()
    if key in SYNONYMS:
        return SYNONYMS[key]
    for variants in SYNONYMS.values():  # e.g. "Postgres" -> the postgresql group
        if key in variants:
            return variants
    return [key]


def _contains(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


def _has_skill(text: str, skill: str) -> bool:
    return any(_contains(text, v) for v in _variants(skill))


def _detect_education(text: str) -> tuple[str, str]:
    checks = [
        (EducationLevel.PHD, r"\bph\.?d\b|doctorate"),
        (EducationLevel.MASTERS, r"\bmaster|\bmsc\b|\bmscs\b|\bms in\b|\bm\.sc|\bmba\b"),
        (EducationLevel.BACHELORS, r"\bbachelor|\bbs\b|\bbsc\b|\bbscs\b|\bb\.sc|\bbe\b|\bbtech"),
        (EducationLevel.DIPLOMA, r"diploma|associate"),
        (EducationLevel.HIGH_SCHOOL, r"high school|intermediate|f\.sc|\bfsc\b|a-levels"),
        (EducationLevel.MATRIC, r"matric|o-levels|\bssc\b"),
    ]
    for level, pattern in checks:
        if re.search(pattern, text):
            return level.value, level.value.replace("_", " ").title()
    return EducationLevel.NONE.value, "Not specified"


def _years(text: str) -> float:
    years = [float(y) for y in re.findall(r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)\b", text)]
    months = [float(m) / 12 for m in re.findall(r"(\d+)\s*months?\b", text)]
    return round(max(years) if years else sum(months), 1)


def _detect_cgpa(text: str) -> float | None:
    m = re.search(r"c?gpa[:\s]*([0-4](?:\.\d{1,2})?)(?!\d)(?:\s*/\s*4(?:\.0+)?)?", text)
    return float(m.group(1)) if m else None


def mock_resume_screen(job, resume_text: str, form_answers: list[dict] | None = None) -> dict:
    # form answers fill gaps in the resume (e.g. "2" for total experience becomes "2 years")
    extra = [
        f"{a['answer']} years experience" if a["id"] == "total_experience" else f"{a['label']}: {a['answer']}"
        for a in (form_answers or [])
    ]
    text = "\n".join([resume_text, *extra]).lower()
    required = job.required_skills or []
    matched = [s for s in required if _has_skill(text, s)]
    missing = [s for s in required if s not in matched]
    skills = sorted({v for v in VOCAB if _contains(text, v)} | {m.lower() for m in matched})

    ratio = len(matched) / len(required) if required else 1.0
    skill_score = min(40.0, round(40 * ratio, 1))

    years_exp = _years(text)
    if job.min_experience_years <= 0:
        exp_score = 20.0 if years_exp > 0 else 14.0
    else:
        exp_score = round(min(20.0, 20 * years_exp / job.min_experience_years), 1)
    if ratio < 0.25:  # experience is probably not relevant to this job
        exp_score = round(exp_score * 0.4, 1)

    level, edu_label = _detect_education(text)
    relevant_field = any(
        _contains(text, w) for w in ["computer", "software", "information technology", "data science", "engineering"]
    )
    gap = EDUCATION_RANK[EducationLevel(job.education_level)] - EDUCATION_RANK[EducationLevel(level)]
    if level == EducationLevel.NONE.value:
        edu_score = 0.0
    elif gap <= 0:
        edu_score = 10.0 if relevant_field else 7.0
    elif gap == 1:
        edu_score = 5.0
    else:
        edu_score = 2.0

    return {
        "skills": skills,
        "matched_skills": matched,
        "missing_skills": missing,
        "years_experience": _years(resume_text.lower()),  # from the resume alone, like education_level
        "education": f"{edu_label}{' (Computing)' if relevant_field else ''}",
        "education_level": _detect_education(resume_text.lower())[0],  # from the resume alone, not the claims
        "cgpa": _detect_cgpa(resume_text.lower()),
        "certifications": re.findall(r"(?:certified|certificate in|certification:?)\s+([a-z0-9 .+#-]{3,40})", text)[:5],
        "summary": (
            f"[Mock AI] Candidate lists {len(skills)} technical skills and about {years_exp:g} years of "
            f"experience. Matches {len(matched)} of {len(required)} required skills for {job.title}."
        ),
        "skill_score": skill_score,
        "experience_score": exp_score,
        "education_score": edu_score,
        "reasoning": (
            f"Skills: matched {len(matched)}/{len(required)} ({', '.join(matched) or 'none'}). "
            f"Experience: ~{years_exp:g} years vs {job.min_experience_years} required. "
            f"Education: {edu_label} vs required {job.education_level}."
        ),
    }


def mock_questions(job, parsed: dict, n: int) -> dict:
    questions: list[dict] = []
    for skill in job.required_skills:
        questions.append(
            {
                "text": f"Tell me about a project where you used {skill}. What did you build with it?",
                "focus": skill,
            }
        )
    for skill in (parsed or {}).get("skills", []):
        if skill.lower() not in {s.lower() for s in job.required_skills}:
            questions.append(
                {
                    "text": f"Your resume mentions {skill}. How does it relate to the work of a " f"{job.title}?",
                    "focus": f"Resume: {skill}",
                }
            )
    generic = [
        {
            "text": f"Why do you want to work as a {job.title}?",
            "focus": "Motivation",
        },
        {
            "text": "When something in your code does not work, what steps do you take to find the problem?",
            "focus": "Problem solving",
        },
        {
            "text": "How do you make sure the code you write is reliable and easy for others to maintain?",
            "focus": "Code quality",
        },
    ]
    questions.extend(generic)
    behavioural = {
        "text": "Tell me about a time you disagreed with a teammate. How did you handle it and what "
        "was the outcome?",
        "focus": "Behavioural",
    }
    return {"questions": questions[: n - 1] + [behavioural]}


def _seed(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest(), 16)


def mock_follow_up(question: dict, transcript: str) -> dict:
    """Simulated live follow-up: quotes the start of the candidate's own answer back to them."""
    words = transcript.split()
    quote = " ".join(words[:8]).rstrip(",.") + ("…" if len(words) > 8 else "")
    return {
        "text": f'You said: "{quote}". Can you give one concrete example of that and explain why you chose '
        f"that approach?"
    }


def mock_transcript(audio: bytes, question: dict) -> str:
    """Pretend to transcribe. Tiny recordings are treated as silence (empty transcript)."""
    if len(audio) < 2000:
        return ""
    focus = question.get("focus", "this topic").removeprefix("Follow-up: ") or "this topic"
    quality = _seed(hashlib.sha256(audio).hexdigest(), question["text"]) % 3
    if quality == 0:
        return (
            f"Yes, so with {focus} I built a project where we had to handle a lot of requests. "
            f"I designed the structure, wrote tests, and fixed a performance issue by adding caching "
            f"and an index on the database. I learned to measure first before optimising."
        )
    if quality == 1:
        return (
            f"I have used {focus} in my university project. It was mostly basic usage, I followed "
            f"tutorials and then changed things for our needs. It worked well in the end."
        )
    return "Um, I'm not really sure about that one, I think I would search online for it."


def mock_answer_eval(job, question: dict, transcript: str) -> dict:
    text = transcript.lower()
    words = len(text.split())
    keywords = [question.get("focus", "")] + list(job.required_skills)
    hits = sum(1 for k in keywords if k and _has_skill(text, k))
    concrete = sum(
        1
        for w in ["built", "designed", "tests", "fixed", "index", "measure", "example", "because", "learned", "project"]
        if w in text
    )
    accuracy = min(10.0, 2 + hits * 1.5 + concrete * 0.8)
    relevance = min(10.0, 3 + hits * 2.5)
    clarity = min(10.0, 2 + words / 8)
    if words < 15:
        accuracy, relevance, clarity = min(accuracy, 3), min(relevance, 4), min(clarity, 3)
    return {
        "accuracy": round(accuracy, 1),
        "relevance": round(relevance, 1),
        "clarity": round(clarity, 1),
        "score": 0,
        "feedback": (
            "[Mock AI] The answer "
            + (
                "gives concrete details and examples. "
                if concrete >= 3
                else "is quite general and lacks specific examples. "
            )
            + ("It stays on topic. " if hits else "It does not clearly address the question topic. ")
            + "A stronger answer would describe a specific situation, the actions taken and the result."
        ),
    }
