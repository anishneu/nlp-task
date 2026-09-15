import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta

import dateparser

from app import clock
from app.models import TaskStatus
from app.nlp.hf_intent import classify_intent_hf
from app.nlp.hf_segment import segment_events_hf
from app.nlp.intents import Intent

_DAY = r"(?:mon(?:day)?|tue(?:s|sday)?|wed(?:nesday)?|thu(?:rs|rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
_NUM_WORD = r"(?:a|an|\d+)"
_TIME = r"\d{1,2}(?::\d{2})?\s*(?:am|pm)|noon|midnight|(?<=\bat )\d{1,2}(?::\d{2})?\b"
_BARE_HOUR_RE = re.compile(r"^(?:at\s+)?\d{1,2}(?::\d{2})?$", re.IGNORECASE)
_PERIOD_OF_DAY_RE = re.compile(r"\b(morning|afternoon|evening|night)\b", re.IGNORECASE)
_PERIOD_TO_AMPM = {"morning": "am", "afternoon": "pm", "evening": "pm", "night": "pm"}
_REL = r"today|tomorrow|tonight"
_DAY_AFTER_TOMORROW = r"(?:the\s+)?day after tomorrow"
_NEXT_THIS = rf"(?:next|this)\s+(?:week|month|year|{_DAY})"
_IN_OFFSET = rf"in\s+{_NUM_WORD}\s+(?:min(?:ute)?s?|hrs?|hours?|days?|weeks?)"
_RECUR_DAY = rf"every\s+{_DAY}"
_RECUR_UNIT = r"every\s+(?:weekday|day|week|month|year)"
_RECUR_INTERVAL = r"every\s+\d+\s+(?:days?|weeks?|months?)"
_ORDINAL_DAY = r"(?:on\s+)?the\s+(?:[12]?[0-9]|3[01])(?:st|nd|rd|th)"
_URL_RE = re.compile(
    r"https?://\S+|(?:meet\.google\.com|zoom\.us|teams\.microsoft\.com)\S*", re.IGNORECASE
)

_DATE_PHRASE_RE = re.compile(
    # "friday at 5pm" / "friday 5pm" (the "at" is optional so a time right
    # after a date word — the far more common way people actually phrase
    # it — isn't left behind for dateparser to fail to a bare weekday).
    rf"\b(?:{_RECUR_DAY}|{_RECUR_INTERVAL}|{_RECUR_UNIT}|{_DAY_AFTER_TOMORROW}|{_REL}|{_NEXT_THIS}|{_DAY}|{_IN_OFFSET}|{_ORDINAL_DAY})\b(?:\s+(?:at\s+)?(?:{_TIME})\b)?"
    # "at 5pm friday" / "5pm friday" — time-first phrasing, with an
    # optional trailing date word so it also matches a bare time.
    rf"|\b(?:at\s+)?(?:{_TIME})\b(?:\s+(?:{_REL}|{_NEXT_THIS}|{_DAY}))?",
    re.IGNORECASE,
)
_IN_OFFSET_RE = re.compile(rf"^{_IN_OFFSET}\b", re.IGNORECASE)
_TIME_RE = re.compile(rf"\b(?:{_TIME})\b", re.IGNORECASE)
_RECUR_DAY_RE = re.compile(rf"^every\s+{_DAY}", re.IGNORECASE)
_NEXT_THIS_DAY_RE = re.compile(rf"^(?:next|this)\s+({_DAY})", re.IGNORECASE)
_RECUR_UNIT_RE = re.compile(r"^every\s+(weekday|day|week|month|year)\b", re.IGNORECASE)
_RECUR_INTERVAL_RE = re.compile(r"^every\s+(\d+)\s+(days?|weeks?|months?)\b", re.IGNORECASE)
_ORDINAL_DAY_RE = re.compile(r"^(?:on\s+)?the\s+([12]?[0-9]|3[01])(?:st|nd|rd|th)\b", re.IGNORECASE)
_RECURRENCE_LABELS = {
    "weekday": "weekday",
    "day": "daily",
    "week": "weekly",
    "month": "monthly",
    "year": "yearly",
}

