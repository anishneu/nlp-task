import concurrent.futures
import re
from datetime import date, datetime, time

import dateparser
from sqlalchemy.orm import Session

from app import clock, crud
from app.config import HF_REPLY_ENABLED
from app.models import ClarificationKind, MessageRole, PendingClarification, Task, TaskStatus
from app.nlp import phrasing
from app.nlp.hf_reply import generate_title, rephrase_reply, summarize_task_title
from app.nlp.hf_similarity import find_best_match_hf
from app.nlp.intents import Intent
from app.nlp.parser import (
    ParsedMessage,
    extract_time_phrase,
    has_strong_intent_trigger,
    looks_like_new_event,
    parse,
    split_compound_actions,
)
from app.schemas import ChatResponse, TaskCreate, TaskOut, TaskUpdate

_ORDINAL_WORDS = {
    "first": 0, "1st": 0, "1": 0,
    "second": 1, "2nd": 1, "2": 1,
    "third": 2, "3rd": 2, "3": 2,
    "fourth": 3, "4th": 3, "4": 3,
}
_STOPWORDS = {"the", "a", "an", "one", "task", "reminder", "that", "this", "please", "my", "it"}


def _format_due(due_at) -> str:
    return due_at.strftime("%a, %b %d at %I:%M %p") if due_at else ""


_RECURRENCE_PHRASING = {
    "daily": "daily",
    "weekly": "weekly",
    "monthly": "monthly",
    "yearly": "yearly",
    "weekday": "on weekdays",
}
_CUSTOM_INTERVAL_RE = re.compile(r"^every_(\d+)_(days|weeks|months)$")


def _format_recurrence(recurrence: str) -> str:
    if recurrence in _RECURRENCE_PHRASING:
        return _RECURRENCE_PHRASING[recurrence]
    match = _CUSTOM_INTERVAL_RE.match(recurrence)
    if match:
        count, unit = int(match.group(1)), match.group(2)
        if count == 1:
            unit = unit.rstrip("s")
        return f"every {count} {unit}"
    return recurrence


def _format_confirmation(title: str, due_at, recurrence: str | None, link: str | None) -> str:
    when = f" for {_format_due(due_at)}" if due_at else ""
    repeats = f", repeating {_format_recurrence(recurrence)}" if recurrence else ""
    link_note = f" Join here: {link}" if link else ""
    return phrasing.pick(phrasing.CONFIRM_TASK, title=title, when=when, repeats=repeats, link_note=link_note)


def _format_rescheduled(task: Task) -> str:
    return phrasing.pick(phrasing.RESCHEDULED, title=task.title, due=_format_due(task.due_at))


def _format_deleted(title: str) -> str:
    return phrasing.pick(phrasing.DELETED, title=title)


def _polish_title(raw_title: str) -> str:
    """Runs a single task title through summarize_task_title(), falling
    back to the regex-cleaned title as-is if HF is off/unavailable.
    """
    return summarize_task_title(raw_title) or raw_title


def _polish_titles(raw_titles: list[str]) -> list[str]:
    """Same as _polish_title, but for several titles at once (a multi-task
    message) — fired concurrently so N titles cost roughly one call's worth
    of wall-clock time instead of N sequential round-trips.
    """
    if not HF_REPLY_ENABLED or not raw_titles:
        return raw_titles
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(raw_titles)) as pool:
        results = list(pool.map(summarize_task_title, raw_titles))
    return [polished or raw for polished, raw in zip(results, raw_titles)]


