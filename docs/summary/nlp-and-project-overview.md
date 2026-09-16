# TodoWeave — NLP & Project Overview

This document explains what natural language processing (NLP) means in practice, and exactly how TodoWeave uses it — which parts are classic rule-based text processing, which parts call a real machine learning model, and why the system is built as a layered fallback chain instead of leaning on one model for everything.

## 1. What "NLP" actually covers here

"NLP" isn't one technique — it's an umbrella over several distinct problems, and TodoWeave touches most of them:

| NLP task | Plain-English question it answers | Where TodoWeave does this |
|---|---|---|
| **Intent classification** | "What is the user trying to *do*?" | Deciding whether a message is a request to create, list, complete, delete, or reschedule a task (or just a greeting) |
| **Named-entity / slot extraction** | "What are the specific *facts* in this sentence?" | Pulling a date, a time, a recurrence rule, a task title, or a meeting link out of free text |
| **Zero-shot classification** | "Which of these labels fits, without training on examples of each?" | A general-purpose model scores the message against task-domain labels it's never been fine-tuned on |
| **Semantic similarity** | "Do these two phrases mean the same thing, even with no shared words?" | Matching `"the dentist thing"` to a task titled `"call the dentist"` |
| **Text generation / summarization** | "Can a model produce new, fluent text from a prompt?" | Rephrasing a templated reply conversationally, generating a conversation title, condensing a raw task description into a clean title |

Two very different implementation strategies show up across that table:

- **Rule-based / symbolic**: regular expressions and the `dateparser` library. Deterministic, instant, free, and fully explainable — but only as good as the patterns someone thought to write.
- **Statistical / neural**: pretrained transformer models called over the Hugging Face Inference API. Generalizes to phrasing nobody anticipated — but costs latency (seconds, not milliseconds), depends on network availability, and can be wrong in ways that are much harder to predict than a missed regex.

TodoWeave's core design decision is to **never depend on the neural half alone**. Every ML call has a deterministic fallback, and every ML output that could smuggle in a fabricated fact gets re-verified by rule-based code before it reaches the database. The sections below walk through exactly how.

## 2. The pipeline, end to end

```
User message
     │
     ▼
Regex intent classifiers (instant, free, deterministic)
     │  no confident match?
     ▼
HF zero-shot classification — facebook/bart-large-mnli  (only if HF_TOKEN is set)
     │  still nothing (HF unset/unavailable/low-confidence)?
     ▼
Heuristic fallback: "mentions a date, isn't phrased as a question" → assume create_task
     │
     ▼
Regex + dateparser entity extraction (title, date/time, recurrence, link)
     │  message looks like it describes 2+ events but regex can't cleanly split them?
     ▼
HF segmentation — a small chat-completion model splits the raw text into
per-event snippets (never computes dates itself — see §3.3)
     │
     ▼
Task created / task looked up (semantic match via HF sentence embeddings,
falling back to keyword overlap) / clarification question asked
     │
     ▼
Reply built from a local phrasing template
     │  HF_REPLY_ENABLED?
     ▼
LLM rephrases the reply + (on a new conversation) generates a title
```

Every arrow that leaves the rule-based path and enters an HF call is optional and monitored: if the call fails, times out, or the account's free quota is exhausted, execution falls straight back to the deterministic behavior on the left. The user should never see "the AI is down" — worst case, replies get a little more templated and title-polishing stops happening.

## 3. Component-by-component

### 3.1 Intent classification (`app/nlp/parser.py`, `app/nlp/hf_intent.py`)

The first pass is a stack of regexes tuned on real conversation logs from this project — `remind`/`reminder` for creation, `mark ... done` for completion, `delete`/`remove`/`cancel`, `reschedule`/`postpone`/`update`, `show`/`list ... tasks`, and so on. These are checked in a fixed priority order (delete/update/complete/list/create) because a phrase like *"can you reschedule..."* would otherwise be ambiguous between "create" and "update" if checked in the wrong order.

Only when **none** of those triggers fire does the message go to Hugging Face's zero-shot classifier (`facebook/bart-large-mnli` by default, swappable via `HF_INTENT_MODEL`). Zero-shot means the model was never fine-tuned on this app's specific categories — instead, it's handed the raw text plus seven candidate label *sentences* (`"create a task or reminder"`, `"a greeting or friendly small talk"`, etc.) and scores how well each one entails the input. A result below 50% confidence, or any network/timeout failure, is treated as "no answer" — the request never raises an error, it just returns `None` and the caller moves on.

