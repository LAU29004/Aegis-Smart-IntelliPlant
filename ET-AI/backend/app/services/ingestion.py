"""Ingestion pipeline: parse → chunk → extract entities → embed → index.

Runs as a FastAPI background task (production path: Redis + Celery queue).
"""
import traceback
import uuid
from pathlib import Path

from ..database import Document, IngestJob, SessionLocal
from .chunking import chunk_pages
from .entities import extract_entities
from .parsing import parse_file
from .vectorstore import get_store


def ingest_file(path: str | Path, doc_type: str = "other", equipment_id: str = "",
                department: str = "", db=None, display_name: str = "") -> str:
    """Synchronously ingest one file. Returns doc_id."""
    own_session = db is None
    db = db or SessionLocal()
    path = Path(path)
    name = display_name or path.name
    doc_id = f"doc_{uuid.uuid4().hex[:10]}"
    try:
        pages = parse_file(path)
        full_text = "\n".join(t for _, t in pages)
        entities = extract_entities(full_text)
        tags = list(dict.fromkeys(
            ([equipment_id.upper()] if equipment_id else []) + entities.get("equipment_ids", [])
        ))[:10]
        chunks = chunk_pages(pages)
        get_store().add_chunks(doc_id, name, doc_type, department, chunks)
        db.add(Document(
            doc_id=doc_id, name=name, doc_type=doc_type, equipment_tags=tags,
            department=department, file_path=str(path), chunk_count=len(chunks),
            processing_status="indexed", entities=entities,
        ))
        db.commit()
        return doc_id
    except Exception:
        db.add(Document(
            doc_id=doc_id, name=name, doc_type=doc_type, equipment_tags=[],
            department=department, file_path=str(path), chunk_count=0,
            processing_status="failed", entities={},
        ))
        db.commit()
        raise
    finally:
        if own_session:
            db.close()


def run_ingest_job(job_id: str, files: list[tuple[str, str]], doc_type: str,
                   equipment_id: str, department: str) -> None:
    """Background-task entry point: process every (saved_path, original_name)
    pair in the job, tracking progress."""
    db = SessionLocal()
    try:
        job = db.get(IngestJob, job_id)
        if job is None:
            return
        job.status = "processing"
        db.commit()
        doc_ids, errors = [], []
        for i, (fp, orig_name) in enumerate(files):
            try:
                doc_ids.append(ingest_file(fp, doc_type, equipment_id, department,
                                           db=db, display_name=orig_name))
            except Exception as e:
                errors.append(f"{orig_name}: {e}")
                traceback.print_exc()
            job.progress = int((i + 1) / len(files) * 100)
            job.doc_ids = list(doc_ids)
            db.commit()
        job.status = "failed" if errors and not doc_ids else "completed"
        job.error_message = "; ".join(errors)
        job.progress = 100
        db.commit()
    finally:
        db.close()
