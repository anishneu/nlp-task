import time

import requests

from app.config import HF_REPLY_FALLBACK_MODEL, HF_REPLY_MODEL, HF_TOKEN

_API_URL = "https://router.huggingface.co/v1/chat/completions"
_TIMEOUT_SECONDS = 12
_QUOTA_COOLDOWN_SECONDS = 300

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

    Returns `original` unchanged whenever HF is unavailable — the rephrasing
    is purely cosmetic, so falling back to the plain template is always safe.
    """
    prompt = _REPHRASE_PROMPT.format(bot_name=bot_name, original=original)
    return _call_with_fallback(prompt, max_tokens=100, temperature=0.7) or original


def generate_title(first_message: str) -> str | None:
    """Generates a short conversation title from the first message.

    Returns None whenever HF is unavailable, so callers can fall back to a
    plain truncation of the message.
    """
    prompt = _TITLE_PROMPT.format(message=first_message)
    title = _call_with_fallback(prompt, max_tokens=20, temperature=0.5)
    return title.strip(' "\'') if title else None
