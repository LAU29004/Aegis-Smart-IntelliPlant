from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents import maintenance, patterns
from ..database import Alert, User, get_db
from ..envelope import ok

from ..security import get_current_user, require_roles
from pydantic import BaseModel
import uuid
from datetime import datetime, timezone

from ..services import alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])

_SEV_ORDER = {"critical": 0, "warning": 1, "info": 2}

class CreateAlertBody(BaseModel):
    equipment_id: str
    severity: str
    title: str
    description: str
    recommended_action: str = ""

    
class AckBody(BaseModel):
    notes: str = ""


def _alert_dict(a: Alert) -> dict:
    return {
        "alert_id": a.alert_id, "equipment_id": a.equipment_id, "severity": a.severity,
        "title": a.title, "description": a.description,
        "triggered_at": a.triggered_at.isoformat(), "status": a.status,
        "recommended_action": a.recommended_action,
    }


@router.get("")
def list_alerts(severity: str | None = None, status: str | None = None,
                equipment_id: str | None = None,
               user: User = Depends(
    require_roles(
        "Admin",
        "Plant Manager",
        "Engineer",
        "Safety Officer",
    )
), db: Session = Depends(get_db)):
    items = db.scalars(select(Alert)).all()
    if severity:
        items = [a for a in items if a.severity == severity]
    if status:
        items = [a for a in items if a.status == status]
    if equipment_id:
        items = [a for a in items if a.equipment_id == equipment_id.upper()]
    items.sort(key=lambda a: (_SEV_ORDER.get(a.severity, 3), a.triggered_at))
    return ok({"alerts": [_alert_dict(a) for a in items]})


@router.get("/patterns")
def failure_patterns(user: User = Depends(
    require_roles(
        "Admin",
        "Plant Manager",
        "Engineer",
    )
), db: Session = Depends(get_db)):
    return ok({"patterns": maintenance.detect_patterns(db)})


@router.get("/warnings")
def warnings(user: User = Depends(
    require_roles(
        "Admin",
        "Plant Manager",
        "Engineer",
        "Safety Officer",
    )
), db: Session = Depends(get_db)):
    return ok({"warnings": patterns.get_warnings(db)})


@router.get("/{alert_id}")
def get_alert(alert_id: str, user: User = Depends(
    require_roles(
        "Admin",
        "Plant Manager",
        "Engineer",
        "Safety Officer",
    )
),
              db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    similar = patterns.similar_incidents(db, f"{a.title}. {a.description}")
    return ok({**_alert_dict(a),
               "ai_explanation": a.ai_explanation or a.description,
               "similar_past_incidents": [{
                   "incident_id": s["incident_id"], "title": s["title"],
                   "date": "", "outcome": s["outcome"],
               } for s in similar]})


@router.post("/{alert_id}/acknowledge")
def acknowledge(alert_id: str, body: AckBody,
                user: User = Depends(
    require_roles(
        "Admin",
        "Plant Manager",
        "Engineer",
    )
), db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    a.status = "acknowledged"
    a.acknowledged_at = datetime.now(timezone.utc)
    a.acknowledged_by = user.name
    a.notes = body.notes
    db.commit()
    return ok({"alert_id": a.alert_id, "status": a.status,
               "acknowledged_at": a.acknowledged_at.isoformat()})


@router.post("")
def create_alert(
    body: CreateAlertBody,
    user: User = Depends(require_roles("Admin","Plant Manager","Engineer",)),
    db: Session = Depends(get_db),
):
    alert = alert_service.create_alert(
        db=db,
        equipment_id=body.equipment_id,
        severity=body.severity,
        title=body.title,
        description=body.description,
        recommended_action=body.recommended_action,
    )

    return ok({
        "alert_id": alert.alert_id,
        "status": "created" if getattr(alert, "is_new", False) else "duplicate_suppressed",
        "notification_sent": getattr(alert, "notification_sent", False),
    })