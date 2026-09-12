from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.database import Base, engine
from app.routers import chat, reminders, tasks
from app.scheduler import start_scheduler, stop_scheduler

Base.metadata.create_all(bind=engine)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Custom To-Do Bot API")
app.include_router(tasks.router)
app.include_router(chat.router)
app.include_router(reminders.router)


@app.on_event("startup")
def on_startup():
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown():
    stop_scheduler()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def ui():
    return FileResponse(STATIC_DIR / "index.html")