def _handle_create_task(db: Session, parsed: ParsedMessage, conversation_id: str | None) -> ChatResponse:
    """Handles an already-parsed create_task message — factored out of the
    main create_task branch so the complete/delete/update branch can also
    call it directly on a retry (see looks_like_new_event in
    _process_message), reusing the exact same task-creation logic instead
    of a second, subtly-different copy of it.
    """
    if parsed.task_specs:
        polished_titles = _polish_titles([s.title for s in parsed.task_specs])
        tasks = [
            crud.create_task(
                db,
                TaskCreate(title=title, due_at=s.due_at, recurrence=s.recurrence, link=s.link),
            )
            for s, title in zip(parsed.task_specs, polished_titles)
        ]
        lines = [f'- "{t.title}" for {_format_due(t.due_at)}' for t in tasks]
        noun = "task" if len(tasks) == 1 else "tasks"
        reply = phrasing.pick(phrasing.CONFIRM_MULTI, n=len(tasks), noun=noun, lines="\n".join(lines))
        return ChatResponse(
            reply=reply,
            intent=Intent.create_task.value,
            tasks=[TaskOut.model_validate(t) for t in tasks],
        )
    if not parsed.title:
        return ChatResponse(
            reply=phrasing.pick(phrasing.ASK_TITLE),
            intent=Intent.create_task.value,
        )
    if parsed.date_is_ambiguous:
        base_date = parsed.due_at.date() if parsed.due_at else clock.now().date()
        if conversation_id:
            crud.set_pending(
                db,
                conversation_id,
                kind=ClarificationKind.awaiting_time,
                title=parsed.title,
                base_date=base_date.isoformat(),
                recurrence=parsed.recurrence,
                link=parsed.link,
            )
        return ChatResponse(
            reply=phrasing.pick(phrasing.ASK_TIME, title=parsed.title),
            intent=Intent.create_task.value,
        )
    task = crud.create_task(
        db,
        TaskCreate(
            title=_polish_title(parsed.title),
            due_at=parsed.due_at,
            recurrence=parsed.recurrence,
            link=parsed.link,
        ),
    )
    return ChatResponse(
        reply=_format_confirmation(task.title, task.due_at, task.recurrence, task.link),
        intent=Intent.create_task.value,
        task=TaskOut.model_validate(task),
    )


def _try_execute_action_clause(db: Session, parsed: ParsedMessage) -> str:
    """Fully executes one clause of a compound multi-action message (see
    split_compound_actions) with no follow-up questions — a compound
    message commits to resolving every action outright; a clause that
    can't (task not found, more than one match, no time given for a
    reschedule) is reported as such rather than kicking off a multi-turn
    clarification for just one of several actions, which the single-slot
    pending-clarification system has no good way to represent anyway.

    Always returns a one-line result — success or explained failure —
    never raises, so the caller can join every clause's line into one
    combined reply regardless of how many of them actually went through.
    """
    if parsed.intent == Intent.create_task:
        if parsed.task_specs or not parsed.title or parsed.date_is_ambiguous:
            return "couldn't tell what to create from that part"
        task = crud.create_task(
            db,
            TaskCreate(
                title=_polish_title(parsed.title),
                due_at=parsed.due_at,
                recurrence=parsed.recurrence,
                link=parsed.link,
            ),
        )
        return f'created "{task.title}" for {_format_due(task.due_at)}'

    if parsed.intent == Intent.list_tasks:
        return "listing tasks isn't supported alongside other actions in one message — ask separately"

    if not parsed.task_query:
        return "wasn't clear which task that part meant"
    matches = crud.find_tasks_by_title(db, parsed.task_query)
    if not matches:
        pending_tasks = crud.list_tasks(db, status=TaskStatus.pending)
        hf_index = find_best_match_hf(parsed.task_query, [t.title for t in pending_tasks])
        if hf_index is not None:
            matches = [pending_tasks[hf_index]]
    if not matches:
        return f'couldn\'t find a task matching "{parsed.task_query}"'
    if len(matches) > 1:
        return f'found more than one task matching "{parsed.task_query}", so skipped it'
    task = matches[0]
    if parsed.intent == Intent.complete_task:
        task = crud.update_task(db, task, TaskUpdate(status=TaskStatus.completed))
        return f'marked "{task.title}" as completed'
    if parsed.intent == Intent.delete_task:
        title = task.title
        crud.delete_task(db, task)
        return f'deleted "{title}"'
    if parsed.intent == Intent.update_task:
        if parsed.due_at is None or parsed.date_is_ambiguous:
            return f'wasn\'t given a clear time to reschedule "{task.title}" to, so skipped it'
        task = crud.update_task(db, task, TaskUpdate(due_at=parsed.due_at, recurrence=parsed.recurrence))
        return f'rescheduled "{task.title}" to {_format_due(task.due_at)}'
    return "couldn't figure out that part"


def _keywords(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.lower()) if w not in _STOPWORDS}


def _resolve_choice(text: str, candidates: list[Task]) -> Task | None:
    lowered = text.strip().lower()
    index = _ORDINAL_WORDS.get(lowered)
    if index is not None and index < len(candidates):
        return candidates[index]

    hf_index = find_best_match_hf(text, [c.title for c in candidates])
    if hf_index is not None:
        return candidates[hf_index]

    direct = [c for c in candidates if lowered in c.title.lower() or c.title.lower() in lowered]
    if len(direct) == 1:
        return direct[0]

    query_words = _keywords(lowered)
    if not query_words:
        return None
    scored = [
        (len(query_words & _keywords(c.title)), c)
        for c in candidates
    ]
    scored = [(score, c) for score, c in scored if score > 0]
    if not scored:
        return None
    scored.sort(key=lambda pair: -pair[0])
    if len(scored) == 1 or scored[0][0] > scored[1][0]:
        return scored[0][1]
    return None


