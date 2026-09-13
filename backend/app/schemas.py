from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import MessageRole, TaskStatus


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    due_at: datetime | None = None
    recurrence: str | None = None
    link: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_at: datetime | None = None
    recurrence: str | None = None
    status: TaskStatus | None = None
    starred: bool | None = None
    link: str | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    due_at: datetime | None
    recurrence: str | None
    status: TaskStatus
    starred: bool
    link: str | None
    created_at: datetime
    updated_at: datetime


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    bot_name: str | None = None


class ChatResponse(BaseModel):
    reply: str
    intent: str
    task: TaskOut | None = None
    tasks: list[TaskOut] | None = None
    bot_name: str | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: MessageRole
    content: str
    intent: str | None
    created_at: datetime
