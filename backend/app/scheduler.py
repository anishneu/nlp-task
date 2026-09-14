from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from dateutil.relativedelta import relativedelta

from app import crud
from app.database import SessionLocal
from app.notifications import send_due_email

_RECURRENCE_STEP = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    # A calendar month/year, not a flat number of days — a flat step drifts
    # the due date across real months (e.g. Jan 31 + 30 days lands on Mar 2,
    # not Feb 28).
    "monthly": relativedelta(months=1),
    "yearly": relativedelta(years=1),
    # "weekday" isn't a fixed step (it has to skip Saturday/Sunday), so it's
    # handled separately in run_reminder_tick rather than through this map.
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
            if task.recurrence == "weekday":
                next_due = task.due_at
                while next_due <= now or next_due.weekday() >= 5:
                    next_due += timedelta(days=1)
                task.due_at = next_due
                task.notified_at = None
                continue
            step = _RECURRENCE_STEP.get(task.recurrence)
            if step is None:
                continue
            if isinstance(step, relativedelta):
                # Jump directly from the original due date rather than
                # repeatedly re-basing on the previous (possibly
                # day-clamped) result — otherwise a short month like
                # February permanently "sticks" the day-of-month down
                # (Jan 31 -> Feb 28 -> Mar 28 instead of Mar 31).
                anchor = task.due_at
                periods = 1
                next_due = anchor + step
                while next_due <= now:
                    periods += 1
                    next_due = anchor + step * periods
            else:
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
