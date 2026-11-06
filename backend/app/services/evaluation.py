"""Score math in one place, so it is easy to test and explain.

resume_total   = skill (0-40) + experience (0-20) + education (0-10)        -> 0-70
answer score   = 0.5*accuracy + 0.3*relevance + 0.2*clarity                 -> 0-10 per answer
interview      = mean(answer scores) / 10 * 30                              -> 0-30
composite      = resume_total + interview                                   -> 0-100
"""


def resume_total(skill: float, experience: float, education: float) -> float:
    return round(skill + experience + education, 1)


def answer_score(accuracy: float, relevance: float, clarity: float) -> float:
    return round(0.5 * accuracy + 0.3 * relevance + 0.2 * clarity, 1)


def interview_score(answer_scores: list[float]) -> float:
    if not answer_scores:
        return 0.0
    mean = sum(answer_scores) / len(answer_scores)
    return round(mean / 10 * 30, 1)


def composite_score(resume: float, interview: float | None) -> float:
    return round(resume + (interview or 0.0), 1)
