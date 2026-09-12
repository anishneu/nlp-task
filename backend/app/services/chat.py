from sqlalchemy.orm import Session

from app import crud
from app.models import TaskStatus
from app.nlp.intents import Intent
from app.nlp.parser import parse
from app.schemas import ChatResponse, TaskCreate, TaskOut, TaskUpdate


def _format_due(due_at) -> str:
    return due_at.strftime("%a, %b %d at %I:%M %p") if due_at else ""


def handle_message(db: Session, text: str) -> ChatResponse:
    parsed = parse(text)

    if parsed.intent == Intent.create_task:
        if not parsed.title:
            return ChatResponse(
                reply="What would you like the reminder to be about?",
                intent=parsed.intent.value,
            )
        if parsed.date_is_ambiguous:
            return ChatResponse(
                reply=f'What time should I remind you to "{parsed.title}"?',
                intent=parsed.intent.value,
            )
        task = crud.create_task(db, TaskCreate(title=parsed.title, due_at=parsed.due_at))
        when = f" for {_format_due(task.due_at)}" if task.due_at else ""
        return ChatResponse(
            reply=f'Got it — I\'ve scheduled "{task.title}"{when}.',
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
            return ChatResponse(
                reply=f'I couldn\'t find a task matching "{parsed.task_query}".',
                intent=parsed.intent.value,
            )
        if len(matches) > 1:
            titles = ", ".join(f'"{m.title}"' for m in matches)
            return ChatResponse(
                reply=f"I found multiple matching tasks: {titles}. Could you be more specific?",
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

    return ChatResponse(
        reply='I didn\'t understand that. Try something like "Remind me to call Mom on Friday at 6 PM."',
        intent=parsed.intent.value,
    )
