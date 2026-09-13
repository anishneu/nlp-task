import re
from dataclasses import dataclass
from datetime import date, datetime

import dateparser

from app.models import TaskStatus
from app.nlp.hf_intent import classify_intent_hf
from app.nlp.intents import Intent

_DAY = r"(?:mon(?:day)?|tue(?:s|sday)?|wed(?:nesday)?|thu(?:rs|rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
_NUM_WORD = r"(?:a|an|\d+)"
_TIME = r"\d{1,2}(?::\d{2})?\s*(?:am|pm)|noon|midnight"
_REL = r"today|tomorrow|tonight"
_NEXT_THIS = rf"(?:next|this)\s+(?:week|month|year|{_DAY})"
_IN_OFFSET = rf"in\s+{_NUM_WORD}\s+(?:min(?:ute)?s?|hrs?|hours?|days?|weeks?)"
_RECUR_DAY = rf"every\s+{_DAY}"
_RECUR_UNIT = r"every\s+(?:day|week|month)"
_URL_RE = re.compile(
    r"https?://\S+|(?:meet\.google\.com|zoom\.us|teams\.microsoft\.com)\S*", re.IGNORECASE
)

_DATE_PHRASE_RE = re.compile(
    rf"\b(?:{_RECUR_DAY}|{_RECUR_UNIT}|{_REL}|{_NEXT_THIS}|{_DAY}|{_IN_OFFSET})\b(?:\s+at\s+(?:{_TIME})\b)?"
    rf"|\b(?:{_TIME})\b",
    re.IGNORECASE,
)
_IN_OFFSET_RE = re.compile(rf"^{_IN_OFFSET}\b", re.IGNORECASE)
_TIME_RE = re.compile(rf"\b(?:{_TIME})\b", re.IGNORECASE)
_RECUR_DAY_RE = re.compile(rf"^every\s+{_DAY}", re.IGNORECASE)
_NEXT_THIS_DAY_RE = re.compile(rf"^(?:next|this)\s+({_DAY})", re.IGNORECASE)
_RECUR_UNIT_RE = re.compile(r"^every\s+(day|week|month)\b", re.IGNORECASE)
_RECURRENCE_LABELS = {"day": "daily", "week": "weekly", "month": "monthly"}

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
    r"\bremind me\s+(?:that|to)?\s*|\breminder\s+(?:that|to)?\s*", re.IGNORECASE
)
_CREATE_INTENT_RE = re.compile(
    r"\bremind\b|\breminder\b|^add (?:a )?task\b|^create (?:a )?task\b|^i need to\b|^schedule\b|^set a reminder\b",
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
_GREETING_RE = re.compile(
    r"^(?:hi|hello|hey|yo|sup|howdy|good morning|good afternoon|good evening)"
    r"(?:\s+\w+)?[\s!.,]*$",
    re.IGNORECASE,
)
_NAME_QUERY_RE = re.compile(
    r"^what(?:'s| is) your name\??$|^what should i call you\??$", re.IGNORECASE
)
_SET_NAME_RE = re.compile(
    r"^(?:can|could) i call (?:you|u)\s+(.+?)[\?\.!]*$"
    r"|^(?:i'?ll|i will|i want to) call (?:you|u)\s+(.+?)[\?\.!]*$"
    r"|^call (?:you|u)\s+(.+?)[\?\.!]*$"
    r"|^(?:your name is|you'?re now called|you are now called)\s+(.+?)[\?\.!]*$",
    re.IGNORECASE,
)

_TRAILING_CONNECTOR_RE = re.compile(
    r"\s+(?:on|at|by|for|every|this|next|that|to)$", re.IGNORECASE
)
_LEADING_CONNECTOR_RE = re.compile(
    r"^(?:on|at|by|for|every|this|next|that|to)\s+", re.IGNORECASE
)
_LEADING_ARTICLE_RE = re.compile(r"^(?:my|the)\s+", re.IGNORECASE)
_TRAILING_NOUN_RE = re.compile(r"\s+(?:task|reminder)$", re.IGNORECASE)


@dataclass
class DatePhrase:
    due_at: datetime | None
    has_explicit_time: bool
    recurrence: str | None = None


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


def _parse_date_match(match: re.Match) -> DatePhrase:
    phrase = match.group(0)
    recurrence = None
    remainder = phrase

    unit_match = _RECUR_UNIT_RE.match(phrase)
    day_match = _RECUR_DAY_RE.match(phrase)
    next_this_day_match = _NEXT_THIS_DAY_RE.match(phrase)
    if unit_match:
        recurrence = _RECURRENCE_LABELS[unit_match.group(1).lower()]
        remainder = phrase[unit_match.end():].strip()
    elif day_match:
        recurrence = "weekly"
        remainder = phrase[len("every "):].strip()
    elif next_this_day_match:
        # dateparser can't handle "next/this <weekday>" as a phrase (returns
        # None) even though the bare weekday works fine — strip the prefix.
        remainder = phrase[next_this_day_match.start(1):]

    parsed = dateparser.parse(remainder, settings={"PREFER_DATES_FROM": "future"}) if remainder else None
    if parsed is None and recurrence is None:
        return DatePhrase(due_at=None, has_explicit_time=False)
    is_precise = bool(_TIME_RE.search(phrase)) or bool(_IN_OFFSET_RE.match(phrase))
    return DatePhrase(due_at=parsed, has_explicit_time=is_precise, recurrence=recurrence)


def _extract_date_phrase(text: str) -> DatePhrase:
    match = _DATE_PHRASE_RE.search(text)
    if not match:
        return DatePhrase(due_at=None, has_explicit_time=False)
    return _parse_date_match(match)


def _clean_title(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    while True:
        stripped = _TRAILING_CONNECTOR_RE.sub("", text).strip()
        stripped = _LEADING_CONNECTOR_RE.sub("", stripped).strip()
        if stripped == text:
            break
        text = stripped
    return text.strip(" .!?")


def _split_on_date_phrase(text: str) -> tuple[str, DatePhrase]:
    match = _DATE_PHRASE_RE.search(text)
    if not match:
        return _clean_title(text), DatePhrase(due_at=None, has_explicit_time=False)
    date_phrase = _parse_date_match(match)
    remaining = text[: match.start()] + " " + text[match.end():]
    return _clean_title(remaining), date_phrase


def _clean_task_reference(text: str) -> str:
    text = _LEADING_ARTICLE_RE.sub("", text)
    text = _TRAILING_NOUN_RE.sub("", text)
    return text.strip(" .!?")


def _classify_intent(text: str) -> Intent:
    if _GREETING_RE.search(text):
        return Intent.greeting
    if _NAME_QUERY_RE.match(text) or _SET_NAME_RE.match(text):
        return Intent.set_name
    hf_intent = classify_intent_hf(text)
    if hf_intent is not None:
        return hf_intent
    if _DELETE_INTENT_RE.search(text):
        return Intent.delete_task
    if _COMPLETE_INTENT_RE.search(text):
        return Intent.complete_task
    if _LIST_INTENT_RE.search(text):
        return Intent.list_tasks
    if _CREATE_INTENT_RE.search(text):
        return Intent.create_task
    return Intent.unknown


def _strip_create_trigger(text: str) -> str:
    for trigger in _CREATE_TRIGGERS:
        match = re.match(trigger, text, re.IGNORECASE)
        if match:
            return text[match.end():]
    match = _CREATE_TRIGGER_ANYWHERE_RE.search(text)
    if match:
        return text[match.end():]
    return text


def parse(text: str) -> ParsedMessage:
    text = text.strip()
    intent = _classify_intent(text)

    if intent == Intent.create_task:
        remainder = _strip_create_trigger(text)
        url_match = _URL_RE.search(remainder)
        link = url_match.group(0).rstrip(".,;:!?") if url_match else None
        if url_match:
            remainder = remainder[: url_match.start()] + remainder[url_match.end():]
        title, date_phrase = _split_on_date_phrase(remainder)
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

    if intent == Intent.greeting:
        return ParsedMessage(intent=intent, raw_text=text)

    if intent == Intent.set_name:
        match = _SET_NAME_RE.match(text)
        proposed_name = None
        if match:
            proposed_name = next((g for g in match.groups() if g), None)
            if proposed_name:
                proposed_name = proposed_name.strip(" \"'")
        return ParsedMessage(intent=intent, raw_text=text, proposed_name=proposed_name or None)

    return ParsedMessage(intent=Intent.unknown, raw_text=text)
