import re
import time

import requests

from app.config import HF_REPLY_ENABLED, HF_REPLY_FALLBACK_MODEL, HF_REPLY_MODEL, HF_TOKEN

_API_URL = "https://router.huggingface.co/v1/chat/completions"
_TIMEOUT_SECONDS = 12
_QUOTA_COOLDOWN_SECONDS = 300
# Small connector words that "polishing" a title can legitimately introduce
# even though they weren't literally in the original wording (e.g. adding
# "to" when tightening "submit my resume, google" into "submit resume to
# google") — anything else that shows up in a polished title but wasn't in
# the original is treated as a possible fabrication, not a paraphrase.
_TITLE_SAFE_EXTRA_WORDS = {
    "a", "an", "the", "to", "with", "for", "and", "at", "on", "in", "of",
    "my", "your", "his", "her", "our", "their",
}

_REPHRASE_PROMPT = (
    "You are {bot_name}, a friendly task and reminder assistant. "
    "Rephrase the following reply to sound more natural and conversational, in 1-2 short sentences. "
    "Keep every fact EXACTLY the same (names, dates, times, links) — do not add, remove, or change "
    "any fact. Do not use markdown. Do not repeat these instructions.\n\n"
    "Original reply: {original}\n\nRephrased reply:"
)

_TITLE_PROMPT = (
    "Summarize the following message as a short chat conversation title, 3-6 words, "
    "no punctuation at the end, no quotes. Just output the title itself, nothing else.\n\n"
    "Message: {message}\n\nTitle:"
)

_TASK_TITLE_PROMPT = (
    "Rewrite the following task description as a short, clean task title, 2-6 words, "
    "no punctuation at the end, no quotes, no leading articles like \"a\"/\"the\". "
    "Keep the same meaning and keep any names/companies exactly as given — don't add "
    "new information or change what the task is about. Just output the title itself, "
    "nothing else.\n\n"
    "Description: {text}\n\nTitle:"
)

# Per-model cooldown — HF_REPLY_MODEL and HF_REPLY_FALLBACK_MODEL are tracked
# separately since a 402 on one says nothing about whether the other's own
# cooldown should apply.
_cooldown_until: dict[str, float] = {}


def _call_chat_completion(model: str, prompt: str, max_tokens: int, temperature: float) -> tuple[str | None, bool]:
    """Returns (content, quota_exhausted). content is None (never raises)
    whenever HF isn't configured, the call fails/times out, or the model
    isn't set — quota_exhausted is only ever true on an HTTP 402 (or while
    still in that cooldown), so callers can tell "try the fallback, this
    provider just had a bad moment" apart from "don't bother, we're out of
    the shared credit pool" (see _call_with_fallback).
    """
    global _cooldown_until
    if not HF_TOKEN or not model:
        return None, False
    if time.time() < _cooldown_until.get(model, 0.0):
        return None, True
    try:
        response = requests.post(
            _API_URL,
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=_TIMEOUT_SECONDS,
        )
        if response.status_code == 402:
            _cooldown_until[model] = time.time() + _QUOTA_COOLDOWN_SECONDS
            return None, True
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None, False
    return (content or None), False


def _call_with_fallback(prompt: str, max_tokens: int, temperature: float) -> str | None:
    """Tries HF_REPLY_MODEL, then HF_REPLY_FALLBACK_MODEL if the first call
    fails for a reason other than quota exhaustion.

    HF's free third-party "included credits" quota is a single pool shared
    across every provider on the router (confirmed by testing — it isn't
    metered per provider), so a fallback model gains nothing when the
    primary genuinely hit a 402; the fallback would draw against the same
    exhausted pool and fail the same way, just after paying for a second
    round trip. What the fallback DOES help with is everything else that
    can take a single provider down without touching the shared quota at
    all — a timeout, a connection error, or a provider-specific capacity
    error (seen in practice: "Insufficient capacity... All endpoints at
    capacity" from a provider whose credits were otherwise fine).
    """
    content, quota_exhausted = _call_chat_completion(HF_REPLY_MODEL, prompt, max_tokens, temperature)
    if content is not None:
        return content
    if quota_exhausted:
        return None
    content, _ = _call_chat_completion(HF_REPLY_FALLBACK_MODEL, prompt, max_tokens, temperature)
    return content


