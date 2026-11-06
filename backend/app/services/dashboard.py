"""Recruiter dashboard: ranked candidates, full candidate detail, decisions/notes and job statistics."""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.client import AIServiceError
from app.models import Application, Job, User
from app.models.enums import Decision, JobStatus, Stage
from app.services import integrity
from app.services import profile as profile_svc
from app.services.application import set_stage
from app.services.interview import create_interview_session
from app.services.notification import Notifier

SORTS = {"recent", "composite", "resume", "interview", "date", "name"}


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)  # SQLite returns naive datetimes


def last_activity(a: Application) -> tuple[datetime, str]:
    """The latest thing the candidate did, so fresh interviews rise to the top."""
    s = a.interview
    options = [(_aware(a.created_at), "Applied")]
    if s and s.started_at:
        options.append((_aware(s.started_at), "Started interview"))
    if s and s.completed_at:
        options.append((_aware(s.completed_at), "Ended interview early" if s.terminated else "Finished interview"))
    return max(options, key=lambda o: o[0])


def is_new(a: Application) -> bool:
    """Something happened since the recruiter last opened this candidate."""
    when, _ = last_activity(a)
    seen = _aware(a.recruiter_viewed_at)
    return seen is None or when > seen


def mark_viewed(db: Session, a: Application) -> None:
    a.recruiter_viewed_at = datetime.now(UTC)
    db.commit()


def _photo(a: Application) -> str | None:
    p = a.candidate.profile
    return profile_svc.photo_url(a.candidate_id, p.photo_key) if p else None


def _resume_degree(a: Application) -> str | None:
    level = _parsed(a).get("education_level")
    return profile_svc.level_label(level) if level and level != "none" else None


def _row(a: Application) -> dict:
    ev = a.evaluation
    snap = a.profile_snapshot or {}
    return {
        "application_id": a.id,
        "candidate_id": a.candidate_id,
        "full_name": a.candidate.full_name,
        "email": a.candidate.email,
        "photo_url": _photo(a),
        "headline": snap.get("headline"),
        "city": snap.get("city"),
        "degree": (snap.get("highest_degree_label") if snap.get("highest_degree") else None) or _resume_degree(a),
        "experience_years": (
            snap["experience_years"] if snap.get("experience_years") is not None else _parsed(a).get("years_experience")
        ),
        "cgpa": snap.get("cgpa") if snap.get("cgpa") is not None else _parsed(a).get("cgpa"),
        "mismatch_count": len(a.mismatches or []),
        "stage": a.stage,
        "decision": a.recruiter_decision,
        "composite_score": ev.composite_score if ev else None,
        "skill_score": ev.skill_score if ev else None,
        "experience_score": ev.experience_score if ev else None,
        "education_score": ev.education_score if ev else None,
        "resume_total": ev.resume_total if ev else None,
        "interview_score": ev.interview_score if ev else None,
        "incomplete": ev.incomplete if ev else True,
        "needs_manual_review": a.needs_manual_review,
        "issue_reported": bool(a.interview and a.interview.issue_reported),
        "integrity_level": (
            integrity.summary(a.interview)["level"] if a.interview and a.interview.started_at else None
        ),
        "archived": a.archived,
        "form_answers": a.form_answers or [],
        "applied_at": a.created_at,
        "interview_completed_at": _aware(a.interview.completed_at) if a.interview else None,
        "last_activity_at": last_activity(a)[0],
        "last_activity": last_activity(a)[1],
        "is_new": is_new(a),
    }


