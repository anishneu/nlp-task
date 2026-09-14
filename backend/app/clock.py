from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import APP_TIMEZONE


def now() -> datetime:
    """The current time as a naive datetime, in APP_TIMEZONE if it's set.

    Every "now" in this app — task due dates, timestamps, the scheduler's
    overdue check — should go through here instead of calling
    datetime.now() directly. The whole app treats naive datetimes as
    wall-clock time in one timezone, so without this, the server process's
    own system clock (which may not match where you actually live,
    especially on a cloud host or a dev sandbox) silently becomes the
    source of truth instead of yours.
    """
    if APP_TIMEZONE:
        return datetime.now(ZoneInfo(APP_TIMEZONE)).replace(tzinfo=None)
    return datetime.now()
