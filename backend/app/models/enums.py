"""String constants used as enum values across models, schemas and services."""

from enum import StrEnum


class Role(StrEnum):
    RECRUITER = "recruiter"
    CANDIDATE = "candidate"


class EducationLevel(StrEnum):
    NONE = "none"
    MATRIC = "matric"  # Matric / O-Levels
    HIGH_SCHOOL = "high_school"  # Intermediate / A-Levels
    DIPLOMA = "diploma"
    BACHELORS = "bachelors"
    MASTERS = "masters"
    PHD = "phd"


EDUCATION_RANK = {lvl: i for i, lvl in enumerate(EducationLevel)}
EDUCATION_LABEL = {
    EducationLevel.NONE: "No formal degree",
    EducationLevel.MATRIC: "Matric / O-Levels",
    EducationLevel.HIGH_SCHOOL: "Intermediate / A-Levels",
    EducationLevel.DIPLOMA: "Diploma",
    EducationLevel.BACHELORS: "Bachelor's",
    EducationLevel.MASTERS: "Master's",
    EducationLevel.PHD: "PhD",
}


class JobStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class Stage(StrEnum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    SCREENING_FAILED = "screening_failed"
    NOT_QUALIFIED = "not_qualified"
    INTERVIEW_INVITED = "interview_invited"
    INTERVIEW_IN_PROGRESS = "interview_in_progress"
    EVALUATED = "evaluated"


class Decision(StrEnum):
    PENDING = "pending"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"


class SessionStatus(StrEnum):
    INVITED = "invited"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class AuditKind(StrEnum):
    RESUME_SCREEN = "resume_screen"
    QUESTION_GEN = "question_gen"
    ANSWER_EVAL = "answer_eval"
    TRANSCRIBE = "transcribe"
