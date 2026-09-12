import requests

from app.config import HF_INTENT_MODEL, HF_TOKEN
from app.nlp.intents import Intent

_API_URL = f"https://api-inference.huggingface.co/models/{HF_INTENT_MODEL}"
_MIN_CONFIDENCE = 0.5
_TIMEOUT_SECONDS = 6

_LABEL_TO_INTENT = {
    "create a task or reminder": Intent.create_task,
    "list or show existing tasks": Intent.list_tasks,
    "mark a task as complete": Intent.complete_task,
    "delete a task": Intent.delete_task,
}


def classify_intent_hf(text: str) -> Intent | None:
    """Zero-shot intent classification via the HF Inference API.

    Returns None (never raises) whenever HF isn't configured or the call
    fails, so callers can fall back to the rule-based parser transparently.
    """
    if not HF_TOKEN:
        return None
    try:
        response = requests.post(
            _API_URL,
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            json={
                "inputs": text,
                "parameters": {"candidate_labels": list(_LABEL_TO_INTENT.keys())},
            },
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        top_label = data["labels"][0]
        top_score = data["scores"][0]
    except Exception:
        return None

    if top_score < _MIN_CONFIDENCE:
        return None
    return _LABEL_TO_INTENT.get(top_label)
