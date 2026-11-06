"""Candidate profiles: saving, photo and default resume, completeness, and the hard job requirements check."""

import hashlib
import hmac
import re
import secrets
import time
import unicodedata
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Application, CandidateProfile, Job, User
from app.models.enums import EDUCATION_LABEL, EDUCATION_RANK, EducationLevel, Role
from app.schemas.profile import ProfileIn
from app.services.storage import StorageError, get_storage

MAX_PHOTO_BYTES = 2 * 1024 * 1024
PHOTO_URL_SECONDS = 12 * 3600


def get_or_create(db: Session, user: User) -> CandidateProfile:
    if user.profile is None:
        user.profile = CandidateProfile(user_id=user.id)
        db.add(user.profile)
        db.flush()
    return user.profile


def level_label(level: str | None) -> str:
    if not level:
        return "Not set"
    try:
        return EDUCATION_LABEL[EducationLevel(level)]
    except ValueError:
        return level


def _parts(p: CandidateProfile | None) -> list[tuple[str, bool]]:
    """Each part of a complete profile and whether it is done. Only basic details: degree, experience and CGPA
    are read from the resume during screening."""
    p = p or CandidateProfile()
    return [
        ("Photo", bool(p.photo_key)),
        ("Phone", bool(p.phone)),
        ("City", bool(p.city)),
        ("Resume", bool(p.resume_key)),
    ]


def missing_fields(p: CandidateProfile | None) -> list[str]:
    """Plain names of what is still needed before the candidate can apply."""
    return [name for name, done in _parts(p) if not done]


def completion(p: CandidateProfile | None) -> int:
    parts = _parts(p)
    return round(100 * sum(done for _, done in parts) / len(parts))


def photo_url(user_id: uuid.UUID, photo_key: str | None) -> str | None:
    """A signed link the browser can use in <img src>, valid for a few hours. Only given to allowed viewers."""
    if not photo_key:
        return None
    exp = int(time.time()) + PHOTO_URL_SECONDS
    exp -= exp % 3600  # same link for an hour so the browser can cache the image
    sig = _sign(f"{user_id}:{photo_key}:{exp}")
    return f"/api/photos/{user_id}?exp={exp}&sig={sig}"


def _sign(text: str) -> str:
    return hmac.new(settings.JWT_SECRET.encode(), text.encode(), hashlib.sha256).hexdigest()[:32]


def check_photo_signature(user_id: uuid.UUID, photo_key: str, exp: int, sig: str) -> bool:
    return exp >= time.time() and hmac.compare_digest(_sign(f"{user_id}:{photo_key}:{exp}"), sig)


def to_out(user: User) -> dict:
    p = user.profile
    missing = missing_fields(p)
    data = {
        "user_id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "completion": completion(p),
        "missing": missing,
        "complete": not missing,
    }
    if p is not None:
        data |= {
            "headline": p.headline,
            "phone": p.phone,
            "city": p.city,
            "about": p.about,
            "photo_url": photo_url(user.id, p.photo_key),
            "highest_degree": p.highest_degree,
            "highest_degree_label": level_label(p.highest_degree) if p.highest_degree else None,
            "field_of_study": p.field_of_study,
            "institute": p.institute,
            "cgpa": p.cgpa,
            "graduation_year": p.graduation_year,
            "experience_years": p.experience_years,
            "experience": p.experience or [],
            "skills": p.skills or [],
            "linkedin_url": p.linkedin_url,
            "github_url": p.github_url,
            "portfolio_url": p.portfolio_url,
            "resume_filename": p.resume_filename,
            "has_resume": bool(p.resume_key),
        }
    return data


def update(db: Session, user: User, data: ProfileIn) -> User:
    p = get_or_create(db, user)
    changes = data.model_dump(exclude_unset=True, mode="json")
    if "full_name" in changes:
        if changes["full_name"]:
            user.full_name = changes["full_name"]
        changes.pop("full_name")
    for field, value in changes.items():
        setattr(p, field, value)
    db.commit()
    db.refresh(user)
    return user


