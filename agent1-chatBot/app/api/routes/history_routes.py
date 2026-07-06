"""
app/api/routes/history_routes.py

WHY THIS FILE EXISTS
---------------------
Implements `GET /history`. WHY this queries `ConversationHistory`
directly rather than calling `ConversationMemoryService.get_recent_history`:
that service method deliberately returns the MINIMAL
`ConversationTurn` shape (`role`, `content`) - exactly what
`PromptBuilderService` needs to replay history into an LLM prompt, and
nothing more (see `app/prompts/schemas.py`'s docstring). This API
response needs MORE: `turn_index` and `created_at`, for a client to
render turns in order with timestamps. Rather than bloating the
internal prompt-building type with API-display-only fields it has no
use for, this route does its own direct, minimal query - the same
"simple read doesn't need a dedicated service" reasoning documented in
`document_routes.py` for `GET /documents`.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ConversationHistory
from app.database.session import get_db_session
from app.schemas.history_schemas import (
    ConversationTurnResponse,
    HistoryQueryParams,
    HistoryResponse,
)

router = APIRouter(tags=["conversation"])


@router.get(
    "/history",
    response_model=HistoryResponse,
    summary="Retrieve conversation history",
    description="Returns the most recent turns for a conversation session, "
    "in chronological order.",
)
def get_history(
    params: HistoryQueryParams = Depends(),
    db: Session = Depends(get_db_session),
) -> HistoryResponse:
    # WHY fetch DESC + reverse in Python: identical rationale to
    # ConversationMemoryService.get_recent_history - selects the MOST
    # RECENT `limit` turns regardless of total conversation length,
    # then reorders them chronologically for display.
    rows = (
        db.execute(
            select(ConversationHistory)
            .where(ConversationHistory.session_id == params.session_id)
            .order_by(ConversationHistory.turn_index.desc())
            .limit(params.limit)
        )
        .scalars()
        .all()
    )
    chronological = list(reversed(rows))

    return HistoryResponse(
        session_id=params.session_id,
        turns=[ConversationTurnResponse.model_validate(row) for row in chronological],
    )