_CREATE_TRIGGERS = [
    r"^remind me to\s+",
    r"^remind me\s+",
    r"^set a reminder to\s+",
    r"^add a task to\s+",
    r"^add a task\s+",
    r"^add task\s+",
    r"^create a task to\s+",
    r"^create a task\s+",
    r"^create task\s+",
    r"^i need to\s+",
    r"^schedule\s+",
]
_CREATE_TRIGGER_ANYWHERE_RE = re.compile(
    r"\bremind me\b(?:\s+(?:that|to|of))?\s*"
    r"|\breminder\b(?:\s+(?:that|to|of))?\s*"
    # "add 2 more tasks to the list" — the plain "^add (?:a )?task\b" below
    # only matches when that's literally the first thing said; conversation
    # almost never phrases it that plainly ("ok Celine, now could you also
    # add 2 more tasks to the list, one is...") and it fell through to
    # Intent.unknown, entirely undetected, since nothing else here matched.
    r"|\badd\b(?:\s+\w+){0,3}?\s+tasks?\b(?:\s+to\s+(?:the|my)\s+list)?\s*",
    re.IGNORECASE,
)
_CREATE_INTENT_RE = re.compile(
    r"\bremind\b|\breminder\b|^add (?:a )?task\b|^create (?:a )?task\b|^i need to\b|^schedule\b|^set a reminder\b"
    r"|\badd\b(?:\s+\w+){0,3}?\s+tasks?\b",
    re.IGNORECASE,
)
_LIST_INTENT_RE = re.compile(
    r"\b(?:show|list|display)\b.*\btasks?\b"
    r"|what(?:'s| is| are)\b.*\b(?:tasks?|to-?do)\b"
    r"|\bwhat do i have\b",
    re.IGNORECASE,
)
_COMPLETE_INTENT_RE = re.compile(
    r"\bmark\b.*\b(?:as\s+)?(?:done|complete|completed|finished)\b"
    r"|^i (?:finished|completed|did)\b"
    r"|^(?:complete|finish)\b",
    re.IGNORECASE,
)
_DELETE_INTENT_RE = re.compile(r"^(?:delete|remove|cancel)\b", re.IGNORECASE)
# "reschedule"/"postpone"/"push back" are unambiguous verbs in this domain
# regardless of position ("can u reschedule..."); "update"/"edit" are more
# generic English verbs, so they're anchored at the start to avoid matching
# incidentally inside some other request.
_UPDATE_INTENT_RE = re.compile(
    r"\b(?:reschedule|postpone|push back)\b|^(?:update|edit)\b", re.IGNORECASE
)
_TIME_GREETING = r"good (?:morning|afternoon|evening)"
_GREETING_RE = re.compile(
    rf"^(?:hi|hello|hey|yo|sup|howdy|{_TIME_GREETING})"
    rf"(?:[\s,]+\w+)?"  # optional name, e.g. "Hi Serene"
    rf"(?:[\s,]+{_TIME_GREETING})?"  # optional trailing "...  good morning"
    rf"[\s!.,]*$",
    re.IGNORECASE,
)
_NAME_QUERY_RE = re.compile(
    r"^what(?:'s| is) your name\??$|^what should i call you\??$", re.IGNORECASE
)
_THANKS_RE = re.compile(
    r"^(?:thanks?|thank\s+you|thx|ty|much\s+appreciated|appreciate\s+it)\b", re.IGNORECASE
)
_QUESTION_RE = re.compile(
    r"^(?:what|when|where|why|how|who|which|is|are|was|were|do|does|did|can|could|will|would|should)\b",
    re.IGNORECASE,
)
_SET_NAME_RE = re.compile(
    # "call(ing)?" so "can I start calling u X" / "can I call u X" both
    # match — the plain "call" (no "-ing") was too rigid to catch the
    # equally natural "start calling" phrasing.
    r"^(?:can|could|may) i (?:start |begin )?call(?:ing)? (?:you|u)\s+(.+?)[\?\.!]*$"
    r"|^(?:i'?ll|i will|i want to)(?:\s+start|\s+begin)? call(?:ing)? (?:you|u)\s+(.+?)[\?\.!]*$"
    r"|^(?:start |begin )?call(?:ing)? (?:you|u)\s+(.+?)[\?\.!]*$"
    r"|^(?:your name is|you'?re now called|you are now called)\s+(.+?)[\?\.!]*$",
    re.IGNORECASE,
)
_NAME_TRAILING_FILLER_RE = re.compile(
    r"\s+(?:from now on|from now|now on|onwards|onward|now|please)$", re.IGNORECASE
)


