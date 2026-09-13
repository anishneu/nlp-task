import time

import requests

from app.config import HF_REPLY_MODEL, HF_TOKEN

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

_quota_exhausted_until = 0.0


def _call_chat_completion(prompt: str, max_tokens: int, temperature: float) -> str | None:
    """Returns the model's response text, or None (never raises) whenever HF
    isn't configured, the call fails/times out, or the account's
    inference-provider quota is exhausted (HTTP 402) — in which case further
    calls are skipped for a cooldown window instead of paying the latency
    cost on every message.
    """
    global _quota_exhausted_until
    if not HF_TOKEN or time.time() < _quota_exhausted_until:
        return None
    try:
        response = requests.post(
            _API_URL,
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            json={
                "model": HF_REPLY_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=_TIMEOUT_SECONDS,
        )
        if response.status_code == 402:
            _quota_exhausted_until = time.time() + _QUOTA_COOLDOWN_SECONDS
            return None
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
    return content or None


def rephrase_reply(bot_name: str, original: str) -> str:
    """Rephrases an already-correct templated reply to sound more natural.

    Returns `original` unchanged whenever HF is unavailable — the rephrasing
    is purely cosmetic, so falling back to the plain template is always safe.
    """
    prompt = _REPHRASE_PROMPT.format(bot_name=bot_name, original=original)
    return _call_chat_completion(prompt, max_tokens=100, temperature=0.7) or original


def generate_title(first_message: str) -> str | None:
    """Generates a short conversation title from the first message.

    Returns None whenever HF is unavailable, so callers can fall back to a
    plain truncation of the message.
    """
    prompt = _TITLE_PROMPT.format(message=first_message)
    title = _call_chat_completion(prompt, max_tokens=20, temperature=0.5)
    return title.strip(' "\'') if title else None
