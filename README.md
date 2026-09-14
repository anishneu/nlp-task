# Customizable NLP-Based Task & Reminder Chat Assistant

Conversational task & reminder assistant — natural-language scheduling backed by a structured task API.

**Status: chat, task management, conversation history, scheduling/notifications, and a React frontend are all implemented and working.**

It lets a user manage tasks the way they'd talk to a personal assistant — "remind me to submit my resume tomorrow at 9 AM" — instead of filling out a form. The design separates language understanding from execution: a parser turns a sentence into a structured intent + entities, a dialogue layer fills in anything missing (asking follow-up questions across turns), a plain REST API owns the actual task records, and a background scheduler keeps recurring reminders — and their notifications — on track. Every conversation is a persisted, resumable thread (ChatGPT-style history), and tasks can be starred, filtered, and viewed on a calendar.

Stack: FastAPI (Python) · SQLAlchemy · SQLite (Postgres/MySQL-ready) · `dateparser` · APScheduler · Hugging Face Inference API · React + TypeScript + Tailwind CSS (Vite) · Docker Compose

Author: Anish Kuila

## Table of contents
- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Scale](#scale)
- [Install](#install)
- [Quickstart](#quickstart)
- [Database migrations](#database-migrations)
- [Project structure](#project-structure)
- [API reference](#api-reference)
- [Limitations](#limitations)

## What it does

Pipeline (chat-first assistant):

```
User ──▶ [React chat UI] ──▶ [Parser: HF zero-shot intent → regex fallback + dateparser entities] ──▶ [Chat service] ──▶ [Task CRUD] ──▶ [SQLite/Postgres]
       (frontend/, served       (this repo, app/nlp/)                                              (dialogue state,   (this repo)
        by FastAPI at /)                                                                             app/services/)
                                                                                                              │
                                                                                    ┌─────────────────────────┼─────────────────────────┐
                                                                                    ▼                         ▼                         ▼
                                                                     create_task               list_tasks       complete_task / delete_task / update_task
                                                                                    │                                                    │
                                                                    ambiguous date/time or            multiple tasks match a free-text reference, or
                                                                    recurrence w/o time? ask,          a reschedule with no resolved time yet? ask,
                                                                    remember the pending question      remember the pending question (either order)
                                                                                    └───────────────┬───────────┘
                                                                                                      ▼
                                                                                     Next message answers the question
                                                                                     (PendingClarification, keyed by conversation_id)
                                                                                                      │
                                                                                                      ▼
                                                                          APScheduler (every 30s): fast-forwards any recurring
                                                                          task whose due date has passed to its next occurrence
                                                                                                      │
                                                                                                      ▼
                                                                                    GET /reminders/due ──▶ in-app toast
```

A message like `"Remind me to call Mom on Friday at 6 PM"` is classified into an intent (`create_task`), has its title and due date extracted, and is executed straight against the task store. Intent classification tries the Hugging Face Inference API first when `HF_TOKEN` is configured — zero-shot classification against seven candidate labels: the five task actions plus "a greeting or friendly small talk" and "something unrelated to managing tasks or reminders", so casual chat (`"how are you doing?"`, `"thanks!"`) has a legitimate bucket instead of being force-fit into a task action — and transparently falls back to the regex classifier otherwise, so the bot works identically with zero setup, and gets a real ML model in the loop the moment you add a free token.

If a date is mentioned without a time (`"remind me to study tomorrow"`) — or a recurrence is given with no time at all (`"remind me to drink water every day"`) — the parser flags it as ambiguous and the bot asks a follow-up question instead of guessing. That follow-up is genuinely multi-turn: the frontend sends a `conversation_id` with every message, the backend remembers the pending question against it, and your very next message (`"10am"`, or `"the bank one"` when disambiguating between two similarly-named tasks) is interpreted as the answer rather than a fresh command. `"remind me to exercise every Monday at 7 AM"` sets up a recurring task directly; a background APScheduler job fast-forwards any missed recurring task to its next future occurrence, so it always lands on the right future date instead of staying stuck in the past. The bundled UI polls `GET /reminders/due` and pops an in-app toast notification for anything currently due.

A single message describing several distinct events — joined by a conjunction (`"an interview at 2pm and a birthday party at 7pm"`), written as separate sentences, or with no connecting word at all (`"call the dentist at 2pm, submit taxes by 5pm"`) — is split into that many separate tasks, each with its own title and time. Regex handles the common conjunction/sentence-boundary cases for free; when it finds 2+ of its own explicit-time phrases in one message but can't confidently separate them itself, it escalates once to a small HF-hosted LLM (opt-in via `HF_TOKEN`) whose only job is to segment the raw text — it never computes a date itself, so a hallucinated date can't slip through: each returned snippet is re-run through the same regex + dateparser extraction used everywhere else. Only segments that resolve their own clear title + explicit time count; anything else (a connective opener like "I've got a few things to do today", trailing filler like "could you please") is silently dropped rather than voiding the split. If fewer than two segments end up resolving — e.g. `"buy milk and eggs tomorrow at 5pm"`, only one time for both — the whole message falls back to becoming one task instead of guessing at a partial split.

The bot also handles basic small talk outside the task domain: a greeting (`"hi"`, `"hey"`) gets a friendly reply introducing itself — echoing back "Good morning"/"afternoon"/"evening" if you used one — and asking it to rename itself (`"can I call you Romero"`) actually renames it — the reply carries the new name back to the frontend, which persists it to `localStorage` and updates the header, browser tab title, and input placeholder, exactly as if you'd used the manual Rename button.

Picking *which* task a `complete_task`/`delete_task`/`update_task` message refers to also goes through Hugging Face when configured: `"get rid of the dentist thing, not doing it anymore"` has no keyword overlap with a task titled `"call the dentist"`, but their sentence embeddings (`BAAI/bge-small-en-v1.5`, compared by cosine similarity) are close enough to resolve it correctly. Falls back to keyword-overlap matching when `HF_TOKEN` isn't set, same pattern as intent classification.

`"reschedule"`/`"postpone"`/`"push back"`/`"update"`/`"edit"` are recognized as a distinct `update_task` intent — a real reschedule (`"reschedule my dinner date with Ms. Erza to tomorrow 9pm"`) modifies the matching task's due date in place instead of silently creating a duplicate. If the message names multiple matching tasks, a new time with no task chosen yet, or both at once, the two questions ("which task?" and "what time?") are asked and remembered in whichever order is actually missing, resolving to the same update either way.

Every reply also passes through a small LLM (`google/gemma-2-2b-it`) that rephrases the deterministic template into something more conversational — the underlying facts (task titles, dates, links) are computed exactly as before and the LLM's only job is wording, so a "Got it — I've scheduled X for Y" can come back as "Sounds good, I'll remind you about X on Y!" without risking the actual data. Falls back to the plain template instantly if `HF_TOKEN` isn't set or the call fails for any reason (see [Limitations](#limitations) for a real caveat about this one's free-tier quota).

Every conversation is a real, persisted thread: a left sidebar lists past conversations (auto-titled from their first message), **New Chat** starts a fresh one, and clicking any past conversation reloads its full message history from the database — nothing lives only in browser memory. Pasting a meeting link into a message (`"remind me to join the standup at meet.google.com/abc-defg-hij tomorrow at 10am"` — also recognizes `zoom.us/...`, `teams.microsoft.com/...`, or any `https://` URL) attaches it to the task and shows it as a clickable "🎥 Join Meet" button on the task card and in the chat reply. Tasks can be starred as important, filtered by status or starred-only, and viewed either as a list or on a full month calendar grid (click a day to filter the list to it) — each task also shows a relative "created X ago" timestamp. Clicking a task's title opens a detail popup with its full record: status, exact due date, recurrence, description, link, and both created/last-updated timestamps, with Star/Mark done/Delete actions right there — and an Edit button next to the due date lets you set or change it directly with a native date/time picker, no chat message required. Chat messages carry a full date + time (not just a bare clock time), and addressing the bot by name first ("Serene, remind me to...") no longer breaks parsing — the vocative is stripped before anything else runs.

## Architecture

| Layer | Technology | Status |
|---|---|---|
| Backend | FastAPI, Pydantic schemas, SQLAlchemy ORM | Implemented |
| Database | SQLite (dev), swappable to MySQL/Postgres via `DATABASE_URL` | Implemented |
| NLP — intent classification | Hugging Face Inference API zero-shot (`facebook/bart-large-mnli`), 7 labels (5 task actions + greeting + off-topic), opt-in via `HF_TOKEN`, with a regex classifier as automatic fallback | Implemented |
| NLP — task matching | Hugging Face sentence embeddings (`BAAI/bge-small-en-v1.5`, cosine similarity) to resolve which task a vague/indirect phrase refers to, opt-in via `HF_TOKEN`, with keyword-overlap matching as automatic fallback | Implemented |
| Conversational tone | Hugging Face chat-completion (`google/gemma-2-2b-it`, configurable via `HF_REPLY_MODEL`) rephrases each deterministic reply to sound natural, opt-in via `HF_TOKEN`, with the plain template as automatic fallback | Implemented |
| NLP — entities (dates/times/recurrence/links) | Regex + `dateparser` | Implemented (rule-based) |
| NLP — multi-event segmentation | Regex (conjunctions/sentence boundaries) first; escalates to a small HF chat-completion model, opt-in via `HF_TOKEN`, only when regex finds 2+ explicit times it can't separate itself — segmentation only, never date computation | Implemented |
| Dialogue state | Per-conversation `PendingClarification` (DB-backed), multi-turn follow-up answers | Implemented |
| Conversation history | `Conversation` + `Message` tables; sidebar lists/switches/deletes threads, full history reloads on select | Implemented |
| Meeting links | Regex extraction of pasted meeting URLs (Meet/Zoom/Teams/any `https://` link) from a message, attached to the task | Implemented |
| Task organization | `starred` flag, status + starred-only filters, sort by recently-updated/due date/recently-created/title, list/calendar views, relative "created X ago" timestamps | Implemented |
| Scheduling | APScheduler background job: recurrence advancement + due-reminder notification | Implemented |
| Notifications | In-app toasts via `/reminders/due` polling | Implemented |
| Frontend | React 19 + TypeScript + Tailwind CSS 4, built with Vite; landing page → sidebar + chat + tasks; served by FastAPI at `/` in production, or `npm run dev` (proxied) for local development | Implemented |
| Infra | Docker Compose (`docker-compose.yml` + `backend/Dockerfile`, multi-stage: builds the frontend, then the API image), named volume for SQLite persistence | Implemented |

## Scale

Counted directly from the codebase, not estimated:

| Metric | Count |
|---|---|
| REST API endpoints | 11, across 4 route modules |
| Database tables | 4 (`tasks`, `pending_clarifications`, `conversations`, `messages`) |
| Task lifecycle states | 2 (`pending`, `completed`) |
| Chat intents recognized | 7 (`create_task`, `list_tasks`, `complete_task`, `delete_task`, `update_task`, `greeting`, `set_name`) |
| Recurrence cadences | 5 fixed (`daily`, `weekly`, `monthly`, `yearly`, `weekday`) + arbitrary "every N days/weeks/months" |
| Dialogue follow-up kinds | 2 (ambiguous time, ambiguous task choice) |
| Notification channels | 1 (in-app toast) |
| Hugging Face models used | 3 (`facebook/bart-large-mnli` for intent, `BAAI/bge-small-en-v1.5` for task matching, `google/gemma-2-2b-it` for reply tone) |
| Meeting link platforms recognized | 3 (Google Meet, Zoom, Microsoft Teams) + any `https://` URL |
| Task views | 2 (filterable list, month calendar grid) |

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
# terminal 1 — from the repo root
cd backend
venv/Scripts/activate    # venv\Scripts\activate on Windows cmd, source venv/bin/activate on macOS/Linux
uvicorn app.main:app --reload --port 8000

# terminal 2 — from the repo root
cd frontend && npm run dev
```

Open `http://localhost:3000/` — Vite proxies `/tasks`, `/chat`, `/reminders`, and `/health` to the backend, so no CORS setup is needed. `http://127.0.0.1:8000/docs` still has the raw API.

**Single-server (production-like):**

```bash
cd frontend && npm run build   # outputs into backend/app/static
cd ../backend
venv/Scripts/activate    # venv\Scripts\activate on Windows cmd, source venv/bin/activate on macOS/Linux
uvicorn app.main:app --port 8000
```

Open `http://127.0.0.1:8000/` — FastAPI now serves the built frontend directly, no separate frontend server. A `todo_bot.db` SQLite file is created automatically on first run; point `DATABASE_URL` at a MySQL/Postgres instance to use that instead. To enable ML-backed intent classification, set `HF_TOKEN` in `backend/.env` to a free token from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) — without it, the app runs entirely on the rule-based parser with no loss of functionality. Every due date and timestamp is computed using the server process's own system timezone by default; if that machine isn't in your own timezone (a cloud host, a container, a dev sandbox), set `APP_TIMEZONE` in `backend/.env` to an IANA name like `America/New_York` so "today"/"tomorrow"/bare times resolve against where you actually are.

### Or with Docker

```bash
cp .env.example .env   # optional — fill in HF_TOKEN to enable ML-backed features
docker compose up --build
```

Builds the frontend and the API into one image (multi-stage build). Same app, same `/` UI, at `http://localhost:8000/`. The SQLite database lives in a named volume (`todo_bot_data`) so it survives container restarts.

## Database migrations

Schema changes go through [Alembic](https://alembic.sqlalchemy.org/) (`backend/migrations/`). The app runs pending migrations automatically on startup — `alembic upgrade head` for a fresh or already-tracked database, or a one-time `alembic stamp head` (no schema changes, just marking it current) if it's a database from before Alembic was introduced. You don't need to run anything by hand to keep using the app.

To change a model, edit `backend/app/models.py`, then generate and apply a migration:

```bash
cd backend
alembic revision --autogenerate -m "add priority to tasks"   # inspects models.py vs the current db, writes migrations/versions/<hash>_add_priority_to_tasks.py
alembic upgrade head                                          # applies it (the app would also do this on next startup)
```

Autogenerate is good at columns and tables; it doesn't reliably catch things like renaming a column (it sees that as a drop + an add) or data backfills — review the generated file before running it, and hand-edit `upgrade()`/`downgrade()` when it's not exactly what you meant. `alembic downgrade -1` reverts the most recent migration.

## Project structure

```
nlp-task/
├── docker-compose.yml           Backend service (multi-stage build) + persistent SQLite volume
├── .env.example                 Vars docker-compose reads (HF_TOKEN + model overrides, APP_TIMEZONE)
├── backend/
│   ├── Dockerfile                Multi-stage: builds frontend/, then the Python image
│   ├── .env.example               Same vars, for local (non-Docker) runs
│   ├── alembic.ini                 Alembic config (sqlalchemy.url overridden at runtime from DATABASE_URL)
│   ├── migrations/                 Alembic migration scripts — see "Database migrations" above
│   ├── app/
│   │   ├── main.py                FastAPI app entrypoint, scheduler lifecycle, health check, serves the built frontend at /
│   │   ├── config.py               Env var loading (HF_TOKEN, APP_TIMEZONE) via python-dotenv
│   │   ├── clock.py                 now() — every "current time" in the app goes through here, adjusted to APP_TIMEZONE if set
│   │   ├── models.py               SQLAlchemy models: Task, PendingClarification, Conversation, Message
│   │   ├── schemas.py              Pydantic request/response models
│   │   ├── crud.py                 Database operations
│   │   ├── database.py             Engine/session setup + run_migrations() (upgrade or stamp on startup)
│   │   ├── scheduler.py            APScheduler job: recurrence advancement for overdue recurring tasks
│   │   ├── nlp/
│   │   │   ├── intents.py          Intent enum
│   │   │   ├── hf_intent.py        Hugging Face zero-shot intent classification (falls back to None on any failure)
│   │   │   ├── hf_similarity.py    Hugging Face sentence embeddings for semantic task matching (falls back to None on any failure)
│   │   │   ├── hf_reply.py         Hugging Face chat-completion: rephrases replies conversationally, with a fallback model for non-quota failures
│   │   │   ├── hf_segment.py       Hugging Face chat-completion: segments a multi-event message into per-event text snippets only (never computes dates itself)
│   │   │   └── parser.py           Regex intent classification + dateparser entity/recurrence/link extraction
│   │   ├── services/
│   │   │   └── chat.py             Dialogue logic: parsed message → task action or follow-up question → reply; persists messages
│   │   ├── routers/
│   │   │   ├── tasks.py            /tasks CRUD endpoints
│   │   │   ├── chat.py             /chat conversational endpoint
│   │   │   ├── reminders.py        /reminders/due endpoint for in-app notification polling
│   │   │   └── conversations.py    /conversations list/messages/delete endpoints
│   │   └── static/                 Build output (git-ignored) — `npm run build` writes here
│   └── requirements.txt
├── frontend/
│   ├── vite.config.ts             Tailwind plugin, dev-server proxy to the API, build output → backend/app/static
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                 Top-level layout + shared state (tasks, conversations, bot name)
│       ├── api.ts                  Typed fetch wrappers for /tasks, /chat, /reminders, /conversations
│       ├── types.ts                 Task / ChatResponse / Conversation / Message types (mirror the Pydantic schemas)
│       ├── storage.ts               localStorage helpers: conversation id, bot name
│       └── components/
│           ├── LandingPage.tsx      Intro page with feature highlights + Get Started button
│           ├── Sidebar.tsx          Conversation history list, New Chat, switch/delete
│           ├── ChatPanel.tsx        Message log (controlled), example prompts, input, rename
│           ├── TaskPanel.tsx        Task list: status/starred filters, star toggle, Join Meet link, timestamps
│           ├── TaskDetailModal.tsx   Full task record popup (opened by clicking a task's title)
│           ├── CalendarView.tsx     Month calendar grid, tasks plotted on due dates, click a day to filter
│           └── ToastContainer.tsx   Polls /reminders/due, renders in-app notifications
└── LICENSE
```

## API reference

| Endpoint | Purpose |
|---|---|
| `POST /tasks` | Create a task (title, optional description/due date/link) |
| `GET /tasks` | List tasks, optionally filtered by `status` |
| `GET /tasks/{id}` | Fetch a single task |
| `PATCH /tasks/{id}` | Partially update a task (e.g. mark completed, star, reschedule) |
| `DELETE /tasks/{id}` | Delete a task |
| `POST /chat` | Send a natural-language message (+ optional `conversation_id` for multi-turn follow-ups and history); get back an intent, a reply, and any affected task(s) |
| `GET /reminders/due` | List pending tasks whose due date has passed — polled by the UI to drive in-app toast notifications |
| `GET /conversations` | List conversations (id, title, timestamps), newest first, for the sidebar |
| `GET /conversations/{id}/messages` | Full message history for one conversation |
| `DELETE /conversations/{id}` | Delete a conversation and its messages |
| `GET /health` | Liveness check |

## Limitations

- All three HF-backed features (intent classification, task matching, reply tone) need `HF_TOKEN`; without it, the app runs entirely on regex/template fallbacks.
- Reply rephrasing draws from a much smaller, shared third-party quota than the other two HF features (which run on HF's own free `hf-inference` tier) — it can run out from moderate use. Falls back to the plain template reply when exhausted, with a circuit breaker to avoid repeated latency and a fallback model for non-quota failures. Note: the shared quota means pointing `HF_REPLY_MODEL` at a different provider does *not* grant a fresh quota — it's one pool across all of them.
- The frontend build (`backend/app/static/`) is git-ignored — a fresh clone needs `npm run build` (or `npm run dev`, or Docker) before `/` serves anything; the API itself works either way.
- Extracting *what* a task is about is still regex + `dateparser`, not ML-backed. Handles either word order for date/time ("Friday at 5pm" / "at 5pm Friday"), ordinal dates ("the 1st"), and splits a compound message into multiple tasks when each has its own explicit time — but phrasing well outside those patterns falls back to "I didn't understand that."
- Two `dateparser` quirks are worked around under the hood: it can pick the wrong "now" for a bare time without an explicit `RELATIVE_BASE`, and it misreads a bare ordinal like "the 1st" as a month rather than a day of month (ordinal dates are computed manually instead of via dateparser).
- The task-matching similarity threshold (0.68 cosine similarity) was calibrated on a small manual test set, not a proper eval, and has already been raised once after a real false match slipped through — `"dentist appointment"` scored 0.659 against an unrelated `"call mom"` task under the old 0.65 threshold, high enough to silently reschedule the wrong task. It may still need adjusting if it feels too eager or too conservative in practice.
- Meeting links only work if you paste one into the message yourself — no integration generates a fresh one for you.
- Recurrence supports `daily`/`weekly`/`monthly`/`yearly`/`weekday`, plus an arbitrary "every N days/weeks/months" custom interval — still no full RRULE support (e.g. "the last Friday of the month") and no per-user time zones (one global `APP_TIMEZONE` for the whole app, not per-user).
- The Docker setup hasn't been build-tested end-to-end (no Docker in this environment) — the frontend build and backend startup sequence were each verified individually, but the actual `docker build`/`docker compose up` hasn't run for real. Try it yourself before relying on it in production.
- Conversation titles are LLM-generated (same quota as reply rephrasing above), with a plain-truncation fallback.
- No authentication — single-user, local use for now, by design.
- No automated test suite yet, by design.
- No CI/CD pipeline configured, by design.

## License

MIT — see [LICENSE](LICENSE).
