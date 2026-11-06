"""Email notifications behind one interface: console (dev, just logs) or Resend (production).

The system NEVER emails rejections. Only: application received, interview invitation,
interview completed (candidate), and recruiter alerts (new evaluation, manual review needed).
"""

import logging
from functools import lru_cache
from html import escape
from typing import Protocol

from app.config import settings

log = logging.getLogger("email")


class EmailService(Protocol):
    def send(self, to: str, subject: str, html: str) -> None: ...


class ConsoleEmailService:
    """Dev backend: prints the email to the server log. Keeps a list so tests can inspect sent mail."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, to: str, subject: str, html: str) -> None:
        self.sent.append({"to": to, "subject": subject, "html": html})
        log.info("EMAIL to=%s subject=%s\n%s", to, subject, html)


class ResendEmailService:
    def __init__(self, api_key: str, sender: str) -> None:
        import resend

        resend.api_key = api_key
        self._resend = resend
        self.sender = sender

    def send(self, to: str, subject: str, html: str) -> None:
        try:
            self._resend.Emails.send({"from": self.sender, "to": [to], "subject": subject, "html": html})
        except Exception as exc:  # an email failure must never break the main flow
            log.error("Resend failed for %s: %s", to, exc)


class SmtpEmailService:
    """Any SMTP server, e.g. Gmail with an App password (works without owning a domain)."""

    def __init__(self, host: str, port: int, user: str, password: str, sender: str) -> None:
        self.host, self.port, self.user, self.password = host, port, user, password
        self.sender = sender if "@" in sender and "resend.dev" not in sender else f"RecruitAI <{user}>"

    def send(self, to: str, subject: str, html: str) -> None:
        import smtplib
        import ssl
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.sender, to, subject
        msg.set_content("Please open this email in an app that shows HTML.")
        msg.add_alternative(html, subtype="html")
        try:
            if self.port == 465:
                with smtplib.SMTP_SSL(self.host, self.port, context=ssl.create_default_context(), timeout=20) as s:
                    s.login(self.user, self.password)
                    s.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=20) as s:
                    s.starttls(context=ssl.create_default_context())
                    s.login(self.user, self.password)
                    s.send_message(msg)
        except Exception as exc:  # an email failure must never break the main flow
            log.error("SMTP failed for %s: %s", to, exc)


@lru_cache
def get_email_service() -> EmailService:
    if settings.EMAIL_BACKEND == "resend" and settings.RESEND_API_KEY:
        return ResendEmailService(settings.RESEND_API_KEY, settings.EMAIL_FROM)
    if settings.EMAIL_BACKEND == "smtp" and settings.SMTP_USER and settings.SMTP_PASSWORD:
        return SmtpEmailService(
            settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_USER, settings.SMTP_PASSWORD, settings.EMAIL_FROM
        )
    return ConsoleEmailService()


def _wrap(title: str, body: str) -> str:
    return (
        "<div style='font-family:Inter,Arial,sans-serif;max-width:560px;margin:auto;color:#111'>"
        f"<h2 style='color:#0a0a0a'>{title}</h2>{body}"
        "<p style='color:#888;font-size:12px'>AI Recruitment Assistant</p></div>"
    )


class Notifier:
    """High-level email helpers used by the services."""

    def __init__(self, email: EmailService | None = None) -> None:
        self.email = email or get_email_service()

    def password_reset(self, to: str, name: str, token: str, minutes: int) -> None:
        link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        self.email.send(
            to,
            "Reset your password",
            _wrap(
                "Reset your password",
                f"<p>Hi {escape(name)},</p><p>Someone asked to reset the password for your AI Recruitment Assistant "
                f"account. The link works for {minutes} minutes and only once.</p>"
                f"<p><a href='{link}' style='background:#0a0a0a;color:#fff;padding:10px 16px;border-radius:6px;"
                f"text-decoration:none'>Choose a new password</a></p><p style='word-break:break-all'>{link}</p>"
                "<p>If this wasn't you, ignore this email. Your password stays the same.</p>",
            ),
        )

    def password_code(self, to: str, name: str, code: str, minutes: int, purpose: str) -> None:
        """A 6-digit code for resetting (forgot password) or changing the password."""
        action = "reset" if purpose == "reset" else "change"
        self.email.send(
            to,
            f"Your RecruitAI code: {code}",
            _wrap(
                f"Your code to {action} your password",
                f"<p>Hi {escape(name)},</p><p>Use this code to {action} your RecruitAI password. "
                f"It works for {minutes} minutes.</p>"
                f"<p style='font-size:32px;font-weight:700;letter-spacing:8px;margin:24px 0'>{code}</p>"
                "<p>If you did not ask for this, ignore this email. Your password stays the same.</p>",
            ),
        )

    def verify_email(self, to: str, name: str, token: str) -> None:
        link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        self.email.send(
            to,
            "Confirm your email",
            _wrap(
                "Welcome to RecruitAI",
                f"<p>Hi {escape(name)},</p><p>Please confirm that this is your email address. The link works for "
                f"3 days.</p><p><a href='{link}' style='background:#0a0a0a;color:#fff;padding:10px 16px;"
                f"border-radius:6px;text-decoration:none'>Confirm my email</a></p>"
                f"<p style='word-break:break-all'>{link}</p>",
            ),
        )

    def application_received(self, to: str, name: str, job_title: str) -> None:
        name, job_title = escape(name), escape(job_title)
        self.email.send(
            to,
            f"Application received: {job_title}",
            _wrap(
                "We received your application",
                f"<p>Hi {name},</p><p>Thanks for applying to <b>{job_title}</b>. Our system is reviewing your "
                "resume and we will contact you about next steps.</p>",
            ),
        )

    def interview_invitation(self, to: str, name: str, job_title: str, session_id: str) -> None:
        name, job_title = escape(name), escape(job_title)
        link = f"{settings.FRONTEND_URL}/interview/{session_id}"
        self.email.send(
            to,
            f"Interview invitation: {job_title}",
            _wrap(
                "You're invited to an AI voice interview",
                f"<p>Hi {name},</p><p>Your application for <b>{job_title}</b> has moved forward. Please complete a "
                f"short voice interview in your browser (Chrome recommended, microphone required).</p>"
                f"<p><a href='{link}' style='background:#0a0a0a;color:#fff;padding:10px 16px;border-radius:6px;"
                f"text-decoration:none'>Start interview</a></p><p>{link}</p>",
            ),
        )

    def shortlisted(self, to: str, name: str, job_title: str) -> None:
        name, job_title = escape(name), escape(job_title)
        self.email.send(
            to,
            f"Good news about your application: {job_title}",
            _wrap(
                "You've been shortlisted",
                f"<p>Hi {name},</p><p>The recruiter has shortlisted you for <b>{job_title}</b>. They will contact you "
                f"by email about the next steps.</p><p><a href='{settings.FRONTEND_URL}/applications'>View my "
                "applications</a></p>",
            ),
        )

    def interview_completed(self, to: str, name: str, job_title: str) -> None:
        name, job_title = escape(name), escape(job_title)
        self.email.send(
            to,
            f"Interview completed: {job_title}",
            _wrap(
                "Thank you for completing your interview",
                f"<p>Hi {name},</p><p>Your interview for <b>{job_title}</b> is complete. The recruiter will review "
                "your application and contact you.</p>",
            ),
        )

    def recruiter_candidate_evaluated(self, to: str, candidate: str, job_title: str, app_id: str) -> None:
        candidate, job_title = escape(candidate), escape(job_title)
        self.email.send(
            to,
            f"New candidate evaluated: {candidate}",
            _wrap(
                "A candidate finished their interview",
                f"<p>{candidate} completed the interview for <b>{job_title}</b>.</p>"
                f"<p><a href='{settings.FRONTEND_URL}/recruiter/applications/{app_id}'>View candidate</a></p>",
            ),
        )

    def recruiter_manual_review(self, to: str, candidate: str, job_title: str, reason: str, app_id: str) -> None:
        candidate, job_title = escape(candidate), escape(job_title)
        self.email.send(
            to,
            f"Manual review needed: {candidate}",
            _wrap(
                "An application needs manual review",
                f"<p>The application from {candidate} for <b>{job_title}</b> could not be screened automatically.</p>"
                f"<p>Reason: {reason}</p>"
                f"<p><a href='{settings.FRONTEND_URL}/recruiter/applications/{app_id}'>Open application</a></p>",
            ),
        )
