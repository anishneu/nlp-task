import requests

from app.config import HF_REPLY_MODEL, HF_TOKEN

_API_URL = "https://router.huggingface.co/v1/chat/completions"
_TIMEOUT_SECONDS = 12

_PROMPT = (
    "You are {bot_name}, a friendly task and reminder assistant. "
    "Rephrase the following reply to sound more natural and conversational, in 1-2 short sentences. "
    "Keep every fact EXACTLY the same (names, dates, times, links) — do not add, remove, or change "
    "any fact. Do not use markdown. Do not repeat these instructions.\n\n"
    "Original reply: {original}\n\nRephrased reply:"
)


def rephrase_reply(bot_name: str, original: str) -> str:
    """Rephrases an already-correct templated reply to sound more natural.

    Returns `original` unchanged (never raises) whenever HF isn't configured
    or the call fails/times out — the rephrasing is purely cosmetic, so a
    fallback to the plain template is always safe.
    """
    if not HF_TOKEN:
        return original
    try:
        response = requests.post(
            _API_URL,
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            json={
                "model": HF_REPLY_MODEL,
                "messages": [
                    {"role": "user", "content": _PROMPT.format(bot_name=bot_name, original=original)}
                ],
                "max_tokens": 100,
                "temperature": 0.7,
            },
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return original
    return content or original