def _image_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_photo(db: Session, user: User, data: bytes) -> User:
    ext = _image_type(data)
    if ext is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Photo must be a JPG, PNG or WebP image")
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Photo must be 2 MB or smaller")
    p = get_or_create(db, user)
    old = p.photo_key
    key = f"profiles/{user.id}/photo-{secrets.token_hex(4)}.{ext}"
    get_storage().save(key, data, {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[ext])
    p.photo_key = key
    db.commit()
    _delete_quietly(old)
    db.refresh(user)
    return user


def save_resume(db: Session, user: User, upload: UploadFile, data: bytes) -> User:
    from app.services.application import validate_pdf  # avoid an import cycle

    validate_pdf(upload, data)
    p = get_or_create(db, user)
    old = p.resume_key
    key = f"profiles/{user.id}/resume-{secrets.token_hex(4)}.pdf"
    get_storage().save(key, data, "application/pdf")
    p.resume_key = key
    p.resume_filename = (upload.filename or "resume.pdf").replace("/", "_")[-200:]
    db.commit()
    _delete_quietly(old)
    db.refresh(user)
    return user


def _delete_quietly(key: str | None) -> None:
    if not key:
        return
    storage = get_storage()
    if hasattr(storage, "delete"):
        try:
            storage.delete(key)
        except Exception:  # an old file left behind does no harm
            pass


def load_file(key: str | None) -> bytes:
    if not key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    try:
        return get_storage().load(key)
    except StorageError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found") from None


# --- Hard requirements -----------------------------------------------------------------------------
def _fmt_years(v: float | None) -> str:
    if v is None:
        return "Not set"
    return f"{v:g} year" + ("" if v == 1 else "s")


def requirements(job: Job, level: str | None, years: float | None, cgpa: float | None) -> list[dict]:
    """The job's minimum degree, experience and CGPA checked against what the RESUME shows. Only rules the job
    sets are listed. A degree or CGPA the resume does not state is not held against the candidate."""
    checks = []
    if job.education_level and job.education_level != EducationLevel.NONE:
        need = EducationLevel(job.education_level)
        known = bool(level) and level != EducationLevel.NONE
        checks.append(
            {
                "rule": "education",
                "label": "Minimum degree",
                "required": f"{EDUCATION_LABEL[need]} or higher",
                "yours": level_label(level) if known else "Not shown in the resume",
                "ok": not known or EDUCATION_RANK[EducationLevel(level)] >= EDUCATION_RANK[need],
            }
        )
    if job.min_experience_years and job.min_experience_years > 0:
        checks.append(
            {
                "rule": "experience",
                "label": "Minimum experience",
                "required": f"{_fmt_years(job.min_experience_years)} or more",
                "yours": _fmt_years(years or 0),
                "ok": (years or 0) + 1e-9 >= job.min_experience_years,
            }
        )
    if job.min_cgpa:
        checks.append(
            {
                "rule": "cgpa",
                "label": "Minimum CGPA",
                "required": f"{job.min_cgpa:.2f} / 4.00 or higher",
                "yours": f"{cgpa:.2f} / 4.00" if cgpa is not None else "Not shown in the resume",
                "ok": cgpa is None or cgpa + 1e-9 >= job.min_cgpa,
            }
        )
    return checks


def eligibility(job: Job, p: CandidateProfile | None) -> dict:
    """Before applying only the profile must be complete. The job's minimums are checked from the resume when it
    is screened, so "checks" is empty here."""
    complete = not missing_fields(p)
    return {"eligible": complete, "profile_complete": complete, "checks": []}


def snapshot(user: User) -> dict:
    """What the candidate claimed when they applied. Kept on the application, so later profile edits don't change it."""
    p = user.profile
    return {
        "headline": p.headline,
        "phone": p.phone,
        "city": p.city,
        "highest_degree": p.highest_degree,
        "highest_degree_label": level_label(p.highest_degree),
        "field_of_study": p.field_of_study,
        "institute": p.institute,
        "cgpa": p.cgpa,
        "graduation_year": p.graduation_year,
        "experience_years": p.experience_years,
        "experience": p.experience or [],
        "skills": p.skills or [],
        "linkedin_url": p.linkedin_url,
        "github_url": p.github_url,
        "portfolio_url": p.portfolio_url,
    }


def snapshot_as_answers(snap: dict | None) -> list[dict]:
    """The profile in the same shape as form answers, for the AI prompt (and the mock AI)."""
    if not snap:
        return []
    out = []
    if snap.get("highest_degree"):
        out.append({"id": "highest_degree", "label": "Highest degree", "answer": snap.get("highest_degree_label")})
    if snap.get("field_of_study"):
        out.append({"id": "field_of_study", "label": "Field of study", "answer": snap["field_of_study"]})
    if snap.get("cgpa") is not None:
        out.append({"id": "cgpa", "label": "CGPA (out of 4.0)", "answer": f"{snap['cgpa']:.2f}"})
    if snap.get("experience_years") is not None:
        out.append(
            {"id": "total_experience", "label": "Total years of experience", "answer": f"{snap['experience_years']:g}"}
        )
    # Skills and past roles listed in the profile are not sent: skills are scored from the resume only.
    return out


def compare_with_resume(snap: dict | None, resume_level: str, resume_years: float) -> list[str]:
    """Differences between what the profile claims and what the resume shows. Shown to the recruiter."""
    if not snap:
        return []
    out = []
    claimed = snap.get("highest_degree")
    if claimed and resume_level and resume_level != EducationLevel.NONE:
        if EDUCATION_RANK[EducationLevel(resume_level)] < EDUCATION_RANK[EducationLevel(claimed)]:
            out.append(f"Candidate says {level_label(claimed)}, but the resume shows {level_label(resume_level)}")
    years = snap.get("experience_years")
    if years is not None and years - resume_years >= 2 and years > 1.5 * resume_years:
        out.append(
            f"Candidate says {_fmt_years(years)} of experience, but the resume shows about {_fmt_years(resume_years)}"
        )
    return out


# --- Is this resume the candidate's own? ----------------------------------------------------------------
# Very common first names / titles that alone don't identify anyone.
_COMMON_NAME_PARTS = {"muhammad", "mohammad", "mohammed", "muhammed", "syed", "sayed", "mr", "mrs", "ms", "miss", "dr"}


def name_parts(full_name: str) -> list[str]:
    words = re.findall(r"[a-z]+", unicodedata.normalize("NFKD", full_name).lower())
    return [w for w in words if len(w) >= 3 and w not in _COMMON_NAME_PARTS]


def resume_has_name(full_name: str, text: str) -> bool:
    """True if the resume text shows the profile name: two parts of it (one for a one-word name), as whole words.
    "Ali Hassan" matches a resume for "Muhammad Ali Hassan", but not one for "Ali Khan"."""
    parts = name_parts(full_name)
    if not parts:
        return True  # nothing distinctive to check
    words = set(re.findall(r"[a-z]+", unicodedata.normalize("NFKD", text).lower()))
    return sum(p in words for p in dict.fromkeys(parts)) >= min(2, len(set(parts)))


def form_claims(answers: list[dict] | None) -> dict:
    """Degree and years of experience the candidate typed into the job's form, in the profile snapshot's shape."""
    out: dict = {}
    for a in answers or []:
        if a["id"] == "total_experience":
            try:
                out["experience_years"] = float(a["answer"])
            except ValueError:
                pass
        elif a["id"] == "highest_degree":
            text = a["answer"].lower()
            for level, label in EDUCATION_LABEL.items():
                if level != EducationLevel.NONE and label.split(" ")[0].lower().rstrip("'s") in text:
                    out["highest_degree"] = level.value
    return out


def phone_digits(phone: str | None) -> str:
    """The last 10 digits, so +92 300 1234567 and 0300-1234567 are the same number."""
    return re.sub(r"\D", "", phone or "")[-10:]


# --- Recruiter view ----------------------------------------------------------------------------------
def candidate_for_recruiter(db: Session, candidate_id: uuid.UUID, recruiter: User) -> tuple[User, list[Application]]:
    """A recruiter may see a candidate's profile only if that candidate applied to one of the recruiter's jobs.
    Only applications to this recruiter's jobs are returned."""
    candidate = db.get(User, candidate_id)
    if candidate is None or candidate.role != Role.CANDIDATE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    apps = list(
        db.scalars(
            select(Application)
            .join(Job, Job.id == Application.job_id)
            .where(Application.candidate_id == candidate.id, Job.recruiter_id == recruiter.id)
            .order_by(Application.created_at.desc())
        )
    )
    if not apps:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    return candidate, apps
