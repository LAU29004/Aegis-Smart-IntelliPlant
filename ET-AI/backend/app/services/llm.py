"""Answer generation with three tiers, chosen automatically at runtime:

  1. Claude API      — best quality, needs internet + ANTHROPIC_API_KEY
  2. Local Ollama    — fluent answers, fully OFFLINE (default: qwen3:4b)
  3. Extractive      — pure-python sentence stitcher, zero dependencies

The plant's 2 AM breakdown case works with no internet: tiers 2 and 3 need
no network at all. Every tier is fed the same real retrieved chunks and the
same strict "answer only from context" instruction, which is the real guard
against hallucination.
"""
import json
import re
import urllib.error
import urllib.request

from ..config import (ANTHROPIC_API_KEY, ANTHROPIC_MODEL, DISABLE_OLLAMA,
                      OLLAMA_CHUNK_CHARS, OLLAMA_CONTEXT_CHUNKS, OLLAMA_HOST,
                      OLLAMA_MODEL, OLLAMA_TIMEOUT)
from .embeddings import tokenize

SYSTEM_PROMPT = """You are IntelliPlant Copilot, an industrial knowledge assistant for plant \
engineers and technicians. Answer ONLY from the provided document context. Be precise and \
factual. Cite the source document name inline like [Source: <document>, p.<page>] after the \
facts they support. If the context does not contain the answer, say so plainly and suggest \
what document to check — do NOT invent equipment, numbers, procedures, or dates. Use short \
paragraphs or numbered steps for procedures. Answer in the same language as the question \
(English or Hindi)."""

_ollama_ok: bool | None = None


# --------------------------------------------------------------------------- #
# Availability checks
# --------------------------------------------------------------------------- #
def llm_available() -> bool:
    if not ANTHROPIC_API_KEY:
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def ollama_available() -> bool:
    """True if the Ollama server is reachable and the configured model is pulled.
    Result is cached after the first check."""
    global _ollama_ok
    if DISABLE_OLLAMA:
        return False
    if _ollama_ok is not None:
        return _ollama_ok
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            tags = json.loads(resp.read().decode())
        names = {m.get("name", "") for m in tags.get("models", [])}
        base = OLLAMA_MODEL.split(":")[0]
        _ollama_ok = any(n == OLLAMA_MODEL or n.split(":")[0] == base for n in names)
    except Exception:
        _ollama_ok = False
    return _ollama_ok


def llm_mode() -> str:
    if llm_available():
        return "claude-api"
    if ollama_available():
        return f"ollama:{OLLAMA_MODEL}"
    return "extractive-fallback"


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def generate_answer(query: str, context_chunks: list[dict], history: list[dict]) -> tuple[str, bool]:
    """Return (answer_markdown, used_llm)."""
    if llm_available():
        try:
            return _claude_answer(query, context_chunks, history), True
        except Exception:
            pass
    if ollama_available():
        try:
            return _ollama_answer(query, context_chunks, history), True
        except Exception:
            pass  # fall through to extractive on any local-LLM error
    return _extractive_answer(query, context_chunks), False


def _build_context(context_chunks: list[dict], max_chunks: int | None = None,
                   max_chars: int | None = None) -> str:
    chunks = context_chunks[:max_chunks] if max_chunks else context_chunks
    parts = []
    for c in chunks:
        text = c["text"]
        if max_chars and len(text) > max_chars:
            text = text[:max_chars] + "…"
        parts.append(f"[Document: {c['document']} | Page {c['page']} | Type: {c['doc_type']}]\n{text}")
    return "\n\n---\n\n".join(parts)


# --------------------------------------------------------------------------- #
# Tier 1 — Claude API
# --------------------------------------------------------------------------- #
def _claude_answer(query: str, context_chunks: list[dict], history: list[dict]) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history[-10:]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    messages.append({
        "role": "user",
        "content": f"DOCUMENT CONTEXT:\n{_build_context(context_chunks)}\n\nQUESTION: {query}",
    })
    resp = client.messages.create(
        model=ANTHROPIC_MODEL, max_tokens=1024, system=SYSTEM_PROMPT, messages=messages,
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


# --------------------------------------------------------------------------- #
# Tier 2 — Local Ollama (offline)
# --------------------------------------------------------------------------- #
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_thinking(text: str) -> str:
    text = _THINK_RE.sub("", text)
    if "</think>" in text:  # unbalanced (thinking not disabled) — keep the tail
        text = text.split("</think>")[-1]
    return text.strip()


def _ollama_answer(query: str, context_chunks: list[dict], history: list[dict]) -> str:
    if not context_chunks:
        raise RuntimeError("no context")  # let extractive handle the empty case
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history[-8:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    # Trim context hard: on a CPU, prompt-processing time scales with context
    # size, so we cap chunks and length. `/no_think` (read from the latest user
    # turn) keeps qwen3 fast by skipping its reasoning phase.
    context = _build_context(context_chunks, max_chunks=OLLAMA_CONTEXT_CHUNKS,
                             max_chars=OLLAMA_CHUNK_CHARS)
    messages.append({
        "role": "user",
        "content": (f"DOCUMENT CONTEXT:\n{context}\n\n"
                    f"QUESTION: {query} /no_think"),
    })
    payload = {
        "model": OLLAMA_MODEL,
        "think": False,
        "stream": False,
        "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 350,
                    "num_ctx": 4096},
        "messages": messages,
    }
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
        data = json.loads(resp.read().decode())
    answer = _strip_thinking(data.get("message", {}).get("content", ""))
    if not answer:
        raise RuntimeError("empty ollama response")
    return answer


# --------------------------------------------------------------------------- #
# Tier 3 — Extractive fallback (pure python)
# --------------------------------------------------------------------------- #
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def _extractive_answer(query: str, context_chunks: list[dict]) -> str:
    if not context_chunks:
        return ("No relevant information found in the indexed documents. "
                "Try uploading related documents or rephrasing the question.")
    qterms = set(tokenize(query))
    scored: list[tuple[float, str, dict]] = []
    for c in context_chunks:
        for sent in _SENT_SPLIT.split(c["text"]):
            sent = sent.strip()
            if len(sent) < 25:
                continue
            sterms = set(tokenize(sent))
            if not sterms:
                continue
            score = len(qterms & sterms) / (len(qterms) or 1) + 0.1 * min(len(sterms) / 20, 1)
            if score > 0.1:
                scored.append((score, sent, c))
    scored.sort(key=lambda t: t[0], reverse=True)
    if not scored:
        top = context_chunks[0]
        return (f"Closest match found in **{top['document']}** (p.{top['page']}):\n\n"
                f"> {top['text'][:500]}")
    lines = []
    for score, sent, c in scored[:6]:
        lines.append(f"- {sent} *[Source: {c['document']}, p.{c['page']}]*")
    return "Based on the indexed documents:\n\n" + "\n".join(lines)
