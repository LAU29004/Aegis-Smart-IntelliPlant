"""Split parsed pages into overlapping word-window chunks (~512 tokens / 50 overlap)."""
from ..config import CHUNK_OVERLAP_WORDS, CHUNK_SIZE_WORDS


def chunk_pages(pages: list[tuple[int, str]]) -> list[dict]:
    """Return chunks: {text, page}."""
    chunks: list[dict] = []
    for page_no, text in pages:
        words = text.split()
        if not words:
            continue
        step = max(CHUNK_SIZE_WORDS - CHUNK_OVERLAP_WORDS, 1)
        for start in range(0, len(words), step):
            piece = " ".join(words[start : start + CHUNK_SIZE_WORDS]).strip()
            if len(piece) < 20:
                continue
            chunks.append({"text": piece, "page": page_no})
            if start + CHUNK_SIZE_WORDS >= len(words):
                break
    return chunks
