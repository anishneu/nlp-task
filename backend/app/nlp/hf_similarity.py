import math

import requests

from app.config import HF_TOKEN

_MODEL = "BAAI/bge-small-en-v1.5"
_API_URL = f"https://router.huggingface.co/hf-inference/models/{_MODEL}"
_MIN_SIMILARITY = 0.65
_TIMEOUT_SECONDS = 8


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def find_best_match_hf(query: str, candidates: list[str]) -> int | None:
    """Semantic best match for `query` among `candidates`, via HF sentence embeddings.

    Returns the index into `candidates`, or None (never raises) whenever HF
    isn't configured, the call fails, or nothing clears the similarity
    threshold — callers should fall back to keyword matching either way.
    """
    if not HF_TOKEN or not candidates:
        return None
    try:
        response = requests.post(
            _API_URL,
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            json={"inputs": [query, *candidates]},
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        query_vec, *candidate_vecs = response.json()
    except Exception:
        return None

    scores = [_cosine(query_vec, vec) for vec in candidate_vecs]
    best_index = max(range(len(scores)), key=lambda i: scores[i])
    if scores[best_index] < _MIN_SIMILARITY:
        return None
    return best_index
