"""
Centralized Alert creation service.

This module is the ONLY place in the codebase permitted to:
  - construct/insert Alert rows
  - commit Alert rows
  - call notify_alert()

All fields, statuses, severities, ID format, and normalization rules
below are reused exactly as they already exist in database.py and
routers/alerts.py. Nothing renamed, nothing invented.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import ALERT_DUPLICATE_WINDOW_HOURS
from ..database import Alert
from .notification_dispatcher import notify_alert


def _find_recent_open_duplicate(
    db: Session,
    equipment_id: str,
    severity: str,
    title: str,
    description: str,
) -> Alert | None:
    """
    Looks for an existing OPEN alert with the same equipment_id, severity,
    title, and description, triggered within the configured duplicate
    window.

    Returns that Alert if found, else None.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ALERT_DUPLICATE_WINDOW_HOURS)

    stmt = (
        select(Alert)
        .where(
            Alert.equipment_id == equipment_id,
            Alert.severity == severity,
            Alert.title == title,
            Alert.description == description,
            Alert.status == "open",
            Alert.triggered_at >= cutoff,
        )
        .order_by(Alert.triggered_at.desc())
    )
    return db.scalars(stmt).first()


def create_alert(
    db: Session,
    equipment_id: str,
    severity: str,
    title: str,
    description: str,
    recommended_action: str = "",
) -> Alert:
    """
    Single entry point for creating an alert anywhere in the system.

    Behavior:
    1. Normalizes equipment_id (upper) and severity (lower), exactly as
       the existing POST /alerts handler did.
    2. Duplicate detection: same equipment_id + severity + title +
       description, status == "open", triggered_at within the configured
       window (ALERT_DUPLICATE_WINDOW_HOURS). If found, returns the
       existing Alert. Does NOT create a new row. Does NOT call
       notify_alert() again.
    3. Otherwise creates the Alert using the existing model/constructor,
       generates alert_id in the existing "ALT-XXXXXXXX" format, sets
       status="open" and triggered_at=datetime.now(timezone.utc).
       Commit is wrapped in a try/except: on failure the transaction is
       rolled back and the exception is re-raised, so the caller (router
       or scheduler) sees a clean, consistent DB state either way.
    4. Calls notify_alert() using the existing signature. Notification
       failures are caught and reported via the alert.notification_sent
       attribute — they never roll back the already-committed alert and
       never block alert creation, matching the previous router behavior.

    Two transient (non-persisted, non-mapped) attributes are attached to
    the returned object so callers can distinguish outcomes without a
    second query:
      - alert.is_new: True if a new row was created, False if an existing
        open alert was returned instead. Callers should read this via
        getattr(alert, "is_new", False) rather than assuming it's always
        present, since a plain Alert loaded elsewhere (e.g. db.get())
        won't have it set.
      - alert.notification_sent: True if a new alert was created and
        notify_alert() succeeded, False otherwise (whether because
        notify_alert() raised, or because this was a duplicate and no
        notification attempt was made at all).
    """
    equipment_id = equipment_id.upper()
    severity = severity.lower()

    existing = _find_recent_open_duplicate(
        db, equipment_id, severity, title, description
    )
    if existing is not None:
        existing.is_new = False
        existing.notification_sent = False
        return existing

    alert = Alert(
        alert_id=f"ALT-{uuid.uuid4().hex[:8].upper()}",
        equipment_id=equipment_id,
        severity=severity,
        title=title,
        description=description,
        triggered_at=datetime.now(timezone.utc),
        status="open",
        recommended_action=recommended_action,
    )

    db.add(alert)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(alert)

    notification_sent = True
    try:
        notify_alert(
            db=db,
            alert_id=alert.alert_id,
            equipment_id=alert.equipment_id,
            severity=alert.severity,
            title=alert.title,
            description=alert.description,
        )
    except Exception as e:
        print(f"Notification error:{e}")
        notification_sent = False

    alert.is_new = True
    alert.notification_sent = notification_sent
    return alert