def ranked_candidates(
    db: Session,
    job: Job,
    *,
    min_score: float | None = None,
    max_score: float | None = None,
    stage: str | None = None,
    decision: str | None = None,
    sort: str = "composite",
    only_shortlisted: bool = False,
) -> list[dict]:
    """Rank = position by composite score (desc; unscored last). Filters/sort are applied after ranking."""
    apps = db.scalars(
        select(Application)
        .where(Application.job_id == job.id)
        .options(
            selectinload(Application.candidate).selectinload(User.profile),
            selectinload(Application.evaluation),
            selectinload(Application.interview),
        )
    ).all()
    rows = [_row(a) for a in apps]
    rows.sort(key=lambda r: (r["composite_score"] is None, -(r["composite_score"] or 0), r["applied_at"]))
    for i, r in enumerate(rows, start=1):
        r["rank"] = i

    def keep(r: dict) -> bool:
        score = r["composite_score"]
        if min_score is not None and (score is None or score < min_score):
            return False
        if max_score is not None and (score is None or score > max_score):
            return False
        if stage and r["stage"] != stage:
            return False
        if decision and r["decision"] != decision:
            return False
        if only_shortlisted and r["decision"] != Decision.SHORTLISTED:
            return False
        return True

    rows = [r for r in rows if keep(r)]
    if sort == "resume":
        rows.sort(key=lambda r: (r["resume_total"] is None, -(r["resume_total"] or 0)))
    elif sort == "interview":
        rows.sort(key=lambda r: (r["interview_score"] is None, -(r["interview_score"] or 0)))
    elif sort == "recent":
        rows.sort(key=lambda r: r["last_activity_at"], reverse=True)
    elif sort == "date":
        rows.sort(key=lambda r: r["applied_at"], reverse=True)
    elif sort == "name":
        rows.sort(key=lambda r: r["full_name"].lower())
    return rows


def application_detail(a: Application) -> dict:
    ev, resume, session = a.evaluation, a.resume, a.interview
    interview = None
    if session is not None:
        by_index = {r.question_index: r for r in session.responses}
        responses = []
        for q in session.questions:
            r = by_index.get(q["index"])
            if r is None:
                continue
            responses.append(
                {
                    "question_index": r.question_index,
                    "question": q["text"],
                    "focus": q.get("focus", ""),
                    "transcript": r.transcript,
                    "accuracy": r.accuracy,
                    "relevance": r.relevance,
                    "clarity": r.clarity,
                    "score": r.score,
                    "feedback": r.feedback,
                    "has_audio": bool(r.audio_key),
                    "pending": bool(r.pending),
                    "kind": q.get("kind", "main"),
                }
            )
        interview = {
            "session_id": session.id,
            "status": session.status,
            "total_questions": len(session.questions),
            "current_index": session.current_index,
            "invited_at": session.invited_at,
            "started_at": session.started_at,
            "completed_at": session.completed_at,
            "issue_reported": session.issue_reported,
            "issue_text": session.issue_text,
            "questions": session.questions,
            "responses": responses,
            "integrity": integrity.summary(session) if session.started_at else None,
            "device_locked": session.device_token_hash is not None,
        }
    return {
        "id": a.id,
        "job_id": a.job_id,
        "job_title": a.job.title,
        "form_answers": a.form_answers or [],
        "required_skills": a.job.required_skills,
        "candidate": _candidate_brief(a),
        "profile_snapshot": a.profile_snapshot,
        "mismatches": a.mismatches or [],
        "requirements": _requirements(a),
        "stage": a.stage,
        "decision": a.recruiter_decision,
        "notes": a.recruiter_notes,
        "needs_manual_review": a.needs_manual_review,
        "review_reason": a.review_reason,
        "archived": a.archived,
        "applied_at": a.created_at,
        "resume_filename": resume.original_filename if resume else None,
        "parsed_resume": resume.parsed if resume else None,
        "scores": (
            None
            if ev is None
            else {
                "skill_score": ev.skill_score,
                "experience_score": ev.experience_score,
                "education_score": ev.education_score,
                "resume_total": ev.resume_total,
                "interview_score": ev.interview_score,
                "composite_score": ev.composite_score,
                "resume_reasoning": ev.resume_reasoning,
                "incomplete": ev.incomplete,
            }
        ),
        "interview": interview,
    }


