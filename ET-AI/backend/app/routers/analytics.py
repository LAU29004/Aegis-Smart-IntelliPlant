from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents import compliance as compliance_agent
from ..agents import maintenance
from ..database import Alert, Document, Equipment, QueryLog, User, get_db
from ..envelope import ok

from ..services.embeddings import tokenize
from ..security import require_roles
router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/knowledge-gaps")
def knowledge_gaps(
    user: User = Depends(
        require_roles(
            "Admin",
            "Plant Manager",
            "Safety Officer",
        )
    ),
    db: Session = Depends(get_db),
):
    logs = db.scalars(select(QueryLog)).all()
    low = [l for l in logs if l.confidence < 60]
    counts: Counter[str] = Counter()
    conf: dict[str, list[float]] = {}
    for l in low:
        key = l.query.strip().lower()
        counts[key] += 1
        conf.setdefault(key, []).append(l.confidence)
    out = [{
        "query": q,
        "frequency": n,
        "avg_confidence": round(sum(conf[q]) / len(conf[q])),
        "suggested_document": "Upload documents covering this topic to close the gap",
    } for q, n in counts.most_common(15)]
    return ok({"unanswered_queries": out})


@router.get("/overview")
def overview(
    user: User = Depends(
        require_roles(
            "Admin",
            "Plant Manager",
            "Safety Officer",
        )
    ),
    db: Session = Depends(get_db),
):
    docs = db.scalars(select(Document)).all()
    logs = db.scalars(select(QueryLog)).all()
    alerts = db.scalars(select(Alert).where(Alert.status == "open")).all()
    equipment = db.scalars(select(Equipment)).all()

    week_ago = date.today() - timedelta(days=7)
    recent = [l for l in logs if l.created_at.date() >= week_ago]
    avg_conf = round(sum(l.confidence for l in logs) / len(logs)) if logs else 0

    healthy = 0
    for eq in equipment:
        if maintenance.status_for_score(maintenance.health_score(db, eq.equipment_id)) == "healthy":
            healthy += 1
    healthy_pct = round(healthy / len(equipment) * 100) if equipment else 0

    volume = []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        volume.append({"date": d.isoformat(),
                       "count": len([l for l in logs if l.created_at.date() == d])})

    words: Counter[str] = Counter()
    for l in logs:
        words.update(t for t in tokenize(l.query) if len(t) > 3)
    top_topics = [{"topic": w, "count": n} for w, n in words.most_common(8)]

    return ok({
        "kpis": {
            "documents_indexed": len([d for d in docs if d.processing_status == "indexed"]),
            "queries_this_week": len(recent),
            "avg_confidence": avg_conf,
            "open_alerts": len(alerts),
            "compliance_score": compliance_agent.build_matrix(db)["overall_score"],
            "equipment_healthy_pct": healthy_pct,
        },
        "query_volume": volume,
        "top_topics": top_topics,
    })
