import os
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./todo_bot.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """Brings the database up to the latest Alembic revision on startup.

    A database created before Alembic was introduced (via the old
    `Base.metadata.create_all` + additive-ALTER-TABLE approach) already has
    every current table but no `alembic_version` row — running `upgrade`
    against it would try to CREATE TABLE on tables that already exist and
    fail. Detect that case and `stamp` it as up to date instead, since its
    schema already matches; only a genuinely fresh or already-tracked
    database goes through a real `upgrade`.
    """
    from alembic import command
    from alembic.config import Config

    from app import models  # noqa: F401 — registers every model on Base.metadata

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if existing_tables and "alembic_version" not in existing_tables:
        command.stamp(cfg, "head")
    else:
        command.upgrade(cfg, "head")
