import smtplib
from email.message import EmailMessage

from app.config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_TO, SMTP_USER
from app.models import Task


def send_due_email(task: Task) -> bool:
    """Best-effort email delivery for a due reminder.

    Returns False (never raises) whenever SMTP isn't configured or sending
    fails, so the scheduler can mark the task notified either way rather
    than retrying indefinitely against a broken mail config.
    """
    if not (SMTP_HOST and SMTP_TO):
        return False
    try:
        when = task.due_at.strftime("%a, %b %d at %I:%M %p") if task.due_at else "now"
        message = EmailMessage()
        message["Subject"] = f"Reminder: {task.title}"
        message["From"] = SMTP_FROM
        message["To"] = SMTP_TO
        message.set_content(f'"{task.title}" was due {when}.')

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
        return True
    except Exception:
        return False
