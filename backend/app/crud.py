from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Task, TaskStatus
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