def _handle_followup(
    db: Session, pending: PendingClarification, text: str, conversation_id: str
) -> ChatResponse | None:
    # A message carrying its own strong command trigger ("schedule...",
    # "remind me...", "delete...") is a fresh command, not an answer to the
    # pending question — even if it happens to also contain a parseable
    # time (extract_time_phrase below would find "3pm" in "schedule a
    # meeting with team tomorrow at 3pm" just fine) or overlap a candidate
    # task's title. Bail out so it falls through to be processed as a new
    # command instead of getting silently swallowed into the old one.
    if has_strong_intent_trigger(text):
        return None

    if pending.kind == ClarificationKind.awaiting_time:
        base_date = date.fromisoformat(pending.base_date)
        # Try the bare extracted time first — "10am in the morning" fails
        # to parse at all as a whole (dateparser chokes on the redundant
        # "in the morning"), even though "10am" alone parses cleanly. Falls
        # back to the raw reply for anything that isn't a bare clock time
        # (e.g. "tomorrow"), same as before.
        time_phrase = extract_time_phrase(text) or text
        parsed_dt = dateparser.parse(
            time_phrase,
            settings={"RELATIVE_BASE": datetime.combine(base_date, time.min), "PREFER_DATES_FROM": "future"},
        )
        if parsed_dt is None:
            return None
        if pending.action == Intent.update_task.value:
            task_id = int(pending.candidate_ids) if pending.candidate_ids else None
            task = crud.get_task(db, task_id) if task_id else None
            if task is None:
                return None
            task = crud.update_task(db, task, TaskUpdate(due_at=parsed_dt, recurrence=pending.recurrence))
            return ChatResponse(
                reply=_format_rescheduled(task),
                intent=pending.action,
                task=TaskOut.model_validate(task),
            )
        task = crud.create_task(
            db,
            TaskCreate(
                title=_polish_title(pending.title),
                due_at=parsed_dt,
                recurrence=pending.recurrence,
                link=pending.link,
            ),
        )
        return ChatResponse(
            reply=_format_confirmation(task.title, task.due_at, task.recurrence, task.link),
            intent=Intent.create_task.value,
            task=TaskOut.model_validate(task),
        )

    if pending.kind == ClarificationKind.awaiting_task_choice:
        ids = [int(x) for x in (pending.candidate_ids or "").split(",") if x]
        candidates = crud.get_tasks_by_ids(db, ids)
        chosen = _resolve_choice(text, candidates)
        if chosen is None:
            return None
        if pending.action == Intent.complete_task.value:
            task = crud.update_task(db, chosen, TaskUpdate(status=TaskStatus.completed))
            return ChatResponse(
                reply=phrasing.pick(phrasing.MARKED_DONE, title=task.title),
                intent=pending.action,
                task=TaskOut.model_validate(task),
            )
        if pending.action == Intent.update_task.value:
            if pending.pending_due_at is None:
                # Which task was ambiguous AND the new time was never given
                # ("reschedule call mom" — two matches, no time at all) —
                # resolve the first question, then chain straight into the
                # second rather than dropping it.
                crud.set_pending(
                    db,
                    conversation_id,
                    kind=ClarificationKind.awaiting_time,
                    action=Intent.update_task.value,
                    candidate_ids=str(chosen.id),
                    base_date=clock.now().date().isoformat(),
                    recurrence=pending.recurrence,
                )
                return ChatResponse(
                    reply=phrasing.pick(phrasing.ASK_RESCHEDULE_TIME_CHAINED, title=chosen.title),
                    intent=pending.action,
                )
            task = crud.update_task(
                db, chosen, TaskUpdate(due_at=pending.pending_due_at, recurrence=pending.recurrence)
            )
            return ChatResponse(
                reply=_format_rescheduled(task),
                intent=pending.action,
                task=TaskOut.model_validate(task),
            )
        crud.delete_task(db, chosen)
        return ChatResponse(reply=_format_deleted(chosen.title), intent=pending.action)

    return None


