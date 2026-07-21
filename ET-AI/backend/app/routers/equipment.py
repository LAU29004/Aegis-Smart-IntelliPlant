from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents import maintenance
from ..database import Alert, Document, Equipment, User, get_db
from ..envelope import ok
from ..security import get_current_user

router = APIRouter(prefix="/equipment", tags=["equipment"])


def _summary(db: Session, eq: Equipment) -> dict:
    score = maintenance.health_score(db, eq.equipment_id)
    open_alerts = db.scalars(select(Alert).where(
        Alert.equipment_id == eq.equipment_id, Alert.status == "open")).all()
    return {
        "equipment_id": eq.equipment_id, "name": eq.name, "type": eq.type,
        "location": eq.location, "department": eq.department,
        "health_score": score, "status": maintenance.status_for_score(score),
        "last_serviced": eq.last_serviced, "next_due": eq.next_due,
        "open_alerts_count": len(open_alerts),
    }


def _alert_dict(a: Alert) -> dict:
    return {
        "alert_id": a.alert_id, "equipment_id": a.equipment_id, "severity": a.severity,
        "title": a.title, "description": a.description,
        "triggered_at": a.triggered_at.isoformat(), "status": a.status,
        "recommended_action": a.recommended_action,
    }


@router.get("")
def list_equipment(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    equipment = db.scalars(select(Equipment)).all()
    return ok({"equipment": [_summary(db, eq) for eq in equipment]})


@router.get("/{equipment_id}")
def get_equipment(equipment_id: str, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    eq = db.get(Equipment, equipment_id.upper())
    if eq is None:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return ok({**_summary(db, eq), "manufacturer": eq.manufacturer, "model": eq.model,
               "installed_on": eq.installed_on, "description": eq.description})


@router.get("/{equipment_id}/history")
def history(equipment_id: str, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    return ok({"events": maintenance.timeline(db, equipment_id.upper())})


@router.get("/{equipment_id}/alerts")
def alerts(equipment_id: str, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    items = db.scalars(select(Alert).where(
        Alert.equipment_id == equipment_id.upper())).all()
    items.sort(key=lambda a: a.triggered_at, reverse=True)
    return ok({"alerts": [_alert_dict(a) for a in items]})


@router.get("/{equipment_id}/documents")
def documents(equipment_id: str, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    eq_id = equipment_id.upper()
    docs = [d for d in db.scalars(select(Document)).all() if eq_id in (d.equipment_tags or [])]
    return ok({"documents": [{
        "doc_id": d.doc_id, "name": d.name, "doc_type": d.doc_type,
        "uploaded_at": d.uploaded_at.isoformat(),
    } for d in docs]})


@router.get("/{equipment_id}/rca")
def rca(equipment_id: str, symptom: str = "", user: User = Depends(get_current_user),
        db: Session = Depends(get_db)):
    if not symptom.strip():
        raise HTTPException(status_code=400, detail="symptom query parameter required")
    return ok(maintenance.rca(db, equipment_id.upper(), symptom))
