"""
app/schemas/history_schemas.py

WHY THIS FILE EXISTS
---------------------
Defines the request/response models for `GET /history`. WHY this is
NOT the same shape as `ConversationTurn` (`app/prompts/schemas.py`):
that internal type is deliberately minimal (just `role`/`content`) -
exactly what `PromptBuilderService` needs to replay history into an
LLM message list. The API response needs more: `turn_index` (so a
client can render turns in order and detect gaps) and `created_at`
(so a client can show timestamps) - fields the prompt-building path
has no use for and shouldn't be forced to carry around.
"""

from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from app.database.enums import ConversationRole


class HistoryQueryParams(BaseModel):
    """Query parameters for `GET /history`."""

    session_id: str = Field(..., min_length=1, max_length=100)
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of turns to return, most recent first "
        "before being reordered chronologically in the response.",
    )


class ConversationTurnResponse(BaseModel):
    """One turn in a conversation's history."""

    model_config = ConfigDict(from_attributes=True)

    role: ConversationRole
    message: str
    turn_index: int
    created_at: datetime


class HistoryResponse(BaseModel):
    """Response body for `GET /history`."""

    session_id: str
    turns: List[ConversationTurnResponse] = Field(default_factory=list)