def _clean_proposed_name(name: str) -> str:
    name = name.strip(" \"'")
    while True:
        stripped = _NAME_TRAILING_FILLER_RE.sub("", name).strip(" \"'")
        if stripped == name:
            break
        name = stripped
    return name

_TRAILING_CONNECTOR_RE = re.compile(
    r"\s+(?:on|at|by|for|every|this|next|that|to)$", re.IGNORECASE
)
_LEADING_CONNECTOR_RE = re.compile(
    r"^(?:on|at|by|for|every|this|next|that|to)\s+", re.IGNORECASE
)
_LEADING_ARTICLE_RE = re.compile(r"^(?:my|the)\s+", re.IGNORECASE)
_TRAILING_NOUN_RE = re.compile(r"\s+(?:task|reminder)$", re.IGNORECASE)

_CLAUSE_SPLIT_RE = re.compile(
    r"\bafter which\b|\band then\b|\bso that\b|,?\s*\bthen\b"
    r"|\band (?:i(?:'ve| have)?\s+)?also\b"
    # Bare "and", and a plain sentence boundary, are deliberately
    # last/least specific — either is just as likely to land in the
    # middle of unrelated phrasing ("buy milk and eggs", "It's due
    # Friday. Thanks!") as between two real events. Splitting on them is
    # only safe because of how the caller uses the result: a segment
    # that doesn't resolve to its own title + explicit time is dropped
    # rather than voiding the whole split (see parse()), so a stray
    # non-event segment just disappears instead of forcing a fallback.
    r"|\band\b|\.\s+(?=[A-Za-z])",
    re.IGNORECASE,
)
_CLAUSE_FILLER_RE = re.compile(
    r"^(?:and|so|that|also|another|other)\s+"
    r"|^followed by (?:another\s+)?"
    r"|^i(?:'ve| have| had|'ll| will)?\s+(?:got to\s+|got\s+|need to\s+|could\s+|can\s+)?"
    r"|^(?:could|can|got|have)\s+"
    r"|^an?\s+"
    r"|^the\s+",
    re.IGNORECASE,
)


def _strip_clause_filler(text: str) -> str:
    text = text.strip(" ,.")
    while True:
        stripped = _CLAUSE_FILLER_RE.sub("", text, count=1).strip(" ,.")
        if stripped == text:
            break
        text = stripped
    return text


def _split_into_clauses(text: str) -> list[str]:
    """Splits a compound message like "X at 2pm, then Y at 3pm" into its
    separate event clauses on common sequencing conjunctions.

    Deliberately conservative — no bare commas or "and" (too likely to
    misfire on innocuous phrasing like "buy milk and eggs") — so most
    single-task messages come back as a single untouched clause.
    """
    parts = _CLAUSE_SPLIT_RE.split(text)
    return [p.strip(" ,.") for p in parts if p and p.strip(" ,.")]


@dataclass
class DatePhrase:
    due_at: datetime | None
    has_explicit_time: bool
    recurrence: str | None = None


@dataclass
class TaskSpec:
    title: str
    due_at: datetime | None
    recurrence: str | None
    link: str | None


@dataclass
class ParsedMessage:
    intent: Intent
    raw_text: str
    title: str | None = None
    due_at: datetime | None = None
    date_is_ambiguous: bool = False
    recurrence: str | None = None
    task_query: str | None = None
    status_filter: TaskStatus | None = None
    due_on: date | None = None
    proposed_name: str | None = None
    link: str | None = None
    # Populated instead of the single title/due_at/... fields above when the
    # message describes several distinct events, each with its own clear
    # time (e.g. "interview at 2pm, then a shower at 3pm") — see
    # _split_into_clauses. None/empty means "just one task, use the fields
    # above as usual".
    task_specs: list[TaskSpec] | None = None


def _resolve_ordinal_day(day: int, now: datetime) -> date | None:
    """Finds the next date (today or later) whose day-of-month is `day`,
    skipping a month at a time when `day` doesn't exist in it (e.g. the
    31st in April) or has already passed this month.

    Computed directly rather than handed to dateparser — dateparser treats
    a bare low ordinal like "the 1st"/"the 3rd" as a MONTH reference, not a
    day-of-month one (confirmed live: "the 1st" resolved to next January
    1st while keeping *today's* day-of-month, not "the 1st of next
    month"), and no settings flag was found that fixes it.
    """
    if not 1 <= day <= 31:
        return None
    year, month = now.year, now.month
    for _ in range(24):  # generous cap; every real case resolves well before this
        days_in_month = calendar.monthrange(year, month)[1]
        if day <= days_in_month:
            candidate = date(year, month, day)
            if candidate >= now.date():
                return candidate
        month += 1
        if month > 12:
            month = 1
            year += 1
    return None


