import json

from app.nlp.hf_reply import _call_with_fallback

_SEGMENT_PROMPT = (
    "Split the following message into separate task/reminder descriptions, one per "
    "distinct event. For each one, copy its own wording VERBATIM from the message, "
    "including its date/time phrase — do not summarize, reword, or compute any dates "
    "yourself. Ignore filler that isn't its own event (e.g. \"could you remind me\", "
    "\"I've got a few things to do today\"). Return ONLY a JSON array of strings, "
    "nothing else — no markdown, no explanation, no code fences.\n\n"
    "Message: {message}\n\nJSON array:"
)


def segment_events_hf(text: str) -> list[str] | None:
    """Splits a message describing multiple events into one text snippet per
    event, via a small LLM.

    Used only as a fallback when the regex-based clause splitter (see
    app.nlp.parser) finds signs of multiple events — 2+ phrases with their
    own explicit time — but can't confidently separate them itself (e.g. no
    recognized conjunction between them). Calling this on every message
    would burn through the same small shared HF quota used for reply
    rephrasing; restricting it to that specific situation keeps it rare.

    Returns None (never raises) whenever HF is unavailable, the call fails,
    or the response isn't valid JSON — callers fall back to single-task
    parsing either way. Deliberately asks the model to segment ONLY, never
    to compute a date itself: each returned snippet is re-run through the
    same regex + dateparser pipeline used everywhere else in this app, so a
    hallucinated or misread date can never slip through untested — at worst
    a bad segment fails that pipeline's usual title/time checks and gets
    dropped, same as a bad regex-found segment would.
    """
    prompt = _SEGMENT_PROMPT.format(message=text)
    raw = _call_with_fallback(prompt, max_tokens=300, temperature=0.2)
    if not raw:
        return None

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        segments = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(segments, list) or not all(isinstance(s, str) for s in segments):
        return None
    return [s.strip() for s in segments if s.strip()]
