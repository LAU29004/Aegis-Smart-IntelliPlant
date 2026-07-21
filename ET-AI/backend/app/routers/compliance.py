import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..agents import compliance as agent
from ..database import User, get_db
from ..envelope import ok
from ..security import require_roles

router = APIRouter(prefix="/compliance", tags=["compliance"])


class ScanBody(BaseModel):
    department: str | None = None


@router.get("/matrix")
def matrix(user: User = Depends(
    require_roles(
        "Admin",
        "Plant Manager",
        "Safety Officer",
    )
), db: Session = Depends(get_db)):
    return ok(agent.build_matrix(db))


@router.get("/gaps")
def gaps(department: str | None = None, severity: str | None = None,
         user: User = Depends(
    require_roles(
        "Admin",
        "Plant Manager",
        "Safety Officer",
    )
), db: Session = Depends(get_db)):
    return ok({"gaps": agent.list_gaps(db, department, severity)})


@router.post("/scan")
def scan(body: ScanBody, user: User = Depends(
    require_roles(
        "Admin",
        "Plant Manager",
        "Safety Officer",
    )
),
         db: Session = Depends(get_db)):
    # Scan runs synchronously (fast at demo scale) but reports like a queued job.
    found = agent.run_scan(db, body.department)
    return ok({"scan_job_id": f"scan_{uuid.uuid4().hex[:8]}", "status": "completed",
               "gaps_found": found})


@router.get("/expiring")
def expiring(days: int = 60,user: User = Depends(
    require_roles(
        "Admin",
        "Plant Manager",
        "Safety Officer",
    )
),
             db: Session = Depends(get_db)):
    return ok({"certifications": agent.expiring_certifications(db, days)})