def _process_message(
    db: Session, text: str, conversation_id: str | None, bot_name: str | None
) -> ChatResponse:
    current_name = bot_name or "Celine"
    if conversation_id:
        pending = crud.get_pending(db, conversation_id)
        if pending:
            # Clear before handling, not after — _handle_followup can chain
            # into a second question (e.g. "which task?" then "what time?")
            # by setting a fresh pending state itself; clearing afterward
            # would immediately wipe that back out.
            crud.clear_pending(db, conversation_id)
            response = _handle_followup(db, pending, text, conversation_id)
            if response is not None:
                return response
            # Couldn't interpret as an answer to the pending question — treat
            # this message as a fresh command instead of getting stuck.

    compound = split_compound_actions(text, current_name)
    if compound:
        results = [_try_execute_action_clause(db, clause) for clause in compound]
        return ChatResponse(
            reply=phrasing.pick(phrasing.COMPOUND_ACTION, actions="; ".join(results)),
            intent=Intent.compound_action.value,
        )

    parsed = parse(text, current_name)

    if parsed.intent == Intent.create_task:
        return _handle_create_task(db, parsed, conversation_id)

    if parsed.intent == Intent.list_tasks:
        tasks = crud.list_tasks(db, status=parsed.status_filter)
        if parsed.due_on:
            tasks = [t for t in tasks if t.due_at and t.due_at.date() == parsed.due_on]
        if not tasks:
            return ChatResponse(reply=phrasing.pick(phrasing.NO_TASKS), intent=parsed.intent.value, tasks=[])
        lines = [
            f"- {t.title}" + (f" ({_format_due(t.due_at)})" if t.due_at else "") for t in tasks
        ]
        return ChatResponse(
            reply=phrasing.pick(phrasing.LIST_TASKS, n=len(tasks), lines="\n".join(lines)),
            intent=parsed.intent.value,
            tasks=[TaskOut.model_validate(t) for t in tasks],
        )

    if parsed.intent in (Intent.complete_task, Intent.delete_task, Intent.update_task):
        if not parsed.task_query:
            return ChatResponse(reply=phrasing.pick(phrasing.WHICH_TASK), intent=parsed.intent.value)
        matches = crud.find_tasks_by_title(db, parsed.task_query)
        if not matches:
            pending_tasks = crud.list_tasks(db, status=TaskStatus.pending)
            hf_index = find_best_match_hf(parsed.task_query, [t.title for t in pending_tasks])
            if hf_index is not None:
                matches = [pending_tasks[hf_index]]
        if not matches:
            # The zero-shot classifier can confidently — and wrongly — read
            # a plain description of a new event as a request to
            # reschedule/complete/delete something, when no regex trigger
            # for that action fired at all. Retrying as create_task means a
            # message like "I have a dentist appointment Friday at 2pm"
            # still creates the task instead of dead-ending on "I couldn't
            # find a task matching ...", which would be actively
            # misleading — the user was never trying to change anything.
            if not has_strong_intent_trigger(text) and looks_like_new_event(text):
                retry = parse(text, current_name, force_intent=Intent.create_task)
                return _handle_create_task(db, retry, conversation_id)
            return ChatResponse(
                reply=phrasing.pick(phrasing.NOT_FOUND, query=parsed.task_query),
                intent=parsed.intent.value,
            )
        # A reschedule with no resolvable time at all, or a date with no
        # time of day ("to friday"), still needs a follow-up question —
        # tracked separately from "which task" so the two can be resolved
        # in either order without losing one.
        needs_time = parsed.intent == Intent.update_task and (
            parsed.due_at is None or parsed.date_is_ambiguous
        )
        if len(matches) > 1:
            if conversation_id:
                crud.set_pending(
                    db,
                    conversation_id,
                    kind=ClarificationKind.awaiting_task_choice,
                    action=parsed.intent.value,
                    candidate_ids=",".join(str(m.id) for m in matches),
                    pending_due_at=None if needs_time else parsed.due_at,
                    recurrence=parsed.recurrence,
                )
            titles = ", ".join(f'{i + 1}) "{m.title}"' for i, m in enumerate(matches))
            return ChatResponse(
                reply=phrasing.pick(phrasing.MULTI_MATCH, titles=titles),
                intent=parsed.intent.value,
                tasks=[TaskOut.model_validate(m) for m in matches],
            )
        task = matches[0]
        if parsed.intent == Intent.complete_task:
            task = crud.update_task(db, task, TaskUpdate(status=TaskStatus.completed))
            return ChatResponse(
                reply=phrasing.pick(phrasing.MARKED_DONE, title=task.title),
                intent=parsed.intent.value,
                task=TaskOut.model_validate(task),
            )
        if parsed.intent == Intent.update_task:
            if needs_time:
                base_date = parsed.due_at.date() if parsed.due_at else clock.now().date()
                if conversation_id:
                    crud.set_pending(
                        db,
                        conversation_id,
                        kind=ClarificationKind.awaiting_time,
                        action=Intent.update_task.value,
                        candidate_ids=str(task.id),
                        base_date=base_date.isoformat(),
                        recurrence=parsed.recurrence,
                    )
                return ChatResponse(
                    reply=phrasing.pick(phrasing.ASK_RESCHEDULE_TIME, title=task.title),
                    intent=parsed.intent.value,
                )
            task = crud.update_task(
                db, task, TaskUpdate(due_at=parsed.due_at, recurrence=parsed.recurrence)
            )
            return ChatResponse(
                reply=_format_rescheduled(task),
                intent=parsed.intent.value,
                task=TaskOut.model_validate(task),
            )
        crud.delete_task(db, task)
        return ChatResponse(reply=_format_deleted(task.title), intent=parsed.intent.value)

    if parsed.intent == Intent.greeting:
        time_of_day_match = re.search(r"\bgood (morning|afternoon|evening)\b", text, re.IGNORECASE)
        greeting = f"Good {time_of_day_match.group(1).lower()}!" if time_of_day_match else "Hi there!"
        return ChatResponse(
            reply=phrasing.pick(phrasing.GREETING, greeting=greeting, name=current_name),
            intent=parsed.intent.value,
        )

    if parsed.intent == Intent.thanks:
        return ChatResponse(
            reply=phrasing.pick(phrasing.THANKS),
            intent=parsed.intent.value,
        )

    if parsed.intent == Intent.set_name:
        if parsed.proposed_name:
            return ChatResponse(
                reply=phrasing.pick(phrasing.SET_NAME_CONFIRM, name=parsed.proposed_name),
                intent=parsed.intent.value,
                bot_name=parsed.proposed_name,
            )
        return ChatResponse(
            reply=phrasing.pick(phrasing.SET_NAME_QUERY, name=current_name),
            intent=parsed.intent.value,
        )

    return ChatResponse(
        reply=phrasing.pick(phrasing.UNKNOWN),
        intent=parsed.intent.value,
    )


