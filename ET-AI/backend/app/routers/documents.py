from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import Document, User, get_db
from ..envelope import ok
from ..security import get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])


def _doc_dict(d: Document) -> dict:
    return {
        "doc_id": d.doc_id, "name": d.name, "doc_type": d.doc_type,
        "equipment_tags": d.equipment_tags or [], "department": d.department,
        "uploaded_at": d.uploaded_at.isoformat(), "chunk_count": d.chunk_count,
        "processing_status": d.processing_status,
    }


@router.get("")
def list_documents(doc_type: str | None = None, equipment_id: str | None = None,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = db.scalars(select(Document)).all()
    if doc_type:
        docs = [d for d in docs if d.doc_type == doc_type]
    if equipment_id:
        eq = equipment_id.upper()
        docs = [d for d in docs if eq in (d.equipment_tags or [])]
    docs.sort(key=lambda d: d.uploaded_at, reverse=True)
    return ok({"documents": [_doc_dict(d) for d in docs]})


@router.get("/search")
def search(q: str = "", user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    term = q.lower().strip()
    docs = db.scalars(select(Document)).all()
    matches = [d for d in docs if term in d.name.lower()
               or term in (d.doc_type or "").lower()
               or any(term in t.lower() for t in (d.equipment_tags or []))]
    return ok({"documents": [_doc_dict(d) for d in matches]})


@router.get("/{doc_id}")
def get_document(doc_id: str, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    d = db.get(Document, doc_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return ok({**_doc_dict(d), "entities": d.entities or {}})


@router.get("/{doc_id}/download")
def download(doc_id: str, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    d = db.get(Document, doc_id)
    if d is None or not Path(d.file_path).exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(d.file_path, filename=d.name)
