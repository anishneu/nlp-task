# Custom To-Do Bot

Conversational task & reminder assistant — natural-language scheduling backed by a structured task API.

**Status: all 6 roadmap milestones implemented,** including a React + TypeScript + Tailwind frontend.

Custom To-Do Bot lets a user manage tasks the way they'd talk to a personal assistant — "remind me to submit my resume tomorrow at 9 AM" — instead of filling out a form. The design separates language understanding from execution: a parser turns a sentence into a structured intent + entities, a dialogue layer fills in anything missing (asking follow-up questions across turns), a plain REST API owns the actual task records, and a background scheduler keeps recurring reminders — and their notifications — on track.

Stack: FastAPI (Python) · SQLAlchemy · SQLite (Postgres/MySQL-ready) · `dateparser` · APScheduler · Hugging Face Inference API (optional) · React + TypeScript + Tailwind CSS (Vite) · Docker Compose

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

Pipeline (chat-first assistant, per the [project roadmap](#roadmap)):

```
User ──▶ [React chat UI] ──▶ [Parser: HF zero-shot intent (optional) → regex fallback + dateparser entities] ──▶ [Chat service] ──▶ [Task CRUD] ──▶ [SQLite/Postgres]
       (frontend/, served       (this repo, app/nlp/)                                              (dialogue state,   (this repo)
        by FastAPI at /)                                                                             app/services/)
                                                                                                              │
                                                                                    ┌─────────────────────────┼─────────────────────────┐
                                                                                    ▼                         ▼                         ▼
                                                                             create_task               list_tasks             complete_task / delete_task
                                                                                    │                                                    │
                                                                    ambiguous date/time or            multiple tasks match a free-text reference?
                                                                    recurrence w/o time? ask,          ask which one, remember the answer
                                                                    remember the pending question              │
                                                                                    └───────────────┬───────────┘
                                                                                                      ▼
                                                                                     Next message answers the question
                                                                                     (PendingClarification, keyed by session_id)
                                                                                                      │
                                                                                                      ▼
                                                                          APScheduler (every 30s): fast-forwards any recurring
                                                                          task whose due date has passed to its next occurrence
                                                                                                      │
                                                                                                      ▼
                                                                  GET /reminders/due ──▶ in-app toast   +   opt-in email via SMTP
```

A message like `"Remind me to call Mom on Friday at 6 PM"` is classified into an intent (`create_task`), has its title and due date extracted, and is executed straight against the task store. Intent classification tries the Hugging Face Inference API first when `HF_TOKEN` is configured (zero-shot classification against the four intents), and transparently falls back to the regex classifier otherwise — so the bot works identically with zero setup, and gets a real ML model in the loop the moment you add a free token.

If a date is mentioned without a time (`"remind me to study tomorrow"`) — or a recurrence is given with no time at all (`"remind me to drink water every day"`) — the parser flags it as ambiguous and the bot asks a follow-up question instead of guessing. That follow-up is genuinely multi-turn: the frontend sends a `session_id` with every message, the backend remembers the pending question against it, and your very next message (`"10am"`, or `"the bank one"` when disambiguating between two similarly-named tasks) is interpreted as the answer rather than a fresh command. `"remind me to exercise every Monday at 7 AM"` sets up a recurring task directly; the same background APScheduler job that fast-forwards missed recurring tasks to their next future occurrence also emails (best-effort, opt-in via SMTP env vars) any due task that hasn't been notified yet — so a missed reminder always lands on the right future date, and gets a fresh notification each time it recurs. The bundled UI polls `GET /reminders/due` and pops an in-app toast notification for anything currently due, independent of whether email is configured.

The bot also handles basic small talk outside the task domain: a greeting (`"hi"`, `"hey"`) gets a friendly reply introducing itself, and asking it to rename itself (`"can I call you Romero"`) actually renames it — the reply carries the new name back to the frontend, which persists it to `localStorage` and updates the header, browser tab title, and input placeholder, exactly as if you'd used the manual Rename button.

## Architecture

| Layer | Technology | Status |
|---|---|---|
| Backend | FastAPI, Pydantic schemas, SQLAlchemy ORM | Implemented |
| Database | SQLite (dev), swappable to MySQL/Postgres via `DATABASE_URL` | Implemented |
| NLP — intent classification | Hugging Face Inference API zero-shot (`facebook/bart-large-mnli`), opt-in via `HF_TOKEN`, with a regex classifier as automatic fallback | Implemented |
| NLP — entities (dates/times/recurrence) | Regex + `dateparser` | Implemented (rule-based) |
| Dialogue state | Per-session `PendingClarification` (DB-backed), multi-turn follow-up answers | Implemented |
| Scheduling | APScheduler background job: recurrence advancement + due-reminder notification | Implemented |
| Notifications | In-app toasts (`/reminders/due` polling) always on; email via SMTP opt-in (`smtplib`, stdlib — no extra dependency) | Implemented |
| Frontend | React 19 + TypeScript + Tailwind CSS 4, built with Vite; served by FastAPI at `/` in production, or `npm run dev` (proxied) for local development | Implemented |
| Infra | Docker Compose (`docker-compose.yml` + `backend/Dockerfile`, multi-stage: builds the frontend, then the API image), named volume for SQLite persistence | Implemented |

## Scale

Counted directly from the codebase, not estimated:

| Metric | Count |
|---|---|
| REST API endpoints | 7, across 3 route modules |
| Database tables | 2 (`tasks`, `pending_clarifications`) |
| Task lifecycle states | 2 (`pending`, `completed`) |
| Chat intents recognized | 6 (`create_task`, `list_tasks`, `complete_task`, `delete_task`, `greeting`, `set_name`) |
| Recurrence cadences | 3 (`daily`, `weekly`, `monthly`) |
| Dialogue follow-up kinds | 2 (ambiguous time, ambiguous task choice) |
| Notification channels | 2 (in-app toast, opt-in email) |

## Install

Requires Python 3.10+ and Node 18+.

```bash
git clone https://github.com/anishneu/nlp-task.git custom-todo-bot
cd custom-todo-bot/backend
python -m venv venv
venv/Scripts/activate    # venv\Scripts\activate on Windows cmd, source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env   # optional — only needed to enable the HF Inference API or a non-SQLite database

cd ../frontend
npm install
```

## Quickstart

**Local development** (fast-refresh frontend, proxied to the API):

```bash
# terminal 1
cd backend && uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend && npm run dev
```

Open `http://localhost:5173/` — Vite proxies `/tasks`, `/chat`, `/reminders`, and `/health` to the backend, so no CORS setup is needed. `http://127.0.0.1:8000/docs` still has the raw API.

**Single-server (production-like):**

```bash
cd frontend && npm run build   # outputs into backend/app/static
cd ../backend && uvicorn app.main:app --port 8000
```

Open `http://127.0.0.1:8000/` — FastAPI now serves the built frontend directly, no separate frontend server. A `todo_bot.db` SQLite file is created automatically on first run; point `DATABASE_URL` at a MySQL/Postgres instance to use that instead. To enable ML-backed intent classification, set `HF_TOKEN` in `backend/.env` to a free token from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) — without it, the app runs entirely on the rule-based parser with no loss of functionality.

### Or with Docker

```bash
cp .env.example .env   # optional — fill in HF_TOKEN / SMTP_* to enable those features
docker compose up --build
```

Builds the frontend and the API into one image (multi-stage build). Same app, same `/` UI, at `http://localhost:8000/`. The SQLite database lives in a named volume (`todo_bot_data`) so it survives container restarts.

## Project structure

```
nlp-task/
├── docker-compose.yml           Backend service (multi-stage build) + persistent SQLite volume
├── .env.example                 Vars docker-compose reads (HF_TOKEN, SMTP_*)
├── backend/
│   ├── Dockerfile                Multi-stage: builds frontend/, then the Python image
│   ├── .env.example               Same vars, for local (non-Docker) runs
│   ├── app/
│   │   ├── main.py                FastAPI app entrypoint, scheduler lifecycle, health check, serves the built frontend at /
│   │   ├── config.py               Env var loading (HF_TOKEN, SMTP_*) via python-dotenv
│   │   ├── models.py               SQLAlchemy models: Task, PendingClarification
│   │   ├── schemas.py              Pydantic request/response models
│   │   ├── crud.py                 Database operations
│   │   ├── database.py             Engine/session setup
│   │   ├── scheduler.py            APScheduler job: recurrence advancement + due-reminder emails
│   │   ├── notifications.py        Best-effort SMTP email sender (stdlib smtplib, opt-in)
│   │   ├── nlp/
│   │   │   ├── intents.py          Intent enum
│   │   │   ├── hf_intent.py        Hugging Face zero-shot intent classification (falls back to None on any failure)
│   │   │   └── parser.py           Regex intent classification + dateparser entity/recurrence extraction
│   │   ├── services/
│   │   │   └── chat.py             Dialogue logic: parsed message → task action or follow-up question → reply
│   │   ├── routers/
│   │   │   ├── tasks.py            /tasks CRUD endpoints
│   │   │   ├── chat.py             /chat conversational endpoint
│   │   │   └── reminders.py        /reminders/due endpoint for in-app notification polling
│   │   └── static/                 Build output (git-ignored) — `npm run build` writes here
│   └── requirements.txt
├── frontend/
│   ├── vite.config.ts             Tailwind plugin, dev-server proxy to the API, build output → backend/app/static
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                 Top-level layout + shared state (tasks, bot name)
│       ├── api.ts                  Typed fetch wrappers for /tasks, /chat, /reminders
│       ├── types.ts                 Task / ChatResponse types (mirrors the Pydantic schemas)
│       ├── storage.ts               localStorage helpers: session id, bot name
│       └── components/
│           ├── ChatPanel.tsx        Message log, example prompts, input, rename
│           ├── TaskPanel.tsx        Task list with status/recurrence badges, Done/Delete
│           └── ToastContainer.tsx   Polls /reminders/due, renders in-app notifications
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
| `POST /chat` | Send a natural-language message (+ optional `session_id` for multi-turn follow-ups); get back an intent, a reply, and any affected task(s) |
| `GET /reminders/due` | List pending tasks whose due date has passed — polled by the UI to drive in-app toast notifications |
| `GET /health` | Liveness check |

## Roadmap

1. ~~Basic task API~~ — done
2. ~~Rule-based conversational parser~~ (`create_task` / `list_tasks` / `complete_task` / `delete_task` intents) — done
3. ~~Hugging Face–backed intent classification~~ (opt-in via `HF_TOKEN`, regex fallback when unset) — done
4. ~~Dialogue state~~ (multi-turn follow-up questions, keyed by `session_id`) — done
5. ~~Scheduling engine~~ (APScheduler, recurrence, missed-reminder fast-forwarding) — done
6. ~~Notification delivery, Docker deployment, and React frontend~~ (in-app toasts + opt-in SMTP email, `docker compose up`, React + TypeScript + Tailwind UI) — done

## Limitations

- Intent classification only calls a real ML model when `HF_TOKEN` is set; without it, the app runs entirely on the regex classifier. Both paths are live-verified: the fallback (no token) and a real call against the current Hugging Face Inference Providers endpoint (`router.huggingface.co/hf-inference/...` — note this replaced the older `api-inference.huggingface.co` endpoint, which HF has retired).
- The frontend build (`backend/app/static/`) is git-ignored — it's generated by `npm run build`, not committed source. A fresh clone needs that build step (or `npm run dev`, or Docker) before `/` serves anything; the API itself (`/tasks`, `/chat`, etc.) works either way.
- Entity extraction (dates, times, recurrence, task titles) is regex + `dateparser` only — phrasing well outside the recognized patterns falls back to "I didn't understand that."
- Recurrence is limited to `daily` / `weekly` / `monthly` cadences on a single task row (no full RRULE support, no per-occurrence history) and there's no time zone handling — all dates are naive local server time.
- Email notifications are opt-in via SMTP env vars and best-effort (no retry beyond the next scheduler tick); not tested against a live SMTP server in this environment — the no-SMTP-configured fallback path is what's been verified.
- The Docker setup (`Dockerfile` + `docker-compose.yml`, multi-stage: Node build → Python runtime) hasn't been build-tested in this environment (no Docker available here) — reviewed for correctness, but verify `docker compose up --build` yourself before relying on it.
- No authentication — single-user, local use for now.
- No automated test suite yet.
- No CI/CD pipeline configured.

## License

MIT — see [LICENSE](LICENSE).
