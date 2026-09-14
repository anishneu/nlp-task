# Custom To-Do Bot

Conversational task & reminder assistant — natural-language scheduling backed by a structured task API.

**Status: chat, task management, conversation history, scheduling/notifications, and a React frontend are all implemented and working.**

Custom To-Do Bot lets a user manage tasks the way they'd talk to a personal assistant — "remind me to submit my resume tomorrow at 9 AM" — instead of filling out a form. The design separates language understanding from execution: a parser turns a sentence into a structured intent + entities, a dialogue layer fills in anything missing (asking follow-up questions across turns), a plain REST API owns the actual task records, and a background scheduler keeps recurring reminders — and their notifications — on track. Every conversation is a persisted, resumable thread (ChatGPT-style history), and tasks can be starred, filtered, and viewed on a calendar.

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
- [Limitations](#limitations)

## What it does

Pipeline (chat-first assistant):

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
                                                                                     (PendingClarification, keyed by conversation_id)
                                                                                                      │
                                                                                                      ▼
                                                                          APScheduler (every 30s): fast-forwards any recurring
                                                                          task whose due date has passed to its next occurrence
                                                                                                      │
                                                                                                      ▼
                                                                  GET /reminders/due ──▶ in-app toast   +   opt-in email via SMTP
```

A message like `"Remind me to call Mom on Friday at 6 PM"` is classified into an intent (`create_task`), has its title and due date extracted, and is executed straight against the task store. Intent classification tries the Hugging Face Inference API first when `HF_TOKEN` is configured — zero-shot classification against six candidate labels: the four task actions plus "a greeting or friendly small talk" and "something unrelated to managing tasks or reminders", so casual chat (`"how are you doing?"`, `"thanks!"`) has a legitimate bucket instead of being force-fit into a task action — and transparently falls back to the regex classifier otherwise, so the bot works identically with zero setup, and gets a real ML model in the loop the moment you add a free token.

If a date is mentioned without a time (`"remind me to study tomorrow"`) — or a recurrence is given with no time at all (`"remind me to drink water every day"`) — the parser flags it as ambiguous and the bot asks a follow-up question instead of guessing. That follow-up is genuinely multi-turn: the frontend sends a `conversation_id` with every message, the backend remembers the pending question against it, and your very next message (`"10am"`, or `"the bank one"` when disambiguating between two similarly-named tasks) is interpreted as the answer rather than a fresh command. `"remind me to exercise every Monday at 7 AM"` sets up a recurring task directly; the same background APScheduler job that fast-forwards missed recurring tasks to their next future occurrence also emails (best-effort, opt-in via SMTP env vars) any due task that hasn't been notified yet — so a missed reminder always lands on the right future date, and gets a fresh notification each time it recurs. The bundled UI polls `GET /reminders/due` and pops an in-app toast notification for anything currently due, independent of whether email is configured.

The bot also handles basic small talk outside the task domain: a greeting (`"hi"`, `"hey"`) gets a friendly reply introducing itself, and asking it to rename itself (`"can I call you Romero"`) actually renames it — the reply carries the new name back to the frontend, which persists it to `localStorage` and updates the header, browser tab title, and input placeholder, exactly as if you'd used the manual Rename button.

Picking *which* task a `complete_task`/`delete_task` message refers to also goes through Hugging Face when configured: `"get rid of the dentist thing, not doing it anymore"` has no keyword overlap with a task titled `"call the dentist"`, but their sentence embeddings (`BAAI/bge-small-en-v1.5`, compared by cosine similarity) are close enough to resolve it correctly. Falls back to keyword-overlap matching when `HF_TOKEN` isn't set, same pattern as intent classification.

Every reply also passes through a small LLM (`google/gemma-2-2b-it`) that rephrases the deterministic template into something more conversational — the underlying facts (task titles, dates, links) are computed exactly as before and the LLM's only job is wording, so a "Got it — I've scheduled X for Y" can come back as "Sounds good, I'll remind you about X on Y!" without risking the actual data. Falls back to the plain template instantly if `HF_TOKEN` isn't set or the call fails for any reason (see [Limitations](#limitations) for a real caveat about this one's free-tier quota).

Every conversation is a real, persisted thread: a left sidebar lists past conversations (auto-titled from their first message), **New Chat** starts a fresh one, and clicking any past conversation reloads its full message history from the database — nothing lives only in browser memory. Pasting a meeting link into a message (`"remind me to join the standup at meet.google.com/abc-defg-hij tomorrow at 10am"` — also recognizes `zoom.us/...`, `teams.microsoft.com/...`, or any `https://` URL) attaches it to the task and shows it as a clickable "🎥 Join Meet" button on the task card and in the chat reply. Tasks can be starred as important, filtered by status or starred-only, and viewed either as a list or on a full month calendar grid (click a day to filter the list to it) — each task also shows a relative "created X ago" timestamp.

## Architecture

| Layer | Technology | Status |
|---|---|---|
| Backend | FastAPI, Pydantic schemas, SQLAlchemy ORM | Implemented |
| Database | SQLite (dev), swappable to MySQL/Postgres via `DATABASE_URL` | Implemented |
| NLP — intent classification | Hugging Face Inference API zero-shot (`facebook/bart-large-mnli`), 6 labels (4 task actions + greeting + off-topic), opt-in via `HF_TOKEN`, with a regex classifier as automatic fallback | Implemented |
| NLP — task matching | Hugging Face sentence embeddings (`BAAI/bge-small-en-v1.5`, cosine similarity) to resolve which task a vague/indirect phrase refers to, opt-in via `HF_TOKEN`, with keyword-overlap matching as automatic fallback | Implemented |
| Conversational tone | Hugging Face chat-completion (`google/gemma-2-2b-it`, configurable via `HF_REPLY_MODEL`) rephrases each deterministic reply to sound natural, opt-in via `HF_TOKEN`, with the plain template as automatic fallback | Implemented |
| NLP — entities (dates/times/recurrence/links) | Regex + `dateparser` | Implemented (rule-based) |
| Dialogue state | Per-conversation `PendingClarification` (DB-backed), multi-turn follow-up answers | Implemented |
| Conversation history | `Conversation` + `Message` tables; sidebar lists/switches/deletes threads, full history reloads on select | Implemented |
| Meeting links | Regex extraction of pasted meeting URLs (Meet/Zoom/Teams/any `https://` link) from a message, attached to the task | Implemented |
| Task organization | `starred` flag, status + starred-only filters, list/calendar views, relative "created X ago" timestamps | Implemented |
| Scheduling | APScheduler background job: recurrence advancement + due-reminder notification | Implemented |
| Notifications | In-app toasts (`/reminders/due` polling) always on; email via SMTP opt-in (`smtplib`, stdlib — no extra dependency) | Implemented |
| Frontend | React 19 + TypeScript + Tailwind CSS 4, built with Vite; landing page → sidebar + chat + tasks; served by FastAPI at `/` in production, or `npm run dev` (proxied) for local development | Implemented |
| Infra | Docker Compose (`docker-compose.yml` + `backend/Dockerfile`, multi-stage: builds the frontend, then the API image), named volume for SQLite persistence | Implemented |

## Scale

Counted directly from the codebase, not estimated:

| Metric | Count |
|---|---|
| REST API endpoints | 11, across 4 route modules |
| Database tables | 4 (`tasks`, `pending_clarifications`, `conversations`, `messages`) |
| Task lifecycle states | 2 (`pending`, `completed`) |
| Chat intents recognized | 6 (`create_task`, `list_tasks`, `complete_task`, `delete_task`, `greeting`, `set_name`) |
| Recurrence cadences | 3 (`daily`, `weekly`, `monthly`) |
| Dialogue follow-up kinds | 2 (ambiguous time, ambiguous task choice) |
| Notification channels | 2 (in-app toast, opt-in email) |
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
# terminal 1
cd backend && uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend && npm run dev
```

Open `http://localhost:3000/` — Vite proxies `/tasks`, `/chat`, `/reminders`, and `/health` to the backend, so no CORS setup is needed. `http://127.0.0.1:8000/docs` still has the raw API.

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
│   │   ├── models.py               SQLAlchemy models: Task, PendingClarification, Conversation, Message
│   │   ├── schemas.py              Pydantic request/response models
│   │   ├── crud.py                 Database operations
│   │   ├── database.py             Engine/session setup
│   │   ├── scheduler.py            APScheduler job: recurrence advancement + due-reminder emails
│   │   ├── notifications.py        Best-effort SMTP email sender (stdlib smtplib, opt-in)
│   │   ├── nlp/
│   │   │   ├── intents.py          Intent enum
│   │   │   ├── hf_intent.py        Hugging Face zero-shot intent classification (falls back to None on any failure)
│   │   │   ├── hf_similarity.py    Hugging Face sentence embeddings for semantic task matching (falls back to None on any failure)
│   │   │   ├── hf_reply.py         Hugging Face chat-completion: rephrases replies conversationally (falls back to the original reply on any failure)
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

- All three HF-backed features (intent classification, task matching, reply tone) only call a real ML model when `HF_TOKEN` is set; without it, the app runs entirely on regex/template fallbacks. All six paths are live-verified: every fallback (no token) and every real call against the current Hugging Face endpoints (`router.huggingface.co/hf-inference/...` for classification/embeddings — note this replaced the older `api-inference.huggingface.co` endpoint, which HF has retired; `router.huggingface.co/v1/chat/completions` for reply rephrasing).
- **Reply rephrasing draws from a much smaller quota than the other two HF features.** Intent classification and task matching run on HF's own free `hf-inference` provider; reply rephrasing goes through HF's router to a third-party provider (`featherless-ai` by default), billed against a small shared monthly "included credits" allowance across *all* third-party providers — it was exhausted just from testing this feature during development. When that happens, `POST /chat` still works exactly the same, just with the plain template reply instead of the rephrased one (verified — no errors, no delay beyond the fallback path). A circuit breaker now short-circuits further calls for a 5-minute cooldown as soon as HF returns a 402 (quota exhausted), instead of paying the request latency on every subsequent message. Options if you hit this: wait for the monthly reset, add pre-paid credits or a PRO subscription on Hugging Face, or point `HF_REPLY_MODEL` at a different provider (each has its own separate quota).
- The frontend build (`backend/app/static/`) is git-ignored — it's generated by `npm run build`, not committed source. A fresh clone needs that build step (or `npm run dev`, or Docker) before `/` serves anything; the API itself (`/tasks`, `/chat`, etc.) works either way.
- Extracting *what* a task is about (the title/description text itself) is still regex + `dateparser` only, even with `HF_TOKEN` set — only intent classification and task matching are ML-backed. Phrasing well outside the recognized patterns falls back to "I didn't understand that." Explicit keyword triggers (e.g. "remind"/"reminder", "delete", "mark ... done") are matched deterministically before the intent classifier is consulted at all, so the classifier is only in the loop for genuinely ambiguous phrasing (casual chat, indirect requests) rather than overriding a clear signal. Date/time phrases are recognized in either word order ("Friday at 5pm" or "at 5pm Friday"), with or without the word "at", and "tonight" is handled as a dateparser-specific quirk the same way "this/next Saturday" already was.
- The task-matching similarity threshold (0.65 cosine similarity) was calibrated against a small manual test set, not a proper eval — re-verified against a fresh batch of vague/paraphrased queries ("the bank one", "the dentist thing", "shopping") and it held up (correct match every time, correctly returned no match for unrelated input), but it's still not a proper eval and may need adjusting if real usage feels too eager or too conservative.
- Meeting links only work if you paste one into the message yourself — there's no integration that generates a fresh link for you (e.g. a real Google Calendar event). Recognizes `meet.google.com/...`, `zoom.us/...`, `teams.microsoft.com/...`, and any `https://` URL.
- Recurrence is limited to `daily` / `weekly` / `monthly` cadences on a single task row (no full RRULE support, no per-occurrence history, no "every weekday"/yearly) and there's no time zone handling — all dates and timestamps are naive local server time, consistently, end to end. Monthly recurrence now advances by a real calendar month (via `dateutil.relativedelta`, jumping from the original due date each time) instead of a flat 30-day step, so a task due on the 31st lands on the last day of each following month instead of drifting a little later every cycle.
- Email notifications are opt-in via SMTP env vars and best-effort (no retry beyond the next scheduler tick); not tested against a live SMTP server in this environment — the no-SMTP-configured fallback path is what's been verified.
- The Docker setup (`Dockerfile` + `docker-compose.yml`, multi-stage: Node build → Python runtime) hasn't been build-tested in this environment (no Docker available here) — reviewed for correctness, but verify `docker compose up --build` yourself before relying on it. `.dockerignore` now excludes `backend/app/static` and `.git`, so a locally-built frontend or your git history can't leak stale files into the image or bloat the build context.
- Conversation titles are generated by the same reply LLM (falling back to the first ~60 characters of the first message when HF is unavailable or the call fails) — so title quality tracks the reply-rephrasing quota above. The generic "I didn't understand that" fallback reply is deliberately never sent through the rephrasing LLM — it embeds a quoted usage example, and a small model occasionally misread that as literal context and fabricated an unrelated detail (e.g. asking about "Mom" in a conversation that never mentioned her); the plain, reliable template is used for that one case instead.
- The SQLite schema self-heals additively on startup (new tables/columns from model changes are added automatically), which covers the common single-developer case of pulling a change that adds a field — but it's not a substitute for real migrations (no column removal/renaming, no data backfill) if you ever need those.
- No authentication — single-user, local use for now, by design.
- No automated test suite yet, by design.
- No CI/CD pipeline configured, by design.

## License

MIT — see [LICENSE](LICENSE).
