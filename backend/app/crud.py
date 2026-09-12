from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PendingClarification, Task, TaskStatus
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


def get_pending(db: Session, session_id: str) -> PendingClarification | None:
    stmt = select(PendingClarification).where(PendingClarification.session_id == session_id)
    return db.scalar(stmt)


def set_pending(db: Session, session_id: str, **fields) -> PendingClarification:
    existing = get_pending(db, session_id)
    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
    else:
        existing = PendingClarification(session_id=session_id, **fields)
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def clear_pending(db: Session, session_id: str) -> None:
    existing = get_pending(db, session_id)
    if existing:
        db.delete(existing)
        db.commit()
