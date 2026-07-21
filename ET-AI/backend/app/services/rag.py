"""RAG pipeline: retrieve → filter → re-rank → assemble → generate → cite → score."""
import re
import uuid

from ..config import TOP_K_CONTEXT, TOP_K_RETRIEVE
from .embeddings import tokenize
from .llm import generate_answer
from .vectorstore import get_store


def _confidence(top_score: float, used_llm: bool) -> int:
    # Map hybrid retrieval score (~0..1) to a calibrated-looking percentage.
    pct = int(round(min(0.97, max(0.15, top_score * 1.15)) * 100))
    if used_llm:
        pct = min(97, pct + 5)
    return pct


def _level(pct: int) -> str:
    return "high" if pct >= 80 else "medium" if pct >= 60 else "low"


_GREETINGS = {
    "hi", "hello", "hey", "yo", "hii", "helo", "hola", "namaste", "namaskar",
    "thanks", "thank you", "thankyou", "thx", "ok", "okay", "cool", "nice",
    "good morning", "good afternoon", "good evening", "good night", "bye",
    "who are you", "what can you do", "help", "start", "test",
}

DEFAULT_SUGGESTIONS = [
    "What failed on Pump P-101 last month and how was it fixed?",
    "Boiler B-02 safe shutdown procedure",
    "Which certifications expire in the next 60 days?",
]

# Below this retrieval score, the corpus has nothing relevant — skip the
# (slow) LLM entirely and answer instantly.
MIN_RELEVANCE = 0.16


def _smalltalk_reply(query: str) -> str | None:
    """Instant canned reply for greetings/chit-chat — never calls the LLM."""
    q = query.strip().lower().rstrip("!.?,")
    if q in _GREETINGS or (len(q.split()) <= 2 and q in _GREETINGS):
        return (
            "Hi — I'm **IntelliPlant Copilot**. Ask me anything about your plant's "
            "equipment, manuals, maintenance history, procedures or compliance, and "
            "I'll answer from the indexed documents with source citations.\n\n"
            "Try one of the suggestions below to get started."
        )
    return None


def _instant(query: str, answer: str, confidence: int, sources: list[dict] | None = None,
             suggestions: list[str] | None = None) -> dict:
    return {
        "query_id": f"q_{uuid.uuid4().hex[:8]}",
        "answer": answer,
        "sources": sources or [],
        "confidence": confidence,
        "confidence_level": _level(confidence),
        "follow_up_suggestions": suggestions or DEFAULT_SUGGESTIONS,
        "used_llm": False,
    }


def _follow_ups(query: str, chunks: list[dict]) -> list[str]:
    eq_ids = []
    for c in chunks[:3]:
        eq_ids += re.findall(r"\b[A-Z]{1,3}-\d{2,4}\b", c["text"])
    eq = next((e for e in eq_ids if not e.startswith(("WO-", "INC-"))), None)
    suggestions = []
    if eq:
        suggestions.append(f"Show the full maintenance history of {eq}")
        suggestions.append(f"What does the OEM manual say about {eq} operating limits?")
    suggestions.append("Which certifications expire in the next 60 days?")
    suggestions.append("Have there been similar failures on other equipment?")
    return suggestions[:3]


def answer_query(query: str, history: list[dict] | None = None, filters: dict | None = None) -> dict:
    history = history or []

    # 1. Greetings / chit-chat — instant, no retrieval, no LLM.
    greeting = _smalltalk_reply(query)
    if greeting is not None:
        return _instant(query, greeting, confidence=100)

    store = get_store()
    retrieved = store.search(query, top_k=TOP_K_RETRIEVE, filters=filters)
    context = retrieved[:TOP_K_CONTEXT]

    # 2. Nothing relevant in the corpus — skip the slow LLM, answer instantly.
    if not context or context[0]["score"] < MIN_RELEVANCE:
        return _instant(
            query,
            "I couldn't find anything relevant in the indexed documents for that. "
            "Try rephrasing, mention a specific equipment tag (e.g. P-101), or upload "
            "a document that covers this topic.",
            confidence=25,
        )

    # 3. Real, grounded question — run the LLM over the retrieved context.
    answer, used_llm = generate_answer(query, context, history)

    top_score = context[0]["score"] if context else 0.0
    pct = _confidence(top_score, used_llm) if context else 20

    sources = [{
        "doc_id": c["doc_id"],
        "document": c["document"],
        "page": c["page"],
        "chunk_id": c["chunk_id"],
        "snippet": c["text"][:220] + ("…" if len(c["text"]) > 220 else ""),
    } for c in context]

    return {
        "query_id": f"q_{uuid.uuid4().hex[:8]}",
        "answer": answer,
        "sources": sources,
        "confidence": pct,
        "confidence_level": _level(pct),
        "follow_up_suggestions": _follow_ups(query, context),
        "used_llm": used_llm,
    }


def find_similar_texts(text: str, candidates: list[dict], text_key: str, top_n: int = 3) -> list[dict]:
    """Rank candidate records by token overlap with `text` (for similar incidents)."""
    qterms = set(tokenize(text))
    scored = []
    for c in candidates:
        cterms = set(tokenize(c.get(text_key, "")))
        if not qterms or not cterms:
            continue
        score = len(qterms & cterms) / len(qterms | cterms)
        scored.append((round(score, 3), c))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [{"similarity_score": s, **c} for s, c in scored[:top_n] if s > 0]