def rephrase_reply(bot_name: str, original: str) -> str:
    """Rephrases an already-correct templated reply to sound more natural.

    Returns `original` unchanged — with no network call at all — whenever
    HF_REPLY_ENABLED is off (the default; see config.py) or HF is
    unavailable. The rephrasing is purely cosmetic, so falling back to the
    plain template is always safe.
    """
    if not HF_REPLY_ENABLED:
        return original
    prompt = _REPHRASE_PROMPT.format(bot_name=bot_name, original=original)
    rephrased = _call_with_fallback(prompt, max_tokens=100, temperature=0.7)
    if not rephrased:
        return original
    # Small models sometimes wrap the whole reply in quotes as if quoting
    # themselves back (seen live: `"When is your interview...?"` instead of
    # just the sentence) — strip a wrapping pair, same cleanup
    # generate_title() already does for titles. Only touches the two ends,
    # so a quote legitimately inside the sentence (e.g. around a task
    # title) is untouched.
    return rephrased.strip(' "\'') or original


def generate_title(first_message: str) -> str | None:
    """Generates a short conversation title from the first message.

    Returns None — with no network call at all — whenever HF_REPLY_ENABLED
    is off (the default) or HF is unavailable, so callers fall back to a
    plain truncation of the message.
    """
    if not HF_REPLY_ENABLED:
        return None
    prompt = _TITLE_PROMPT.format(message=first_message)
    title = _call_with_fallback(prompt, max_tokens=20, temperature=0.5)
    return title.strip(' "\'') if title else None


def _title_is_safe(original: str, polished: str) -> bool:
    """Rejects a polished title that introduces a word not present in the
    original (beyond ordinary connector words) — a cheap but real guard
    against the model inventing a fact that was never there. Confirmed
    live: asked to polish "dinner date" it came back as "Dinner date with
    Sarah" — a fabricated name with zero basis in the source text. Titles
    don't get the same regex+dateparser re-verification dates do, so this
    check is what stands between a hallucination and the task list.
    """
    # Apostrophes stripped before comparing so a possessive the model adds
    # or normalizes ("bachelors" -> "bachelor's") isn't flagged as a new
    # word — it's the same word, just punctuated differently.
    original_words = set(re.findall(r"[a-z]+", original.lower().replace("'", "")))
    polished_words = set(re.findall(r"[a-z]+", polished.lower().replace("'", "")))
    return not (polished_words - original_words - _TITLE_SAFE_EXTRA_WORDS)


def summarize_task_title(raw_title: str) -> str | None:
    """Polishes a task title already extracted by the regex parser (date
    and time already removed) into a short, clean title.

    The parser's regex-based filler-stripping only catches the specific
    patterns it's been taught ("I've got a", "followed by another", ...) —
    it can never generalize to arbitrary phrasing the way summarization
    can. Only ever touches wording, never dates/times (those are already
    gone from `raw_title` before this runs), so it can't introduce the
    hallucinated-date risk the rest of the app is careful to avoid — but it
    can still invent words that were never in the source (see
    _title_is_safe), so every result is checked before being trusted.

    Returns None — with no network call at all — whenever HF_REPLY_ENABLED
    is off (the default) or HF is unavailable, or the result doesn't pass
    the fabrication check, so callers fall back to the regex-cleaned title
    as-is either way.
    """
    if not HF_REPLY_ENABLED:
        return None
    prompt = _TASK_TITLE_PROMPT.format(text=raw_title)
    title = _call_with_fallback(prompt, max_tokens=20, temperature=0.3)
    if not title:
        return None
    title = title.strip(' "\'')
    if not title or not _title_is_safe(raw_title, title):
        return None
    return title