If even that comes back empty, a last heuristic runs: **does the message contain a recognizable date/time phrase, and is it not phrased as a question?** If so, it's overwhelmingly more likely someone is describing a new task ("I have a dentist appointment Friday at 2") than anything else a task bot would be asked, so it's treated as `create_task` rather than giving up with "I didn't understand."

### 3.2 Entity extraction — dates, times, recurrence, links

This is deliberately **not** ML-backed. Dates and times need to be *exactly right* — a hallucinated date is worse than no date — so this layer is entirely regex + the `dateparser` library, with the outputs sanity-checked, never guessed:

- A bare ambiguous hour (`"at 5"`, no am/pm) is *not* passed straight to `dateparser`, which was confirmed (via direct testing) to confidently resolve it to a nonsensical date rather than fail cleanly. Instead, nearby period-of-day words (`"evening"`, `"morning"`) are used to infer am/pm; if there's no such clue, the time is left unresolved rather than guessed.
- `dateparser` fails outright on some very natural phrasings that mean something perfectly clear to a person — `"10am in the morning"`, `"tonight"`, `"the next 2 hrs"`, `"the 1st"` (which it misreads as *next January* rather than *day 1 of this month*). Each of these has a small, targeted normalization step before the string reaches `dateparser`, backed by a live regression test that reproduced the exact failure first.
- Recurrence phrases (`"every Monday"`, `"every 3 days"`, `"every weekday"`) are parsed into a small fixed vocabulary of recurrence rules, not a full RRULE grammar — enough for the common cases, explicitly not attempting calendar-spec completeness.

### 3.3 Multi-event / multi-task messages

A message like *"an interview at 2pm and a birthday party at 7pm"* needs to become two separate tasks, not one garbled one. The regex layer splits on conjunctions and sentence boundaries it recognizes (`"and"`, `"then"`, `". "`, …) and tries to resolve a clean title + explicit time out of each resulting clause; a clause that doesn't resolve is silently dropped rather than forcing the whole message to fail (it's usually connective filler like *"I've got a few things to do today"*, not a real missed event).

When the regex splitter finds **fewer** resolved specs than there are distinct explicit-time phrases in the message, that's a strong signal something got missed or merged — for example a comma-joined list with no recognized conjunction. Only then does it escalate to a small HF chat-completion model whose *only* job is to copy out one text snippet per event, verbatim, from the original message. Critically, **this model never computes a date** — every snippet it returns is re-run through the exact same regex + `dateparser` extraction used everywhere else, so a hallucinated or misread date literally cannot reach the database through this path; at worst, a bad snippet just fails the same title/time checks a bad regex clause would and gets dropped.

### 3.4 Semantic task matching (`app/nlp/hf_similarity.py`)

Resolving *which* existing task a vague reference means (`"cancel the dentist thing"`) starts with straightforward keyword overlap, but that fails on paraphrases with zero shared words. When `HF_TOKEN` is set, the query and every candidate task title are embedded with `BAAI/bge-small-en-v1.5` (a sentence-embedding model, not a chat model), and matched by cosine similarity against a calibrated threshold of **0.68**.

That threshold isn't a guess — it was raised from an initial 0.65 after a real false match slipped through in testing (`"dentist appointment"` scored 0.659 against an unrelated `"call mom"` task, just over the old bar). A broader manual test set showed a clean separation between the highest false-match score (0.659) and the lowest genuine-match score (0.697); 0.68 sits in the middle of that gap.

### 3.5 Conversational tone — local phrasing vs. LLM rephrasing (`app/nlp/phrasing.py`, `app/nlp/hf_reply.py`)

Every reply type (confirming a task, asking a follow-up, reporting an error) has 3–4 hand-written phrasing variants, picked at random. This is the *default* behavior — zero network calls, zero latency, and enough variety that a multi-message conversation doesn't read as the same three sentences on repeat.

On top of that, `HF_REPLY_ENABLED` (off by default) layers an actual LLM rephrase (`google/gemma-2-2b-it` via the HF Inference router, with a fallback model tried only on a non-quota failure) that reworks whichever template got picked into fully custom wording — the underlying facts (titles, dates, links) are computed beforehand and only the *wording* is up to the model. This is off by default specifically because it's the one HF feature that fires on **nearly every message** rather than situationally, and free-tier chat-completion latency (2–6s+, sometimes worse) would otherwise dominate response time.

