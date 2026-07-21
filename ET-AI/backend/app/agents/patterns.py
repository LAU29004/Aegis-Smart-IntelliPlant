"""Failure Pattern & Lessons Learned Agent — incident clustering, precursor
warnings, similar-incident search."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import Incident, LessonCard
from ..services.rag import find_similar_texts
from .maintenance import detect_patterns


def similar_incidents(db: Session, text: str, exclude_id: str | None = None,
                      top_n: int = 3) -> list[dict]:
    incidents = db.scalars(select(Incident)).all()
    candidates = [{
        "incident_id": i.incident_id, "title": i.title, "date": i.date,
        "outcome": i.outcome, "resolution": i.resolution,
        "_text": f"{i.title}. {i.description}",
    } for i in incidents if i.incident_id != exclude_id]
    ranked = find_similar_texts(text, candidates, "_text", top_n=top_n)
    return [{k: r[k] for k in (
        "incident_id", "title", "similarity_score", "outcome", "resolution")} for r in ranked]


def incident_clusters(db: Session) -> dict[str, list[Incident]]:
    """Group incidents by shared keywords (production path: embedding clustering)."""
    incidents = db.scalars(select(Incident)).all()
    clusters: dict[str, list[Incident]] = {}
    keywords = ["fouling", "seal", "bearing", "leak", "trip", "overheat", "vibration"]
    for inc in incidents:
        text = f"{inc.title} {inc.description}".lower()
        for kw in keywords:
            if kw in text:
                clusters.setdefault(kw, []).append(inc)
                break
    return clusters


def get_warnings(db: Session) -> list[dict]:
    """Proactive warnings: current conditions matching historical failure precursors.

    Two sources: (1) incident clusters with known precursor conditions —
    the prototype simulates today's plant conditions; (2) high-risk recurring
    failure patterns from the Maintenance Agent.
    """
    warnings = []

    clusters = incident_clusters(db)
    fouling = clusters.get("fouling", [])
    if len(fouling) >= 2:
        years = ", ".join(sorted(i.date[:7] for i in fouling))
        ref = max(fouling, key=lambda i: i.date)
        warnings.append({
            "warning_id": "warn_he_fouling",
            "title": "Line 3 conditions match heat exchanger fouling precursor pattern "
                     f"({len(fouling)} past occurrences: {years})",
            "matching_factors": [
                "Ambient temperature above 38°C for 5+ consecutive days",
                "Cooling water flow rate below 85% of design value",
            ],
            "past_outcome": "HE fouling leading to 18–24 hours unplanned downtime "
                            "in all prior incidents.",
            "recommended_action": "Inspect HE-01 cooling water inlet strainer.",
            "urgency": "high",
            "reference": f"Incident Report {ref.incident_id}",
        })

    for p in detect_patterns(db):
        if p["risk_level"] == "high":
            warnings.append({
                "warning_id": f"warn_{p['pattern_id']}",
                "title": p["title"],
                "matching_factors": [p["description"]],
                "past_outcome": f"Evidence: {', '.join(p['evidence'])}",
                "recommended_action": p["recommended_action"],
                "urgency": "high",
                "reference": p["evidence"][-1] if p["evidence"] else "",
            })
    return warnings


def lessons(db: Session, keyword: str | None = None) -> list[dict]:
    cards = db.scalars(select(LessonCard)).all()
    if keyword:
        kw = keyword.lower()
        cards = [c for c in cards if kw in
                 f"{c.title} {c.what_happened} {c.root_cause}".lower()]
    return [{
        "card_id": c.card_id, "title": c.title, "equipment_type": c.equipment_type,
        "what_happened": c.what_happened, "root_cause": c.root_cause,
        "what_was_done": c.what_was_done, "watch_for": c.watch_for,
    } for c in cards]