def _parse_date_match(match: re.Match) -> DatePhrase:
    phrase = match.group(0)
    recurrence = None
    remainder = phrase
    relative_base = clock.now()

    unit_match = _RECUR_UNIT_RE.match(phrase)
    day_match = _RECUR_DAY_RE.match(phrase)
    interval_match = _RECUR_INTERVAL_RE.match(phrase)
    next_this_day_match = _NEXT_THIS_DAY_RE.match(phrase)
    ordinal_day_match = _ORDINAL_DAY_RE.match(phrase)
    if unit_match:
        recurrence = _RECURRENCE_LABELS[unit_match.group(1).lower()]
        remainder = phrase[unit_match.end():].strip()
    elif day_match:
        recurrence = "weekly"
        remainder = phrase[len("every "):].strip()
    elif interval_match:
        count = int(interval_match.group(1))
        unit_word = interval_match.group(2).rstrip("s") + "s"  # normalize "day"/"days" -> "days"
        recurrence = f"every_{count}_{unit_word}"
        remainder = phrase[interval_match.end():].strip()
    elif next_this_day_match:
        # dateparser can't handle "next/this <weekday>" as a phrase (returns
        # None) even though the bare weekday works fine — strip the prefix.
        remainder = phrase[next_this_day_match.start(1):]
    elif ordinal_day_match:
        base_date = _resolve_ordinal_day(int(ordinal_day_match.group(1)), clock.now())
        if base_date is None:
            return DatePhrase(due_at=None, has_explicit_time=False)
        remainder = phrase[ordinal_day_match.end():].strip()
        relative_base = datetime.combine(base_date, dt_time.min)
        if not remainder:
            # No trailing time ("the 1st" alone) — the date is already
            # fully resolved, so skip dateparser rather than pass it "".
            return DatePhrase(due_at=relative_base, has_explicit_time=False)

    # dateparser also can't handle "tonight" on its own (returns None) even
    # though "today"/"tomorrow" work fine — treat it as "today" for date
    # resolution; the actual time comes from the TIME match elsewhere.
    remainder = re.sub(r"\btonight\b", "today", remainder, flags=re.IGNORECASE)

    bare_hour_match = _BARE_HOUR_RE.match(remainder.strip())
    if bare_hour_match:
        # A bare hour with no am/pm ("at 5") is genuinely ambiguous —
        # confirmed live that dateparser doesn't fail cleanly on it, it
        # confidently misparses it into a nonsensical date/year instead.
        # Infer am/pm from a nearby period-of-day word in the source
        # clause ("evening at 5" -> 5pm) when there is one; otherwise
        # don't guess — leave it unresolved rather than show a wrong time.
        period_match = _PERIOD_OF_DAY_RE.search(match.string)
        if period_match:
            remainder = remainder.strip() + _PERIOD_TO_AMPM[period_match.group(1).lower()]
        else:
            remainder = ""

    parsed = (
        dateparser.parse(
            remainder,
            settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": relative_base},
        )
        if remainder
        else None
    )
    if parsed is None and recurrence is None:
        return DatePhrase(due_at=None, has_explicit_time=False)
    if recurrence == "weekday" and parsed is not None:
        # "every weekday" shouldn't ever land its first occurrence on a
        # Saturday/Sunday just because that's the nearest future date/time —
        # push it to the next Monday instead, same as the scheduler does for
        # every occurrence after this one.
        while parsed.weekday() >= 5:
            parsed += timedelta(days=1)
    is_precise = bool(_TIME_RE.search(phrase)) or bool(_IN_OFFSET_RE.match(phrase))
    return DatePhrase(due_at=parsed, has_explicit_time=is_precise, recurrence=recurrence)


