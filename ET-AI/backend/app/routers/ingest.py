import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..database import Document, IngestJob, User, get_db
from ..envelope import ok
from ..security import get_current_user
from ..services.ingestion import run_ingest_job
from ..services.vectorstore import get_store

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/upload")
async def upload(
    background: BackgroundTasks,
    files: list[UploadFile],
    doc_type: str = Form("other"),
    equipment_id: str = Form(""),
    department: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    job_id = f"job_{uuid.uuid4().hex[:10]}"
    saved, names = [], []
    for f in files:
        safe_name = f"{job_id}_{f.filename}"
        dest = UPLOAD_DIR / safe_name
        dest.write_bytes(await f.read())
        saved.append((str(dest), f.filename))
        names.append(f.filename)
    db.add(IngestJob(job_id=job_id, status="queued", file_names=names))
    db.commit()
    background.add_task(run_ingest_job, job_id, saved, doc_type, equipment_id, department)
    return ok({"job_id": job_id, "status": "queued", "files": names})


@router.get("/status/{job_id}")
def status(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.get(IngestJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return ok({
        "job_id": job.job_id, "status": job.status, "progress": job.progress,
        "error_message": job.error_message or None, "doc_ids": job.doc_ids,
    })


@router.get("/jobs")
def jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    all_jobs = db.scalars(select(IngestJob)).all()
    all_jobs.sort(key=lambda j: j.created_at, reverse=True)
    return ok({"jobs": [{
        "job_id": j.job_id, "status": j.status, "progress": j.progress,
        "file_names": j.file_names, "created_at": j.created_at.isoformat(),
    } for j in all_jobs]})


@router.delete("/{doc_id}")
def remove(doc_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    deleted = get_store().delete_doc(doc_id)
    db.delete(doc)
    db.commit()
    return ok({"doc_id": doc_id, "chunks_deleted": deleted})
