from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Conversation, Message, MessageRole, PendingClarification, Task, TaskStatus
from app.nlp.hf_reply import generate_title
from app.schemas import TaskCreate, TaskUpdate


def create_task(db: Session, task_in: TaskCreate) -> Task:
    task = Task(**task_in.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: int) -> Task | None:
    return db.get(Task, task_id)


def list_tasks(db: Session, status: TaskStatus | None = None) -> list[Task]:
    stmt = select(Task).order_by(Task.due_at.is_(None), Task.due_at)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    return list(db.scalars(stmt))


def find_tasks_by_title(db: Session, query: str) -> list[Task]:
    stmt = select(Task).where(Task.title.ilike(f"%{query}%"))
    return list(db.scalars(stmt))


def update_task(db: Session, task: Task, task_in: TaskUpdate) -> Task:
    for field, value in task_in.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task: Task) -> None:
    db.delete(task)
    db.commit()


def list_due_tasks(db: Session, now: datetime) -> list[Task]:
    stmt = (
        select(Task)
        .where(Task.status == TaskStatus.pending, Task.due_at.is_not(None), Task.due_at <= now)
        .order_by(Task.due_at)
    )
    return list(db.scalars(stmt))


def list_overdue_recurring_tasks(db: Session, now: datetime) -> list[Task]:
    stmt = select(Task).where(
        Task.status == TaskStatus.pending,
        Task.recurrence.is_not(None),
        Task.due_at.is_not(None),
        Task.due_at <= now,
    )
    return list(db.scalars(stmt))


def list_unnotified_due_tasks(db: Session, now: datetime) -> list[Task]:
    stmt = select(Task).where(
        Task.status == TaskStatus.pending,
        Task.due_at.is_not(None),
        Task.due_at <= now,
        Task.notified_at.is_(None),
    )
    return list(db.scalars(stmt))


def get_tasks_by_ids(db: Session, ids: list[int]) -> list[Task]:
    if not ids:
        return []
    stmt = select(Task).where(Task.id.in_(ids))
    return list(db.scalars(stmt))


def get_pending(db: Session, conversation_id: str) -> PendingClarification | None:
    stmt = select(PendingClarification).where(
        PendingClarification.conversation_id == conversation_id
    )
    return db.scalar(stmt)


def set_pending(db: Session, conversation_id: str, **fields) -> PendingClarification:
    existing = get_pending(db, conversation_id)
    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
    else:
        existing = PendingClarification(conversation_id=conversation_id, **fields)
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def clear_pending(db: Session, conversation_id: str) -> None:
    existing = get_pending(db, conversation_id)
    if existing:
        db.delete(existing)
        db.commit()


def get_or_create_conversation(db: Session, conversation_id: str) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        conversation = Conversation(id=conversation_id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    return conversation


def list_conversations(db: Session) -> list[Conversation]:
    stmt = select(Conversation).order_by(Conversation.updated_at.desc())
    return list(db.scalars(stmt))


def list_messages(db: Session, conversation_id: str) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return list(db.scalars(stmt))


def add_message(
    db: Session, conversation_id: str, role: MessageRole, content: str, intent: str | None = None
) -> Message:
    conversation = get_or_create_conversation(db, conversation_id)
    message = Message(conversation_id=conversation_id, role=role, content=content, intent=intent)
    db.add(message)
    if conversation.title is None and role == MessageRole.user:
        conversation.title = generate_title(content) or content[:60]
    conversation.updated_at = datetime.now()
    db.commit()
    db.refresh(message)
    return message


def delete_conversation(db: Session, conversation_id: str) -> None:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        return
    for message in list_messages(db, conversation_id):
        db.delete(message)
    pending = get_pending(db, conversation_id)
    if pending:
        db.delete(pending)
    db.delete(conversation)
    db.commit()
