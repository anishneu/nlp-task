import re
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from dateutil.relativedelta import relativedelta

from app import clock, crud
from app.database import SessionLocal

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

# "every N days/weeks/months" (e.g. "every_3_days") — a custom interval
# beyond the fixed cadences above. Parsed at tick time rather than
# pre-populating the map, since N is unbounded.
_CUSTOM_INTERVAL_RE = re.compile(r"^every_(\d+)_(days|weeks|months)$")


def _step_for_recurrence(recurrence: str):
    step = _RECURRENCE_STEP.get(recurrence)
    if step is not None:
        return step
    match = _CUSTOM_INTERVAL_RE.match(recurrence)
    if not match:
        return None
    count, unit = int(match.group(1)), match.group(2)
    if unit == "days":
        return timedelta(days=count)
    if unit == "weeks":
        return timedelta(weeks=count)
    return relativedelta(months=count)  # "months" — same calendar-correct jump as monthly/yearly


_scheduler = BackgroundScheduler()


def run_reminder_tick() -> None:
    """Runs on every scheduler interval: fast-forwards recurring tasks whose
    due date has passed to their next future occurrence, so a missed
    reminder (server was down, or nobody had the app open) still lands on
    the right future date instead of staying stuck in the past.
    """
    db = SessionLocal()
    try:
        now = clock.now()

        for task in crud.list_overdue_recurring_tasks(db, now):
            if task.recurrence == "weekday":
                next_due = task.due_at
                while next_due <= now or next_due.weekday() >= 5:
                    next_due += timedelta(days=1)
                task.due_at = next_due
                continue
            step = _step_for_recurrence(task.recurrence)
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
