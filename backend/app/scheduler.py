from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app import crud
from app.database import SessionLocal
from app.notifications import send_due_email

_RECURRENCE_STEP = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "monthly": timedelta(days=30),
}

_scheduler = BackgroundScheduler()


def run_reminder_tick() -> None:
    """Runs on every scheduler interval:

    1. Emails (best-effort) any due task that hasn't been notified yet.
    2. Fast-forwards recurring tasks whose due date has passed to their next
       future occurrence, so a missed reminder (server was down, or nobody
       had the app open) still lands on the right future date instead of
       staying stuck in the past — and clears notified_at so the next
       occurrence gets its own notification.
    """
    db = SessionLocal()
    try:
        now = datetime.now()

        for task in crud.list_unnotified_due_tasks(db, now):
            send_due_email(task)
            task.notified_at = now
        db.commit()

        for task in crud.list_overdue_recurring_tasks(db, now):
            step = _RECURRENCE_STEP.get(task.recurrence)
            if step is None:
                continue
            next_due = task.due_at
            while next_due <= now:
                next_due += step
            task.due_at = next_due
            task.notified_at = None
        db.commit()
    finally:
        db.close()


def start_scheduler() -> None:
    if not _scheduler.running:
        _scheduler.add_job(run_reminder_tick, "interval", seconds=30, id="reminder_tick")
        _scheduler.start()


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