### 3.6 Task title polishing — and the fabrication guard

Raw regex-extracted titles are sometimes rough (`"buy milk and eggs"`, or worse, leftover filler that a plain pattern-list couldn't anticipate). `summarize_task_title()` asks a small LLM to tighten a title to 2–6 words. Because a generative model can invent things that were never in the source — confirmed live, asking it to polish `"dinner date"` once came back as `"Dinner date with Sarah"`, a fabricated name with zero basis in the text — every polished title is checked by `_title_is_safe()` before being trusted: if the polished version contains any word (beyond ordinary connectors like "a"/"the"/"with") that wasn't in the original, it's rejected outright and the app falls back to the plain regex-cleaned title. This is the same underlying principle as the multi-event segmentation guard in §3.3: an LLM is allowed to *rephrase*, never to silently *introduce* a fact.

### 3.7 Dialogue state — multi-turn clarification

Not every message resolves on its own. `"remind me to study tomorrow"` has a date but no time; `"reschedule the meeting"` might match two different tasks. Rather than guessing, the bot asks a follow-up and remembers exactly what it's waiting for (`PendingClarification`, keyed by conversation) — `awaiting_time` or `awaiting_task_choice` — so the next message is interpreted as the *answer* rather than a fresh command. A message carrying its own strong command trigger is deliberately exempted from this, so a genuinely new request typed while a question is pending doesn't get silently swallowed into the old one.

### 3.8 Compound multi-action messages

*"Reschedule the interview to Friday and delete the dentist task"* names two different *actions* on two different tasks in one message — a different problem from §3.3's multi-*task-creation*. `split_compound_actions()` splits the message into clauses and classifies each independently, only committing to this path when 2+ clauses resolve to genuinely *different* intents (an all-`create_task` split is deliberately left to the dedicated multi-task pipeline in §3.3 instead, which already has LLM-segmentation escalation this simpler splitter doesn't reimplement). Each resolved clause executes fully with no further questions asked — a compound message commits to reporting a clear per-clause result ("rescheduled X; couldn't find a task matching Y") rather than opening a second, nested clarification the single-slot pending-question system has no way to represent.

## 4. Design principles this project follows

1. **Deterministic first, ML as an enhancement.** Every regex-based path works completely with zero configuration and zero network access; Hugging Face only ever raises the ceiling, it's never required to reach the floor.
2. **Never let a generative model author a fact it could get wrong.** Dates are always computed by `dateparser` against text a human actually wrote, never by an LLM. Task titles are checked against the words that were already there. Multi-event segmentation only ever copies text, never invents timing.
3. **Free-tier by construction.** No paid LLM API is used anywhere — every model call goes through Hugging Face's free Inference API, with cooldowns and a fallback model to absorb a single provider having a bad moment.
4. **Fail toward "still usable," not toward an error page.** Every HF call function returns `None`/falls back on *any* exception — timeout, quota exhaustion, malformed response — rather than raising, so a flaky third-party call degrades the experience instead of breaking it.
5. **Latency-conscious by default.** The one feature that would run on nearly every message (LLM rephrasing) is opt-in rather than on-by-default, specifically because it's the dominant cost in response time — everything situational (intent classification, task matching) stays on by default since it's cheap in aggregate.

## 5. Where this lives in the code

```
backend/app/nlp/
├── intents.py        Intent enum — the small fixed vocabulary everything else classifies into
├── parser.py          Regex intent classification + date/time/recurrence/link extraction (rule-based core)
├── hf_intent.py        Zero-shot intent classification (facebook/bart-large-mnli)
├── hf_similarity.py     Semantic task matching (BAAI/bge-small-en-v1.5, cosine similarity)
├── hf_reply.py          Reply rephrasing, conversation titles, task title polishing + fabrication guard
├── hf_segment.py         Multi-event text segmentation (verbatim-only, never computes dates)
└── phrasing.py            Local, zero-latency reply wording variants (the always-on baseline)

backend/app/services/chat.py   Wires all of the above into one turn of the conversation:
                                pending-question check → compound-action check → single-intent
                                dispatch → task CRUD → reply assembly → optional rephrase/title pass
```

See the main [README](../../README.md) for setup, the full architecture table, and the current list of known limitations.
