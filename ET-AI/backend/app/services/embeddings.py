"""Text embeddings with graceful degradation.

Preferred: sentence-transformers multilingual model (if installed).
Fallback: pure-python feature-hashing embedder (unigrams + bigrams, signed
hashing trick, L2-normalised) — dependency-free and deterministic, good
enough for semantic-ish retrieval over a demo corpus.
"""
import hashlib
import math
import re

DIM = 512
_TOKEN = re.compile(r"[a-z0-9°]+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "was", "were", "be", "been", "at", "by", "with", "from", "as", "it", "its",
    "this", "that", "these", "those", "shall", "should", "must", "will", "can",
}

_st_model = None
_backend = None


def _try_sentence_transformers():
    global _st_model
    try:
        from sentence_transformers import SentenceTransformer

        _st_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        return True
    except Exception:
        return False


def get_backend() -> str:
    global _backend
    if _backend is None:
        _backend = "sentence-transformers" if _try_sentence_transformers() else "hashing-512"
    return _backend


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


def _hash_embed(text: str) -> list[float]:
    vec = [0.0] * DIM
    tokens = tokenize(text)
    grams = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
    for g in grams:
        h = hashlib.md5(g.encode()).digest()
        bucket = int.from_bytes(h[:4], "little") % DIM
        sign = 1.0 if h[4] % 2 == 0 else -1.0
        vec[bucket] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def embed_texts(texts: list[str]) -> list[list[float]]:
    if get_backend() == "sentence-transformers":
        return [list(map(float, v)) for v in _st_model.encode(texts, show_progress_bar=False)]
    return [_hash_embed(t) for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return num / (na * nb)
