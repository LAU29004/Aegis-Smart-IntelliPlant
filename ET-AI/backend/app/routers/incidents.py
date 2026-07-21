import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents import patterns
from ..database import Incident, User, get_db
from ..envelope import ok
from ..security import get_current_user

router = APIRouter(tags=["incidents"])


class ReportBody(BaseModel):
    equipment_id: str
    description: str
    severity: str = "medium"
    incident_type: str = "incident"


@router.post("/incidents/report")
def report(body: ReportBody, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    incident_id = f"INC-{date.today().year}-{uuid.uuid4().hex[:4].upper()}"
    title = body.description.strip().splitlines()[0][:80] or "Reported issue"
    db.add(Incident(
        incident_id=incident_id, equipment_id=body.equipment_id.upper(),
        title=title, description=body.description, severity=body.severity,
        incident_type=body.incident_type, date=date.today().isoformat(),
        status="reported",
    ))
    db.commit()
    return ok({"incident_id": incident_id, "status": "reported"})


@router.get("/incidents")
def list_incidents(incident_type: str | None = None, severity: str | None = None,
                   equipment_id: str | None = None,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Incident)).all()
    if incident_type:
        items = [i for i in items if i.incident_type == incident_type]
    if severity:
        items = [i for i in items if i.severity == severity]
    if equipment_id:
        items = [i for i in items if i.equipment_id == equipment_id.upper()]
    items.sort(key=lambda i: i.date, reverse=True)
    return ok({"incidents": [{
        "incident_id": i.incident_id, "equipment_id": i.equipment_id, "title": i.title,
        "description": i.description, "severity": i.severity,
        "incident_type": i.incident_type, "date": i.date, "status": i.status,
    } for i in items]})


@router.get("/incidents/{incident_id}/similar")
def similar(incident_id: str, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    inc = db.get(Incident, incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return ok({"similar_incidents": patterns.similar_incidents(
        db, f"{inc.title}. {inc.description}", exclude_id=incident_id)})


@router.get("/lessons-learned")
def lessons_learned(keyword: str | None = None,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok({"cards": patterns.lessons(db, keyword)})