def _candidate_brief(a: Application) -> dict:
    c, p = a.candidate, a.candidate.profile
    return {
        "id": str(c.id),
        "full_name": c.full_name,
        "email": c.email,
        "photo_url": _photo(a),
        "headline": p.headline if p else None,
        "phone": p.phone if p else None,
        "city": p.city if p else None,
        "linkedin_url": p.linkedin_url if p else None,
        "github_url": p.github_url if p else None,
        "portfolio_url": p.portfolio_url if p else None,
    }


def _parsed(a: Application) -> dict:
    return (a.resume.parsed if a.resume is not None else None) or {}


def _requirements(a: Application) -> list[dict]:
    """The job's minimum requirements checked against what the resume shows (once it has been screened)."""
    parsed = _parsed(a)
    if not parsed:
        return []
    return profile_svc.requirements(
        a.job, parsed.get("education_level"), parsed.get("years_experience"), parsed.get("cgpa")
    )


def set_decision(db: Session, a: Application, decision: Decision, notes: str | None) -> Application:
    """Recruiters can change ONLY the decision and private notes. AI scores are read-only."""
    newly_shortlisted = decision == Decision.SHORTLISTED and a.recruiter_decision != Decision.SHORTLISTED.value
    a.recruiter_decision = decision.value
    if notes is not None:
        a.recruiter_notes = notes.strip() or None
    db.commit()
    if newly_shortlisted:
        Notifier().shortlisted(a.candidate.email, a.candidate.full_name, a.job.title)
    return a


MANUAL_INVITE_STAGES = {Stage.NOT_QUALIFIED.value, Stage.SCREENING_FAILED.value}


def manual_invite(db: Session, a: Application) -> Application:
    """The recruiter overrides the screening result and invites the candidate to the voice interview."""
    if a.stage not in MANUAL_INVITE_STAGES:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only candidates who were not invited can be invited manually")
    if a.archived or a.job.status == JobStatus.CLOSED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "This job is closed")
    parsed = (a.resume.parsed if a.resume else None) or {}
    try:
        session = create_interview_session(db, a, parsed)
    except AIServiceError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Could not prepare interview questions: {exc}") from None
    set_stage(a, Stage.INTERVIEW_INVITED)
    a.needs_manual_review = False
    db.commit()
    db.refresh(a)
    Notifier().interview_invitation(a.candidate.email, a.candidate.full_name, a.job.title, str(session.id))
    return a


INTERVIEWED = {Stage.EVALUATED}
QUALIFIED = {Stage.INTERVIEW_INVITED, Stage.INTERVIEW_IN_PROGRESS, Stage.EVALUATED}


def _funnel(apps: list[Application], blocked: int = 0) -> list[dict]:
    return [
        {"key": "blocked", "label": "Stopped by requirements", "count": blocked},
        {"key": "applied", "label": "Applied", "count": len(apps)},
        {"key": "qualified", "label": "Passed screening", "count": sum(1 for a in apps if a.stage in QUALIFIED)},
        {"key": "interviewed", "label": "Interviewed", "count": sum(1 for a in apps if a.stage in INTERVIEWED)},
        {
            "key": "shortlisted",
            "label": "Shortlisted",
            "count": sum(1 for a in apps if a.recruiter_decision == Decision.SHORTLISTED),
        },
    ]