def handle_message(
    db: Session, text: str, conversation_id: str | None = None, bot_name: str | None = None
) -> ChatResponse:
    response = _process_message(db, text, conversation_id, bot_name)

    # The "unknown" fallback embeds a quoted usage example ("Remind me to
    # call Mom...") — small rephrasing models sometimes read that as literal
    # context and hallucinate a fact from it. "greeting"'s rephrase prompt
    # only promises to preserve *facts*, and a "Good morning!" echo isn't
    # one, so the model is free to (and did, in testing) swap it for a
    # generic "Hey there!". Both are kept deterministic instead of risking
    # that — and neither gains much from rephrasing anyway.
    needs_rephrase = HF_REPLY_ENABLED and response.intent not in (Intent.unknown.value, Intent.greeting.value)
    # A brand-new conversation also gets its title generated by an HF call
    # (same model, different prompt) the moment it sees its first user
    # message. Left sequential, that meant every new chat's first message
    # paid for two back-to-back external LLM round-trips instead of one —
    # firing them concurrently below (they don't depend on each other at
    # all) cuts that back down to roughly the cost of a single call. Skipped
    # entirely (no DB lookup either) when HF_REPLY_ENABLED is off.
    needs_title = (
        HF_REPLY_ENABLED
        and bool(conversation_id)
        and crud.get_or_create_conversation(db, conversation_id).title is None
    )

    title = None
    if needs_rephrase and needs_title:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            rephrase_future = pool.submit(rephrase_reply, bot_name or "Celine", response.reply)
            title_future = pool.submit(generate_title, text)
            response.reply = rephrase_future.result()
            title = title_future.result()
    else:
        if needs_rephrase:
            response.reply = rephrase_reply(bot_name or "Celine", response.reply)
        if needs_title:
            title = generate_title(text)

    if conversation_id:
        crud.add_message(db, conversation_id, MessageRole.user, text, title=title)
        crud.add_message(db, conversation_id, MessageRole.bot, response.reply, response.intent)
    return response
