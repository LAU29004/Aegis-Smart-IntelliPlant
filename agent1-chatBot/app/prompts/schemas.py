"""
app/prompts/schemas.py

WHY THIS FILE EXISTS
---------------------
`SourceReference` and `ContextBlock` are the hand-off between
`ContextBuilderService` and `PromptBuilderService` (and, downstream,
`CitationBuilderService` in the upcoming `citations/` folder).
`ConversationTurn` is the minimal shape `PromptBuilderService` needs
to replay prior conversation turns into a Groq chat message list.

WHY `ConversationTurn.role` is a plain `str` rather than importing
`app.database.enums.ConversationRole`: `prompts/` must not depend on
`database/` - they are peer, independent leaf packages in this
codebase's dependency graph (both depend on `core/` and `config/`,
neither depends on the other). The upcoming `services/` composition
layer is responsible for converting a `ConversationHistory` ORM row's
`ConversationRole` enum into the plain `"user"`/`"assistant"` string
this module expects - that conversion is a persistence-to-prompt
translation concern, not something `prompts/` should need to know
about a SQLAlchemy enum to do its job.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class SourceReference:
    """
    One numbered citation source backing the LLM's context - the
    AUTHORITATIVE mapping between a bracketed reference number (e.g.
    `[1]`) the LLM is instructed to cite and the actual chunk it came
    from.

    WHY this exact same numbering is later reused by
    `CitationBuilderService` (upcoming `citations/` folder) rather
    than each stage inventing its own numbering: the LLM only ever
    sees the numbers assigned HERE (baked into the context text it's
    given) - if citation building used a DIFFERENT numbering scheme
    when parsing the LLM's answer back, `[1]` in the answer could be
    misattributed to the wrong source. This dataclass is the single
    source of truth for "what does [n] mean" for a given query.
    """

    index: int
    chunk_id: str
    document_name: str
    page_number: Optional[int]
    department: Optional[str]
    equipment_id: Optional[str]
    relevance_score: float


@dataclass(frozen=True)
class ContextBlock:
    """
    The fully assembled, LLM-ready context text plus the authoritative
    source list it was built from.

    Attributes:
        context_text: Numbered, formatted source excerpts, ready to be
            embedded directly into the user-facing prompt content.
        sources: Ordered list of `SourceReference`, index-aligned with
            the `[n]` markers inside `context_text`.
        truncated: True if one or more lower-relevance chunks were
            dropped to stay within the context budget - surfaced so
            callers can log/flag when retrieval found more than could
            actually be used.
    """

    context_text: str
    sources: List[SourceReference] = field(default_factory=list)
    truncated: bool = False


@dataclass(frozen=True)
class ConversationTurn:
    """
    One prior turn to replay into the LLM's message list ahead of the
    current question, for multi-turn conversational context.

    Attributes:
        role: Either `"user"` or `"assistant"` - deliberately a plain
            string (see module docstring) matching Groq's chat message
            role values directly, requiring no translation at the
            call site in `PromptBuilderService`.
        content: The turn's message text.
    """

    role: str
    content: str
