from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import TaskStatus


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_at: datetime | None = None
    status: TaskStatus | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    due_at: datetime | None
    status: TaskStatus
    created_at: datetime
    updated_at: datetime


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    intent: str
    task: TaskOut | None = None
    tasks: list[TaskOut] | None = None
