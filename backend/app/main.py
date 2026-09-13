from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import chat, conversations, reminders, tasks
from app.scheduler import start_scheduler, stop_scheduler

Base.metadata.create_all(bind=engine)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Custom To-Do Bot API")
app.include_router(tasks.router)
app.include_router(chat.router)
app.include_router(reminders.router)
app.include_router(conversations.router)
app.mount(
    "/assets", StaticFiles(directory=STATIC_DIR / "assets", check_dir=False), name="assets"
)


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
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return (
            "Frontend not built yet. Run `npm run build` in frontend/ "
            "(or `npm run dev` for local development), then reload."
        )
    return FileResponse(index_file)
