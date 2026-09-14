import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app import clock
from app.database import Base


class TaskStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"


class ClarificationKind(str, enum.Enum):
    awaiting_time = "awaiting_time"
    awaiting_task_choice = "awaiting_task_choice"


class MessageRole(str, enum.Enum):
    user = "user"
    bot = "bot"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    recurrence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.pending)
    starred: Mapped[bool] = mapped_column(Boolean, default=False)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=clock.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=clock.now, onupdate=clock.now
    )


class PendingClarification(Base):
    """One outstanding follow-up question per conversation (Milestone 4: dialogue state)."""

    __tablename__ = "pending_clarifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    kind: Mapped[ClarificationKind] = mapped_column(Enum(ClarificationKind))
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # The new due date/time for a reschedule that's still waiting on "which
    # task did you mean?" — base_date alone (just a date) can't carry a
    # specific time, and update_task reschedules always specify one.
    pending_due_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    recurrence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    action: Mapped[str | None] = mapped_column(String(20), nullable=True)
    candidate_ids: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=clock.now)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=clock.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=clock.now, onupdate=clock.now
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("conversations.id"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole))
    content: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=clock.now)
