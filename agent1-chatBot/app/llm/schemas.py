"""
app/llm/schemas.py

WHY THIS FILE EXISTS
---------------------
`LLMResponse` is the normalized, provider-agnostic shape every caller
of `GroqLLMService` works with - never Groq's raw SDK response object
directly. WHY that matters: `citations/` and `confidence/` (upcoming
folders) and the eventual query-orchestrating service need the
answer text and token usage, but should never need to know they're
talking to Groq specifically vs. any other OpenAI-compatible chat
completion API. If the LLM provider ever changed, only
`GroqLLMService`'s internals would need to change - every consumer of
`LLMResponse` stays untouched.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResponse:
    """
    Normalized result of one Groq chat completion call.

    Attributes:
        content: The generated text.
        model: The actual model name Groq used to serve this response
            (echoed back by the API - useful for logging/auditing
            exactly which model produced a given answer).
        prompt_tokens: Tokens consumed by the input messages.
        completion_tokens: Tokens generated in the response.
        total_tokens: `prompt_tokens + completion_tokens`, kept as its
            own field (rather than always summed by callers) because
            it's exactly what `query_logs` analytics and cost
            monitoring want to read directly.
        finish_reason: Why generation stopped (`"stop"`, `"length"`,
            etc.) - `"length"` in particular is worth surfacing to
            callers, since it means the answer may have been cut off
            mid-thought by `GROQ_MAX_TOKENS`.
        latency_ms: Wall-clock time the API call took, measured by
            `GroqLLMService` itself (not derived from Groq's own
            `usage.completion_time`, which measures only server-side
            generation time, not round-trip latency including network).
    """

    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finish_reason: str
    latency_ms: float
