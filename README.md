# Custom To-Do Bot

Conversational task & reminder assistant — natural-language scheduling backed by a structured task API.

**Status: early build (Milestone 2 of 6) — task API and rule-based chat parser are live; ML-backed NLP and scheduling are in progress.**

Custom To-Do Bot lets a user manage tasks the way they'd talk to a personal assistant — "remind me to submit my resume tomorrow at 9 AM" — instead of filling out a form. The design separates language understanding from execution: a parser turns a sentence into a structured intent + entities, a dialogue layer fills in anything missing, and a plain REST API owns the actual task records. That separation means the task store and a real (if rule-based) conversation loop already work today, before any ML model is wired in.

Stack: FastAPI (Python) · SQLAlchemy · SQLite (Postgres-ready) · `dateparser` · *(planned: React chat UI, Hugging Face Inference API, APScheduler)*

Author: Anish Kuila

## Table of contents
- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Scale](#scale)
- [Install](#install)
- [Quickstart](#quickstart)
- [Project structure](#project-structure)
- [API reference](#api-reference)
- [Roadmap](#roadmap)
- [Limitations](#limitations)

## What it does

Target pipeline (chat-first assistant, per the [project roadmap](#roadmap)):

```
User ──▶ [Chat UI] ──▶ [Rule-based parser: intent + entities] ──▶ [Chat service] ──▶ [Task CRUD] ──▶ [SQLite/Postgres]
        (planned)          (this repo, /chat)                    (this repo)      (this repo)
                                    │
                        ┌───────────┼───────────┐
                        ▼           ▼           ▼
                 create_task   list_tasks   complete_task / delete_task
                        │
                        └──▶ ambiguous date/time? ask, don't guess
                                    │
                                    ▼
                          Recurrence · Scheduler · Reminder delivery
                                    (planned)
```

A message like `"Remind me to call Mom on Friday at 6 PM"` is classified into an intent (`create_task`), has its title and due date extracted via regex + `dateparser`, and is executed straight against the task store — no ML model in the loop yet. If a date is mentioned without a time (`"remind me to study tomorrow"`), the parser flags it as ambiguous and the chat service asks for clarification instead of silently picking a time. `complete_task`/`delete_task` resolve a free-text task reference against existing titles and ask for clarification on no-match or multiple-match. This whole loop is reachable today via `POST /chat`, independent of the ML-backed NLP and scheduling work still to come.

## Architecture

| Layer | Technology | Status |
|---|---|---|
| Backend | FastAPI, Pydantic schemas, SQLAlchemy ORM | Implemented |
| Database | SQLite (dev), swappable to MySQL/Postgres via `DATABASE_URL` | Implemented |
| NLP — intent/entities | Regex-based intent classification + `dateparser` for dates/times | Implemented (rule-based) |
| NLP — ML upgrade | Hugging Face Inference API for intent/entity extraction | Planned |
| Scheduling | APScheduler + worker | Planned |
| Frontend | React + TypeScript (chat-first, task list secondary) | Planned |
| Infra | Docker Compose | Planned |

## Scale

Counted directly from the codebase, not estimated:

| Metric | Count |
|---|---|
| REST API endpoints | 6, across 2 route modules |
| Database tables | 1 (`tasks`) |
| Task lifecycle states | 2 (`pending`, `completed`) |
| Chat intents recognized | 4 (`create_task`, `list_tasks`, `complete_task`, `delete_task`) |

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/anishneu/nlp-task.git custom-todo-bot
cd custom-todo-bot/backend
python -m venv venv
venv/Scripts/activate    # venv\Scripts\activate on Windows cmd, source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
```

## Quickstart

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

The API is now live at `http://127.0.0.1:8000` (interactive docs at `/docs`); a `todo_bot.db` SQLite file is created automatically on first run. Point `DATABASE_URL` at a MySQL/Postgres instance to use that instead.

## Project structure

```
nlp-task/
├── backend/
│   ├── app/
│   │   ├── main.py           FastAPI app entrypoint, health check
│   │   ├── models.py         SQLAlchemy Task model
│   │   ├── schemas.py        Pydantic request/response models
│   │   ├── crud.py           Database operations
│   │   ├── database.py       Engine/session setup
│   │   ├── nlp/
│   │   │   ├── intents.py    Intent enum
│   │   │   └── parser.py     Regex intent classification + dateparser entity extraction
│   │   ├── services/
│   │   │   └── chat.py       Dialogue logic: parsed message → task action → reply
│   │   └── routers/
│   │       ├── tasks.py      /tasks CRUD endpoints
│   │       └── chat.py       /chat conversational endpoint
│   └── requirements.txt
└── LICENSE
```

## API reference

| Endpoint | Purpose |
|---|---|
| `POST /tasks` | Create a task (title, optional description/due date) |
| `GET /tasks` | List tasks, optionally filtered by `status` |
| `GET /tasks/{id}` | Fetch a single task |
| `PATCH /tasks/{id}` | Partially update a task (e.g. mark completed, reschedule) |
| `DELETE /tasks/{id}` | Delete a task |
| `POST /chat` | Send a natural-language message; get back an intent, a reply, and any affected task(s) |
| `GET /health` | Liveness check |

## Roadmap

1. ~~Basic task API~~ — done
2. ~~Rule-based conversational parser~~ (`create_task` / `list_tasks` / `complete_task` / `delete_task` intents) — done
3. Hugging Face–backed intent classification + entity extraction
4. Dialogue state (follow-up questions for missing info)
5. Scheduling engine (APScheduler, recurrence, time zones)
6. React chat UI, notification delivery, Docker deployment

## Limitations

- Intent/entity extraction is regex + `dateparser` only — no ML model in the loop yet, so phrasing outside the recognized patterns falls back to "I didn't understand that."
- No multi-turn memory — each `/chat` call is stateless; a clarifying question ("what time?") isn't tied to a follow-up reply yet, so the follow-up has to be a full new message.
- No scheduling or reminder delivery, no frontend, no authentication — single-user, local use for now.
- No automated test suite yet.
- No CI/CD pipeline configured.

## License

MIT — see [LICENSE](LICENSE).
