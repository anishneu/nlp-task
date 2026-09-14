import re
from datetime import date, datetime, time

import dateparser
from sqlalchemy.orm import Session

from app import crud
from app.models import ClarificationKind, MessageRole, PendingClarification, Task, TaskStatus
from app.nlp.hf_reply import rephrase_reply
from app.nlp.hf_similarity import find_best_match_hf
from app.nlp.intents import Intent
from app.nlp.parser import parse
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


def _format_confirmation(title: str, due_at, recurrence: str | None, link: str | None) -> str:
    when = f" for {_format_due(due_at)}" if due_at else ""
    repeats = f", repeating {_RECURRENCE_PHRASING.get(recurrence, recurrence)}" if recurrence else ""
    link_note = f" Join here: {link}" if link else ""
    return f'Got it — I\'ve scheduled "{title}"{when}{repeats}.{link_note}'


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


def _handle_followup(db: Session, pending: PendingClarification, text: str) -> ChatResponse | None:
    if pending.kind == ClarificationKind.awaiting_time:
        base_date = date.fromisoformat(pending.base_date)
        parsed_dt = dateparser.parse(
            text,
            settings={"RELATIVE_BASE": datetime.combine(base_date, time.min), "PREFER_DATES_FROM": "future"},
        )
        if parsed_dt is None:
            return None
        task = crud.create_task(
            db,
            TaskCreate(
                title=pending.title,
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
                reply=f'Marked "{task.title}" as completed.',
                intent=pending.action,
                task=TaskOut.model_validate(task),
            )
        crud.delete_task(db, chosen)
        return ChatResponse(reply=f'Deleted "{chosen.title}".', intent=pending.action)

    return None


def _process_message(
    db: Session, text: str, conversation_id: str | None, bot_name: str | None
) -> ChatResponse:
    current_name = bot_name or "Custom To-Do Bot"
    if conversation_id:
        pending = crud.get_pending(db, conversation_id)
        if pending:
            response = _handle_followup(db, pending, text)
            crud.clear_pending(db, conversation_id)
            if response is not None:
                return response
            # Couldn't interpret as an answer to the pending question — treat
            # this message as a fresh command instead of getting stuck.

    parsed = parse(text)

    if parsed.intent == Intent.create_task:
        if not parsed.title:
            return ChatResponse(
                reply="What would you like the reminder to be about?",
                intent=parsed.intent.value,
            )
        if parsed.date_is_ambiguous:
            base_date = parsed.due_at.date() if parsed.due_at else date.today()
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
                reply=f'What time should I remind you to "{parsed.title}"?',
                intent=parsed.intent.value,
            )
        task = crud.create_task(
            db,
            TaskCreate(
                title=parsed.title,
                due_at=parsed.due_at,
                recurrence=parsed.recurrence,
                link=parsed.link,
            ),
        )
        return ChatResponse(
            reply=_format_confirmation(task.title, task.due_at, task.recurrence, task.link),
            intent=parsed.intent.value,
            task=TaskOut.model_validate(task),
        )

    if parsed.intent == Intent.list_tasks:
        tasks = crud.list_tasks(db, status=parsed.status_filter)
        if parsed.due_on:
            tasks = [t for t in tasks if t.due_at and t.due_at.date() == parsed.due_on]
        if not tasks:
            return ChatResponse(reply="You have no matching tasks.", intent=parsed.intent.value, tasks=[])
        lines = [
            f"- {t.title}" + (f" ({_format_due(t.due_at)})" if t.due_at else "") for t in tasks
        ]
        return ChatResponse(
            reply=f"You have {len(tasks)} task(s):\n" + "\n".join(lines),
            intent=parsed.intent.value,
            tasks=[TaskOut.model_validate(t) for t in tasks],
        )

    if parsed.intent in (Intent.complete_task, Intent.delete_task):
        if not parsed.task_query:
            return ChatResponse(reply="Which task do you mean?", intent=parsed.intent.value)
        matches = crud.find_tasks_by_title(db, parsed.task_query)
        if not matches:
            pending_tasks = crud.list_tasks(db, status=TaskStatus.pending)
            hf_index = find_best_match_hf(parsed.task_query, [t.title for t in pending_tasks])
            if hf_index is not None:
                matches = [pending_tasks[hf_index]]
        if not matches:
            return ChatResponse(
                reply=f'I couldn\'t find a task matching "{parsed.task_query}".',
                intent=parsed.intent.value,
            )
        if len(matches) > 1:
            if conversation_id:
                crud.set_pending(
                    db,
                    conversation_id,
                    kind=ClarificationKind.awaiting_task_choice,
                    action=parsed.intent.value,
                    candidate_ids=",".join(str(m.id) for m in matches),
                )
            titles = ", ".join(f'{i + 1}) "{m.title}"' for i, m in enumerate(matches))
            return ChatResponse(
                reply=f"I found multiple matching tasks: {titles}. Which one did you mean?",
                intent=parsed.intent.value,
                tasks=[TaskOut.model_validate(m) for m in matches],
            )
        task = matches[0]
        if parsed.intent == Intent.complete_task:
            task = crud.update_task(db, task, TaskUpdate(status=TaskStatus.completed))
            return ChatResponse(
                reply=f'Marked "{task.title}" as completed.',
                intent=parsed.intent.value,
                task=TaskOut.model_validate(task),
            )
        crud.delete_task(db, task)
        return ChatResponse(reply=f'Deleted "{task.title}".', intent=parsed.intent.value)

    if parsed.intent == Intent.greeting:
        return ChatResponse(
            reply=f"Hi there! I'm {current_name}, your virtual chatbot assistant. How may I help you?",
            intent=parsed.intent.value,
        )

    if parsed.intent == Intent.set_name:
        if parsed.proposed_name:
            return ChatResponse(
                reply=f"Sure, you can call me {parsed.proposed_name} from now on!",
                intent=parsed.intent.value,
                bot_name=parsed.proposed_name,
            )
        return ChatResponse(
            reply=f'You can call me {current_name}. Just say "call me <name>" to rename me.',
            intent=parsed.intent.value,
        )

    return ChatResponse(
        reply='I didn\'t understand that. Try something like "Remind me to call Mom on Friday at 6 PM."',
        intent=parsed.intent.value,
    )


def handle_message(
    db: Session, text: str, conversation_id: str | None = None, bot_name: str | None = None
) -> ChatResponse:
    response = _process_message(db, text, conversation_id, bot_name)
    if response.intent != Intent.unknown.value:
        # The "unknown" fallback embeds a quoted usage example ("Remind me
        # to call Mom...") — small rephrasing models sometimes read that as
        # literal context and hallucinate a fact from it (e.g. asking when
        # to "call Mom" in a conversation that never mentioned Mom). The
        # generic fallback doesn't gain much from rephrasing anyway, so it's
        # left as the reliable plain template instead of risking that.
        response.reply = rephrase_reply(bot_name or "Custom To-Do Bot", response.reply)
    if conversation_id:
        crud.add_message(db, conversation_id, MessageRole.user, text)
        crud.add_message(db, conversation_id, MessageRole.bot, response.reply, response.intent)
    return response
