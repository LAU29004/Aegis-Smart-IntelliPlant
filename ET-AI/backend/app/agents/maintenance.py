"""Maintenance Intelligence Agent — equipment health, failure patterns, RCA."""
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import Alert, Equipment, MaintenanceEvent
from ..services.rag import find_similar_texts
from ..services.vectorstore import get_store

FAILURE_CATEGORIES = {
    "bearing": ["bearing"],
    "mechanical seal": ["seal"],
    "fouling": ["fouling", "foul"],
    "vibration": ["vibration", "vibrat"],
    "leak": ["leak", "leakage"],
    "electrical": ["motor", "winding", "electrical", "trip"],
    "corrosion": ["corrosion", "corroded", "rust"],
}


def _parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def health_score(db: Session, equipment_id: str, today: date | None = None) -> int:
    """0–100: penalise overdue service, recent failures, open alerts."""
    today = today or date.today()
    score = 100.0
    eq = db.get(Equipment, equipment_id)
    if eq and eq.last_serviced:
        d = _parse_date(eq.last_serviced)
        if d:
            days = (today - d).days
            score -= min(25, max(0, (days - 90) / 10))  # penalty after 90 days
    failures = db.scalars(select(MaintenanceEvent).where(
        MaintenanceEvent.equipment_id == equipment_id,
        MaintenanceEvent.event_type == "failure")).all()
    recent = [f for f in failures if (d := _parse_date(f.date)) and (today - d).days <= 365]
    score -= min(35, 12 * len(recent))
    open_alerts = db.scalars(select(Alert).where(
        Alert.equipment_id == equipment_id, Alert.status == "open")).all()
    for a in open_alerts:
        score -= {"critical": 25, "warning": 10, "info": 3}.get(a.severity, 5)
    return max(5, min(100, round(score)))


def status_for_score(score: int) -> str:
    return "healthy" if score >= 75 else "warning" if score >= 55 else "critical"


def timeline(db: Session, equipment_id: str) -> list[dict]:
    events = db.scalars(select(MaintenanceEvent).where(
        MaintenanceEvent.equipment_id == equipment_id)).all()
    events.sort(key=lambda e: e.date, reverse=True)
    return [{
        "event_id": e.event_id, "date": e.date, "event_type": e.event_type,
        "title": e.title, "description": e.description,
        "work_order": e.work_order, "document": e.document,
    } for e in events]


def _interval_phrase(intervals: list[int]) -> str:
    lo, hi = round(min(intervals) / 30), round(max(intervals) / 30)
    return f"{lo} months" if lo == hi else f"{lo} to {hi} months"


def detect_patterns(db: Session, equipment_id: str | None = None,
                    today: date | None = None) -> list[dict]:
    """Recurring failure detection: cluster failures by category, analyse intervals."""
    today = today or date.today()
    q = select(MaintenanceEvent).where(MaintenanceEvent.event_type == "failure")
    if equipment_id:
        q = q.where(MaintenanceEvent.equipment_id == equipment_id)
    failures = db.scalars(q).all()

    grouped: dict[tuple[str, str], list[MaintenanceEvent]] = {}
    for f in failures:
        text = f"{f.title} {f.description}".lower()
        for cat, keywords in FAILURE_CATEGORIES.items():
            if any(k in text for k in keywords):
                grouped.setdefault((f.equipment_id, cat), []).append(f)
                break

    patterns = []
    for (eq_id, cat), evs in grouped.items():
        if len(evs) < 2:
            continue
        dates = sorted(d for e in evs if (d := _parse_date(e.date)))
        if len(dates) < 2:
            continue
        intervals = [(b - a).days for a, b in zip(dates, dates[1:])]
        avg = sum(intervals) / len(intervals)
        since_last = (today - dates[-1]).days
        due_ratio = since_last / avg if avg else 0
        risk = "high" if due_ratio >= 0.8 else "medium" if due_ratio >= 0.5 else "low"
        span_months = max(1, round((dates[-1] - dates[0]).days / 30) + 1)
        patterns.append({
            "pattern_id": f"pat_{eq_id}_{cat.replace(' ', '_')}",
            "equipment_id": eq_id,
            "title": f"Recurring {cat} failures on {eq_id}",
            "description": (
                f"{cat.capitalize()} failures occurring roughly every "
                f"{_interval_phrase(intervals)}. "
                f"{len(evs)} occurrences in {span_months} months. "
                f"Last failure: {dates[-1].strftime('%b %Y')}. "
                f"Current interval: {round(since_last/30)} months."
            ),
            "frequency": f"{len(evs)} occurrences / avg every {round(avg/30)} months",
            "risk_level": risk,
            "evidence": [f"{e.work_order or e.event_id} ({(_parse_date(e.date) or today).strftime('%b %Y')})" for e in evs],
            "recommended_action": (
                f"Schedule {cat} inspection within 30 days. "
                f"Reference the OEM manual maintenance-interval section."
                if risk == "high" else
                f"Monitor {cat} condition indicators; include in next planned maintenance."
            ),
        })
    order = {"high": 0, "medium": 1, "low": 2}
    patterns.sort(key=lambda p: order[p["risk_level"]])
    return patterns


def rca(db: Session, equipment_id: str, symptom: str) -> dict:
    """Root-cause analysis: similar past failures + document evidence, ranked."""
    events = db.scalars(select(MaintenanceEvent).where(
        MaintenanceEvent.equipment_id == equipment_id,
        MaintenanceEvent.event_type.in_(["failure", "repair"]))).all()
    candidates = [{
        "title": e.title, "description": e.description, "date": e.date,
        "work_order": e.work_order, "_text": f"{e.title}. {e.description}",
    } for e in events]
    similar = find_similar_texts(symptom, candidates, "_text", top_n=4)

    chunks = get_store().search(f"{equipment_id} {symptom}", top_k=4,
                                filters={"equipment_id": equipment_id})
    if not chunks:
        chunks = get_store().search(symptom, top_k=4)

    causes = []
    for s in similar:
        causes.append({
            "cause": s["title"],
            "likelihood": "high" if s["similarity_score"] > 0.25 else
                          "medium" if s["similarity_score"] > 0.12 else "low",
            "evidence": f"Similar past event on {s['date']}"
                        + (f" ({s['work_order']})" if s.get("work_order") else "")
                        + f": {s['description'][:180]}",
            "recommended_action": "Review the referenced work order and verify the same "
                                  "failure mechanism before repeating the corrective action.",
        })
    if not causes and chunks:
        causes.append({
            "cause": "See referenced documentation",
            "likelihood": "medium",
            "evidence": chunks[0]["text"][:200],
            "recommended_action": f"Consult {chunks[0]['document']} (p.{chunks[0]['page']}).",
        })

    return {
        "symptom": symptom,
        "probable_causes": causes,
        "sources": [{
            "doc_id": c["doc_id"], "document": c["document"], "page": c["page"],
            "chunk_id": c["chunk_id"], "snippet": c["text"][:200],
        } for c in chunks],
    }
