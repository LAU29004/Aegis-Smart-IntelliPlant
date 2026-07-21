from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents.orchestrator import handle_query
from ..database import QueryLog, User, get_db
from ..envelope import ok
from ..security import get_current_user

router = APIRouter(prefix="/query", tags=["query"])


class AskBody(BaseModel):
    query: str
    conversation_history: list[dict] = Field(default_factory=list)
    filters: dict = Field(default_factory=dict)


class FeedbackBody(BaseModel):
    query_id: str
    rating: int
    comment: str = ""


@router.post("/ask")
def ask(body: AskBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = body.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Empty query")
    filters = {k: v for k, v in (body.filters or {}).items()
               if k in ("equipment_id", "doc_type") and v}
    result = handle_query(db, q, history=body.conversation_history, filters=filters)
    db.add(QueryLog(
        query_id=result["query_id"], user_id=user.user_id, query=q,
        answer=result["answer"], confidence=result["confidence"],
    ))
    db.commit()
    return ok(result)


@router.get("/history")
def history(limit: int = 20, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    logs = db.scalars(select(QueryLog).where(QueryLog.user_id == user.user_id)).all()
    logs.sort(key=lambda l: l.created_at, reverse=True)
    return ok({"queries": [{
        "query_id": l.query_id, "query": l.query, "answer": l.answer,
        "confidence": l.confidence, "created_at": l.created_at.isoformat(),
    } for l in logs[:limit]]})


@router.post("/feedback")
def feedback(body: FeedbackBody, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    log = db.get(QueryLog, body.query_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Query not found")
    log.rating = 1 if body.rating >= 1 else -1
    log.comment = body.comment
    db.commit()
    return ok({"ok": True})
