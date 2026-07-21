"""
Orchestrates the existing Maintenance Agent + alert_service.

maintenance.py remains pure: health_score(), status_for_score(), and
detect_patterns() only perform analysis. They never touch Firebase,
never insert or commit rows, and never construct an Alert. This module
is the only layer that looks at their output and decides whether an
Alert should be raised, and it always does so through
alert_service.create_alert() — never with direct SQL.

This module has no FastAPI dependency, so run_maintenance_check_for_all_equipment(db)
can be called identically by APScheduler, Celery, cron, or FastAPI
BackgroundTasks with no code changes. It must never be called from a
GET route.
"""

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents import maintenance
from ..config import PATTERN_ALERT_SEVERITY
from ..database import Equipment
from . import alert_service


def _tally(stats: Dict[str, Any], alert) -> None:
    if getattr(alert, "is_new", False):
        stats["alerts_created"] += 1
    else:
        stats["alerts_deduplicated"] += 1


def run_maintenance_check(db: Session, equipment_id: str) -> Dict[str, Any]:
    """
    Runs the full maintenance analysis for ONE piece of equipment:
      - health_score() + status_for_score() -> critical alert if needed
      - detect_patterns(equipment_id=...) -> alert for each high-risk pattern

    Safe to call repeatedly. alert_service's duplicate detection (same
    equipment_id + severity + title + description, status == "open",
    within the configured window) prevents re-alerting on every run while
    the same condition persists.
    """
    stats: Dict[str, Any] = {
        "equipment_id": equipment_id,
        "health_score": None,
        "status": None,
        "patterns_detected": 0,
        "high_risk_patterns": 0,
        "alerts_created": 0,
        "alerts_deduplicated": 0,
    }

    score = maintenance.health_score(db, equipment_id)
    status = maintenance.status_for_score(score)
    stats["health_score"] = score
    stats["status"] = status

    if status == "critical":
        alert = alert_service.create_alert(
            db=db,
            equipment_id=equipment_id,
            severity="critical",
            title="Critical equipment health degradation",
            description=(
                f"Health score for {equipment_id} has dropped to {score}, "
                f"indicating a critical condition."
            ),
            recommended_action="Schedule immediate inspection and maintenance.",
        )
        _tally(stats, alert)

    detected_patterns: List[Dict[str, Any]] = maintenance.detect_patterns(
        db, equipment_id=equipment_id
    )
    stats["patterns_detected"] = len(detected_patterns)

    for pattern in detected_patterns:
        if pattern["risk_level"] != "high":
            continue

        stats["high_risk_patterns"] += 1

        alert = alert_service.create_alert(
            db=db,
            equipment_id=pattern["equipment_id"],
            severity=PATTERN_ALERT_SEVERITY,
            title=pattern["title"],
            description=pattern["description"],
            recommended_action=pattern["recommended_action"],
        )
        _tally(stats, alert)

    return stats


def run_maintenance_check_for_all_equipment(db: Session) -> Dict[str, Any]:
    """
    Scheduler entry point. Queries every row in the existing Equipment
    table (there is no active/decommissioned flag on the model to filter
    on, so all equipment is checked) and runs run_maintenance_check() for
    each. This is the ONLY function a scheduler needs to call:

        run_maintenance_check_for_all_equipment(db)

    No equipment IDs need to be passed in manually.
    """
    equipment_ids = db.scalars(select(Equipment.equipment_id)).all()

    results = [run_maintenance_check(db, eq_id) for eq_id in equipment_ids]

    return {
        "equipment_checked": len(equipment_ids),
        "details": results,
        "total_alerts_created": sum(r["alerts_created"] for r in results),
        "total_alerts_deduplicated": sum(r["alerts_deduplicated"] for r in results),
    }