def job_stats(db: Session, job: Job) -> dict:
    apps = db.scalars(
        select(Application)
        .where(Application.job_id == job.id)
        .options(
            selectinload(Application.evaluation), selectinload(Application.interview), selectinload(Application.resume)
        )
    ).all()
    by_stage = {s.value: 0 for s in Stage}
    by_decision = {d.value: 0 for d in Decision}
    composites, resumes = [], []
    for a in apps:
        by_stage[a.stage] += 1
        by_decision[a.recruiter_decision] += 1
        if a.evaluation is not None:
            composites.append(a.evaluation.composite_score)
            resumes.append(a.evaluation.resume_total)
    histogram = [{"range": f"{lo}-{lo + 9 if lo < 90 else 100}", "count": 0} for lo in range(0, 100, 10)]
    for c in composites:
        histogram[min(int(c // 10), 9)]["count"] += 1
    screened = sum(
        by_stage[s]
        for s in (
            Stage.NOT_QUALIFIED,
            Stage.INTERVIEW_INVITED,
            Stage.INTERVIEW_IN_PROGRESS,
            Stage.EVALUATED,
            Stage.SCREENING_FAILED,
        )
    )

    # which required skills applicants are missing most often
    missing: dict[str, int] = {}
    for a in apps:
        parsed = (a.resume.parsed if a.resume else None) or {}
        for skill in parsed.get("missing_skills") or []:
            missing[skill] = missing.get(skill, 0) + 1
    missing_skills = [{"skill": k, "count": v} for k, v in sorted(missing.items(), key=lambda kv: -kv[1])[:8]]

    # average share of each score part (percent of its maximum)
    evs = [a.evaluation for a in apps if a.evaluation is not None]
    interviewed = [e.interview_score for e in evs if e.interview_score is not None]

    def pct(values: list[float], mx: float) -> float | None:
        return round(100 * sum(values) / (len(values) * mx), 1) if values else None

    breakdown = [
        {"part": "Skills", "percent": pct([e.skill_score for e in evs], 40)},
        {"part": "Experience", "percent": pct([e.experience_score for e in evs], 20)},
        {"part": "Education", "percent": pct([e.education_score for e in evs], 10)},
        {"part": "Interview", "percent": pct(interviewed, 30)},
    ]

    integrity_counts = {"clean": 0, "warning": 0, "high": 0}
    for a in apps:
        if a.interview and a.interview.started_at:
            integrity_counts[integrity.summary(a.interview)["level"]] += 1

    degrees: dict[str, int] = {}
    for a in apps:
        snap = a.profile_snapshot or {}
        label = (snap.get("highest_degree_label") if snap.get("highest_degree") else None) or _resume_degree(a)
        if label:
            degrees[label] = degrees.get(label, 0) + 1

    return {
        "job_id": job.id,
        "total": len(apps),
        "by_stage": by_stage,
        "by_decision": by_decision,
        "screened": screened,
        "interviewed": by_stage[Stage.INTERVIEW_IN_PROGRESS] + by_stage[Stage.EVALUATED],
        "evaluated": by_stage[Stage.EVALUATED],
        "avg_composite": round(sum(composites) / len(composites), 1) if composites else None,
        "avg_resume": round(sum(resumes) / len(resumes), 1) if resumes else None,
        "histogram": histogram,
        "funnel": _funnel(list(apps), job.blocked_applications or 0),
        "missing_skills": missing_skills,
        "breakdown": breakdown,
        "integrity": integrity_counts,
        "degrees": [{"label": k, "count": v} for k, v in sorted(degrees.items(), key=lambda kv: -kv[1])],
        "blocked_applications": job.blocked_applications or 0,
        "mismatches": sum(1 for a in apps if a.mismatches),
    }


def recruiter_overview(db: Session, recruiter_id) -> dict:
    """Totals across all of a recruiter's jobs + the most recent applications and items needing attention."""
    jobs = db.scalars(select(Job).where(Job.recruiter_id == recruiter_id)).all()
    job_ids = [j.id for j in jobs]
    apps = (
        db.scalars(
            select(Application)
            .where(Application.job_id.in_(job_ids))
            .options(
                selectinload(Application.candidate),
                selectinload(Application.evaluation),
                selectinload(Application.interview),
                selectinload(Application.job),
            )
            .order_by(Application.created_at.desc())
        ).all()
        if job_ids
        else []
    )
    composites = [a.evaluation.composite_score for a in apps if a.evaluation and not a.evaluation.incomplete]

    def brief(a: Application) -> dict:
        return {
            "application_id": a.id,
            "job_id": a.job_id,
            "job_title": a.job.title,
            "full_name": a.candidate.full_name,
            "stage": a.stage,
            "decision": a.recruiter_decision,
            "composite_score": a.evaluation.composite_score if a.evaluation else None,
            "incomplete": a.evaluation.incomplete if a.evaluation else True,
            "applied_at": a.created_at,
            "last_activity_at": last_activity(a)[0],
            "last_activity": last_activity(a)[1],
            "is_new": is_new(a),
            "integrity_level": (
                integrity.summary(a.interview)["level"] if a.interview and a.interview.started_at else None
            ),
        }

    attention = [a for a in apps if a.needs_manual_review or (a.interview and a.interview.issue_reported)]
    top = sorted(
        [a for a in apps if a.stage == Stage.EVALUATED and a.recruiter_decision == Decision.PENDING],
        key=lambda a: -a.evaluation.composite_score,
    )
    by_job: dict = {j.id: [] for j in jobs}
    for a in apps:
        by_job[a.job_id].append(a)
    job_cards = []
    for j in sorted(jobs, key=lambda j: (j.status != "active", _aware(j.created_at)), reverse=False):
        ja = by_job[j.id]
        done = [a.evaluation.composite_score for a in ja if a.evaluation and not a.evaluation.incomplete]
        latest = max((last_activity(a)[0] for a in ja), default=None)
        job_cards.append(
            {
                "id": j.id,
                "title": j.title,
                "status": j.status,
                "created_at": j.created_at,
                "deadline": j.deadline,
                "required_skills": j.required_skills,
                "applicants": len(ja),
                "new": sum(1 for a in ja if is_new(a) and not a.archived),
                "screening": sum(1 for a in ja if a.stage in (Stage.SUBMITTED, Stage.UNDER_REVIEW)),
                "waiting_interview": sum(
                    1 for a in ja if a.stage in (Stage.INTERVIEW_INVITED, Stage.INTERVIEW_IN_PROGRESS)
                ),
                "to_review": sum(
                    1 for a in ja if a.stage == Stage.EVALUATED and a.recruiter_decision == Decision.PENDING
                ),
                "needs_attention": sum(
                    1 for a in ja if a.needs_manual_review or (a.interview and a.interview.issue_reported)
                ),
                "shortlisted": sum(1 for a in ja if a.recruiter_decision == Decision.SHORTLISTED),
                "avg_score": round(sum(done) / len(done), 1) if done else None,
                "top_score": round(max(done), 1) if done else None,
                "blocked": j.blocked_applications or 0,
                "funnel": _funnel(ja, j.blocked_applications or 0),
                "last_activity_at": latest,
            }
        )
    job_cards.sort(
        key=lambda c: (c["status"] != "active", -(c["last_activity_at"] or _aware(c["created_at"])).timestamp())
    )
    return {
        "jobs": job_cards,
        "jobs_total": len(jobs),
        "jobs_active": sum(1 for j in jobs if j.status == "active"),
        "applications_total": len(apps),
        "interviews_pending": sum(
            1 for a in apps if a.stage in (Stage.INTERVIEW_INVITED, Stage.INTERVIEW_IN_PROGRESS) and not a.archived
        ),
        "evaluated": sum(1 for a in apps if a.stage == Stage.EVALUATED),
        "shortlisted": sum(1 for a in apps if a.recruiter_decision == Decision.SHORTLISTED),
        "needs_attention": len(attention),
        "avg_composite": round(sum(composites) / len(composites), 1) if composites else None,
        "recent": [brief(a) for a in sorted(apps, key=lambda a: last_activity(a)[0], reverse=True)[:8]],
        "recent_interviews": [
            brief(a)
            for a in sorted(
                (a for a in apps if a.interview and a.interview.completed_at),
                key=lambda a: _aware(a.interview.completed_at),
                reverse=True,
            )[:6]
        ],
        "new_count": sum(1 for a in apps if is_new(a) and not a.archived),
        "attention": [
            {**brief(a), "reason": a.review_reason or "Candidate reported a technical problem"} for a in attention[:5]
        ],
        "awaiting_decision": [brief(a) for a in top[:5]],
    }