def _resolve_date_phrase(matches: list[re.Match]) -> DatePhrase:
    """Resolves the DatePhrase for a clause from all its date-phrase regex
    matches, combining a date-only match with a separate time-only match
    when the message states them apart from each other — "the next
    wednesday I got a gag party at 3pm" matches "next wednesday" and "at
    3pm" as two separate spans, since unrelated words sit between them, and
    picking only one (the old behavior) meant either the correct date or
    the correct time got silently discarded.
    """
    parsed = [_parse_date_match(m) for m in matches]
    date_only = [dp for dp in parsed if dp.due_at is not None and not dp.has_explicit_time]
    time_only = [dp for dp in parsed if dp.due_at is not None and dp.has_explicit_time]
    if len(date_only) == 1 and len(time_only) == 1:
        combined = datetime.combine(date_only[0].due_at.date(), time_only[0].due_at.time())
        return DatePhrase(
            due_at=combined,
            has_explicit_time=True,
            recurrence=date_only[0].recurrence or time_only[0].recurrence,
        )
    # Otherwise, prefer whichever single match actually resolves with an
    # explicit time or a recurrence over an earlier bare relative word that
    # just happens to appear first in the sentence — e.g. "tasks to work on
    # today, then an interview at 2pm" shouldn't lock onto "today" (no time
    # of its own) when "2pm" later in the same sentence is the real due time.
    for dp in parsed:
        if dp.has_explicit_time:
            return dp
    for dp in parsed:
        if dp.recurrence is not None:
            return dp
    return parsed[0]


def _count_explicit_time_phrases(text: str) -> int:
    """How many distinct date phrases in `text` resolve with their own
    explicit time — used as a cheap signal for "this message probably
    describes multiple events" when deciding whether it's worth escalating
    to LLM-based segmentation (see parse()).
    """
    return sum(1 for m in _DATE_PHRASE_RE.finditer(text) if _parse_date_match(m).has_explicit_time)


def _extract_date_phrase(text: str) -> DatePhrase:
    matches = list(_DATE_PHRASE_RE.finditer(text))
    if not matches:
        return DatePhrase(due_at=None, has_explicit_time=False)
    return _resolve_date_phrase(matches)


def extract_time_phrase(text: str) -> str | None:
    """Pulls out just the bare clock-time portion of a reply (e.g. "10am"
    out of "10am in the morning"), or None if there isn't one.

    Used when answering a "what time...?" follow-up question, where
    dateparser is handed the user's raw reply directly rather than going
    through the usual regex-extracted phrase — dateparser can fail outright
    on redundant/conversational padding around an otherwise clear time
    ("10am in the morning" doesn't parse at all, even though "10am" alone
    does) instead of just ignoring it.
    """
    match = _TIME_RE.search(text)
    return match.group(0) if match else None


def _clean_title(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    while True:
        # Trailing punctuation has to go first each pass, not just at the
        # very end — "...Erza to tomorrow 9pm?" leaves "...Erza to ?" once
        # the date phrase is removed, and with "?" still there "to" isn't
        # at the true end of the string, so the connector strip below never
        # gets a chance to see it and match.
        stripped = text.strip(" .!?")
        stripped = _TRAILING_CONNECTOR_RE.sub("", stripped).strip()
        stripped = _LEADING_CONNECTOR_RE.sub("", stripped).strip()
        if stripped == text:
            break
        text = stripped
    return text.strip(" .!?")


def _split_on_date_phrase(text: str) -> tuple[str, DatePhrase]:
    matches = list(_DATE_PHRASE_RE.finditer(text))
    if not matches:
        return _clean_title(text), DatePhrase(due_at=None, has_explicit_time=False)
    date_phrase = _resolve_date_phrase(matches)
    # Strip every matched date/time phrase from the title, not just the one
    # that ended up determining the due date — a date-only match and a
    # separate time-only match both get combined above into a single
    # due_at, but both still need removing from the text, or the unused
    # one's words are left sitting in the title.
    remaining = text
    for m in sorted(matches, key=lambda m: m.start(), reverse=True):
        remaining = remaining[: m.start()] + " " + remaining[m.end():]
    return _clean_title(remaining), date_phrase


def _clean_task_reference(text: str) -> str:
    text = _LEADING_ARTICLE_RE.sub("", text)
    text = _TRAILING_NOUN_RE.sub("", text)
    return text.strip(" .!?")


def _classify_intent(text: str) -> Intent:
    if _GREETING_RE.search(text):
        return Intent.greeting
    if _THANKS_RE.match(text):
        return Intent.thanks
    if _NAME_QUERY_RE.match(text) or _SET_NAME_RE.match(text):
        return Intent.set_name
    # Explicit keyword matches (e.g. "remind"/"reminder", "delete", "mark ...
    # done") are unambiguous in this domain, so they take priority over the
    # zero-shot classifier — HF is only consulted for phrasing that doesn't
    # contain one of these deterministic signals (casual chat, indirect
    # requests), where it's actually needed to disambiguate intent.
    if _DELETE_INTENT_RE.search(text):
        return Intent.delete_task
    if _UPDATE_INTENT_RE.search(text):
        return Intent.update_task
    if _COMPLETE_INTENT_RE.search(text):
        return Intent.complete_task
    if _LIST_INTENT_RE.search(text):
        return Intent.list_tasks
    if _CREATE_INTENT_RE.search(text):
        return Intent.create_task
    hf_intent = classify_intent_hf(text)
    if hf_intent is not None:
        return hf_intent
    # Last resort before giving up entirely: none of the explicit triggers
    # matched AND the zero-shot classifier didn't return anything (HF
    # unconfigured, unavailable, or its own confidence too low) — rather
    # than surface "I didn't understand" for every phrasing that doesn't
    # happen to contain "remind"/"schedule"/etc., a message that mentions a
    # real date/time and isn't phrased as a question ("I've got a dentist
    # appointment Friday at 2", "meeting with the team tomorrow at noon")
    # is overwhelmingly more likely describing something to remind the
    # user about than anything else a reminder bot would be asked. A
    # trailing "?" or a leading question word is excluded, since those
    # usually mean the user is asking about an existing plan, not stating
    # a new one.
    if looks_like_new_event(text):
        return Intent.create_task
    return Intent.unknown


def has_strong_intent_trigger(text: str) -> bool:
    """True if `text` contains one of the deterministic keyword triggers
    above (remind/reminder, delete/remove/cancel, reschedule/update/edit,
    mark...done, show/list tasks) — the same signals _classify_intent
    treats as unambiguous.

    Used to tell a genuinely new command apart from the answer to a
    pending follow-up question ("what time...?", "which task...?") when
    the new command happens to also contain something that would
    otherwise look like a valid answer — a parseable time, or a word
    overlapping a candidate task's title — and would otherwise get
    silently swallowed into the old pending question instead of being
    treated as its own command.
    """
    return bool(
        _DELETE_INTENT_RE.search(text)
        or _UPDATE_INTENT_RE.search(text)
        or _COMPLETE_INTENT_RE.search(text)
        or _LIST_INTENT_RE.search(text)
        or _CREATE_INTENT_RE.search(text)
    )


def _strip_create_trigger(text: str) -> str:
    for trigger in _CREATE_TRIGGERS:
        match = re.match(trigger, text, re.IGNORECASE)
        if match:
            return text[match.end():]
    match = _CREATE_TRIGGER_ANYWHERE_RE.search(text)
    if match:
        before = text[: match.start()].strip(" ,.")
        after = text[match.end():].strip(" ,.")
        # Whichever side actually contains a date/time phrase is the real
        # content — a trailing "for me on these tasks?" can run past the
        # old 3-word filler cutoff (it's 5 words) while still being pure
        # filler with zero task info, silently discarding a "before" that
        # has every event and time in the message. Word count alone can't
        # tell those apart; an explicit-time signal can.
        before_has_time = bool(_DATE_PHRASE_RE.search(before))
        after_has_time = bool(_DATE_PHRASE_RE.search(after))
        if before_has_time and not after_has_time:
            return before
        if after_has_time and not before_has_time:
            return after
        # Neither (or both) sides have a time signal — fall back to the
        # original heuristic: the trigger phrase can trail AFTER the real
        # content instead of leading it ("...birthday party at 5:30pm. Can u
        # put a reminder for me") — taking "after" unconditionally produced
        # junk titles like "me" in that case. Use whichever side actually
        # has substance; a short trailing "for me"/"please" is exactly the
        # filler this is meant to strip, not the task itself.
        if len(after.split()) < 3 and len(before.split()) > len(after.split()):
            return before
        return after
    return text


def _build_task_specs(clauses: list[str]) -> list[TaskSpec]:
    """Turns candidate event snippets (from regex clause-splitting or LLM
    segmentation) into TaskSpecs, keeping only the ones that resolve their
    own clear title + explicit time.

    A snippet that doesn't is dropped rather than voiding the whole batch —
    it's usually connective framing ("I've got a few things to do today")
    or trailing filler ("could u please"), not a real event that's just
    missing a time. Callers decide whether enough survived (2+) to commit
    to a multi-task result; a lone survivor would need per-clause
    clarification, which the single-slot pending-clarification flow can't
    express, so that falls back to treating the whole message as one task.
    """
    specs = []
    for clause in clauses:
        # Applied here rather than only at the regex-clause-splitting stage,
        # so an LLM-segmented snippet — which is copied verbatim from the
        # message per its prompt, filler included ("I also have a college
        # union party...") — gets the exact same cleanup as a regex clause
        # instead of leaking that filler straight into the task title.
        clause = _strip_clause_filler(clause)
        url_match = _URL_RE.search(clause)
        link = url_match.group(0).rstrip(".,;:!?") if url_match else None
        if url_match:
            clause = clause[: url_match.start()] + clause[url_match.end():]
        title, date_phrase = _split_on_date_phrase(clause)
        # A second pass — a date phrase removed from the *middle* of a
        # clause ("next wednesday I got a gag party at 3pm" -> "I got a gag
        # party") exposes filler that was never at the start until now, so
        # it survives the first pass (applied before the date was removed)
        # untouched.
        title = _strip_clause_filler(title)
        if not title or date_phrase.due_at is None or not date_phrase.has_explicit_time:
            continue
        specs.append(
            TaskSpec(title=title, due_at=date_phrase.due_at, recurrence=date_phrase.recurrence, link=link)
        )
    return specs


def looks_like_new_event(text: str) -> bool:
    """True if `text` mentions a real date/time and isn't phrased as a
    question — the same signal _classify_intent's own last-resort
    create_task fallback uses (see there for the reasoning).

    Exposed so a caller with more context than parse() has (chat.py has a
    database; parse() deliberately doesn't) can use it as a second-chance
    check: when an HF-classified complete/delete/update intent turns up no
    matching task, a message that looks like this was probably just
    describing a new event, not referencing an existing one.
    """
    return bool(
        _DATE_PHRASE_RE.search(text) and not _QUESTION_RE.match(text) and not text.rstrip().endswith("?")
    )


def parse(text: str, bot_name: str | None = None, force_intent: Intent | None = None) -> ParsedMessage:
    text = text.strip()
    if bot_name:
        # "Serene, I have an interview..." / "Serene, may I call u Celine?" —
        # a leading vocative address breaks every intent regex anchored at
        # the start of the string (^), which is most of them. Strip it
        # before classifying anything else.
        text = re.sub(rf"^{re.escape(bot_name)}\s*[,!]\s*", "", text, count=1, flags=re.IGNORECASE)
    # force_intent skips classification entirely — used to re-run the same
    # raw text through the create_task extraction logic specifically (see
    # looks_like_new_event) without a second, possibly-inconsistent call to
    # the zero-shot classifier.
    intent = force_intent or _classify_intent(text)

    if intent == Intent.create_task:
        remainder = _strip_create_trigger(text)

        clauses = _split_into_clauses(remainder)
        specs = _build_task_specs(clauses)
        time_phrase_count = _count_explicit_time_phrases(remainder)
        if len(specs) < time_phrase_count:
            # The regex clause-splitter only recognizes a fixed set of
            # conjunctions/sentence boundaries — it can miss genuinely novel
            # phrasing entirely (0 specs), or under-split it (e.g. two
            # events joined by a bare comma with no "and"/"then" land in
            # the same clause, merging into one garbled spec with only one
            # of their two times). Either way, finding fewer specs than
            # there are explicit-time phrases in the message is a strong,
            # cheap-to-check signal that events are still being missed, so
            # it's worth the one extra HF call to ask a small LLM to segment
            # the text (never to compute a date itself — see hf_segment.py)
            # and re-run the exact same verified title/time extraction on
            # what it returns.
            llm_segments = segment_events_hf(remainder)
            if llm_segments and len(llm_segments) > 1:
                llm_specs = _build_task_specs(llm_segments)
                if len(llm_specs) > len(specs):
                    specs = llm_specs
        if len(specs) > 1:
            return ParsedMessage(intent=intent, raw_text=text, task_specs=specs)
        if len(specs) == 1 and len(clauses) > 1:
            # The regex splitter found more than one distinct clause, but
            # only one had both a title and an explicit time — the other(s)
            # mentioned a date with no time at all ("this Monday", nothing
            # else) and got dropped rather than guessed at (see
            # _build_task_specs). Use the one clean spec directly instead
            # of falling through to reprocess the *whole* original message
            # below as if it were a single task — that path has no idea a
            # clause was already split off, and merges the dropped clause's
            # leftover words right back into the title.
            return ParsedMessage(intent=intent, raw_text=text, task_specs=specs)

        url_match = _URL_RE.search(remainder)
        link = url_match.group(0).rstrip(".,;:!?") if url_match else None
        if url_match:
            remainder = remainder[: url_match.start()] + remainder[url_match.end():]
        title, date_phrase = _split_on_date_phrase(remainder)
        # Same second pass as _build_task_specs — a date phrase removed
        # from the middle of the remainder can expose filler ("I got a")
        # that was never at the start until now.
        title = _strip_clause_filler(title)
        ambiguous = (date_phrase.due_at is not None and not date_phrase.has_explicit_time) or (
            date_phrase.recurrence is not None and date_phrase.due_at is None
        )
        return ParsedMessage(
            intent=intent,
            raw_text=text,
            title=title or None,
            due_at=date_phrase.due_at,
            date_is_ambiguous=ambiguous,
            recurrence=date_phrase.recurrence,
            link=link,
        )

    if intent == Intent.list_tasks:
        status_filter = None
        lowered = text.lower()
        if "completed" in lowered or "done" in lowered:
            status_filter = TaskStatus.completed
        elif "pending" in lowered or "open" in lowered or "outstanding" in lowered:
            status_filter = TaskStatus.pending
        date_phrase = _extract_date_phrase(text)
        return ParsedMessage(
            intent=intent,
            raw_text=text,
            status_filter=status_filter,
            due_on=date_phrase.due_at.date() if date_phrase.due_at else None,
        )

    if intent == Intent.complete_task:
        remainder = re.sub(
            r"^(?:mark|i finished|i completed|i did|complete|finish)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )
        remainder = re.sub(
            r"\s+(?:as\s+)?(?:done|complete|completed|finished)$",
            "",
            remainder,
            flags=re.IGNORECASE,
        )
        return ParsedMessage(
            intent=intent, raw_text=text, task_query=_clean_task_reference(remainder) or None
        )

    if intent == Intent.delete_task:
        remainder = re.sub(r"^(?:delete|remove|cancel)\s+", "", text, flags=re.IGNORECASE)
        return ParsedMessage(
            intent=intent, raw_text=text, task_query=_clean_task_reference(remainder) or None
        )

    if intent == Intent.update_task:
        # "can u reschedule my dinner date with Ms. Erza to tomorrow 9pm?" —
        # the trigger word can be anywhere in the message (not just at the
        # start), so take everything after it rather than assuming an
        # anchored prefix. The same date-phrase extraction used for
        # create_task pulls out the new time; whatever's left (after the
        # same title/reference cleanup used for complete_task/delete_task)
        # is which existing task to look up.
        trigger_match = _UPDATE_INTENT_RE.search(text)
        remainder = text[trigger_match.end():].strip() if trigger_match else text
        query_text, date_phrase = _split_on_date_phrase(remainder)
        ambiguous = date_phrase.due_at is not None and not date_phrase.has_explicit_time
        return ParsedMessage(
            intent=intent,
            raw_text=text,
            task_query=_clean_task_reference(query_text) or None,
            due_at=date_phrase.due_at,
            date_is_ambiguous=ambiguous,
            recurrence=date_phrase.recurrence,
        )

    if intent == Intent.greeting:
        return ParsedMessage(intent=intent, raw_text=text)

    if intent == Intent.thanks:
        return ParsedMessage(intent=intent, raw_text=text)

    if intent == Intent.set_name:
        match = _SET_NAME_RE.match(text)
        proposed_name = None
        if match:
            proposed_name = next((g for g in match.groups() if g), None)
            if proposed_name:
                proposed_name = _clean_proposed_name(proposed_name)
        return ParsedMessage(intent=intent, raw_text=text, proposed_name=proposed_name or None)

    return ParsedMessage(intent=Intent.unknown, raw_text=text)
