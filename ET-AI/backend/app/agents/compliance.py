"""Compliance Intelligence Agent — regulation mapping, gap detection, expiry alerts."""
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import Certification, ComplianceGap
from ..services.vectorstore import get_store

REGULATIONS = ["Factory Act 1948", "OISD-118", "PESO Guidelines", "ISO 45001", "ISO 9001"]
DEPARTMENTS = ["Maintenance", "Operations", "Safety", "Quality"]

# Requirement checklists per regulation (production path: LLM-extracted from the
# indexed regulation text itself).
REQUIREMENTS = {
    "OISD-118": [
        ("Inter-facility spacing between storage tanks must be verified and documented", "Safety"),
        ("Firewater network flow test to be conducted and recorded every 6 months", "Safety"),
        ("Hot work in hazardous areas requires a documented permit-to-work procedure", "Operations"),
    ],
    "Factory Act 1948": [
        ("Pressure vessels must be tested by a competent person at prescribed intervals", "Maintenance"),
        ("Safety officer to be appointed and safety committee meetings recorded", "Safety"),
    ],
    "ISO 45001": [
        ("Hazard identification and risk assessment records maintained for all activities", "Safety"),
    ],
    "ISO 9001": [
        ("Non-conformance reports must have documented root cause and corrective action", "Quality"),
    ],
    "PESO Guidelines": [
        ("Valid PESO license for petroleum storage displayed and renewed before expiry", "Operations"),
    ],
}


def expiring_certifications(db: Session, days: int = 60, today: date | None = None) -> list[dict]:
    today = today or date.today()
    out = []
    for cert in db.scalars(select(Certification)).all():
        try:
            exp = datetime.strptime(cert.expiry_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        remaining = (exp - today).days
        if remaining <= days:
            out.append({
                "cert_id": cert.cert_id, "name": cert.name,
                "expiry_date": cert.expiry_date, "days_remaining": remaining,
                "department": cert.department,
                "status": "expired" if remaining < 0 else "expiring",
            })
    out.sort(key=lambda c: c["days_remaining"])
    return out


def list_gaps(db: Session, department: str | None = None,
              severity: str | None = None) -> list[dict]:
    q = select(ComplianceGap)
    if department:
        q = q.where(ComplianceGap.department == department)
    if severity:
        q = q.where(ComplianceGap.severity == severity)
    gaps = db.scalars(q).all()
    order = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda g: order.get(g.severity, 3))
    return [{
        "gap_id": g.gap_id, "regulation": g.regulation, "requirement": g.requirement,
        "department": g.department, "severity": g.severity,
        "what_is_missing": g.what_is_missing, "recommended_action": g.recommended_action,
    } for g in gaps]


def build_matrix(db: Session) -> dict:
    gaps = list_gaps(db)
    expiring = expiring_certifications(db)
    expiring_departments = {c["department"] for c in expiring}
    cells = []
    compliant_cells = 0
    assessed = 0
    for reg in REGULATIONS:
        reg_departments = {d for _, d in REQUIREMENTS.get(reg, [])}
        for dept in DEPARTMENTS:
            gap_count = len([g for g in gaps if g["regulation"] == reg and g["department"] == dept])
            if gap_count:
                status = "gap"
            elif dept in reg_departments:
                status = "expiring" if dept in expiring_departments and reg in (
                    "PESO Guidelines", "Factory Act 1948") else "compliant"
            else:
                status = "not_assessed"
            if status != "not_assessed":
                assessed += 1
                if status == "compliant":
                    compliant_cells += 1
            cells.append({"regulation": reg, "department": dept,
                          "status": status, "gap_count": gap_count})
    score = round(compliant_cells / assessed * 100) if assessed else 0
    return {"regulations": REGULATIONS, "departments": DEPARTMENTS,
            "cells": cells, "overall_score": score}


def run_scan(db: Session, department: str | None = None) -> int:
    """Re-run gap detection: for each requirement, check whether any indexed SOP
    covers it (retrieval score threshold). Regenerates scan-detected gaps."""
    store = get_store()
    # drop previous scan-generated gaps (seeded ones are kept as curated findings)
    for g in db.scalars(select(ComplianceGap)).all():
        if g.gap_id.startswith("gap_scan_"):
            db.delete(g)
    found = 0
    for reg, reqs in REQUIREMENTS.items():
        for i, (req, dept) in enumerate(reqs):
            if department and dept != department:
                continue
            hits = store.search(req, top_k=3, filters={"doc_type": "sop"})
            covered = hits and hits[0]["score"] >= 0.35
            already = db.scalars(select(ComplianceGap).where(
                ComplianceGap.regulation == reg,
                ComplianceGap.requirement == req)).first()
            if not covered and not already:
                found += 1
                db.add(ComplianceGap(
                    gap_id=f"gap_scan_{reg.replace(' ', '')}_{i}",
                    regulation=reg, requirement=req, department=dept,
                    severity="high" if reg in ("OISD-118", "Factory Act 1948") else "medium",
                    what_is_missing="No indexed SOP adequately covers this requirement "
                                    "(retrieval coverage below threshold).",
                    recommended_action="Draft or upload the SOP addressing this requirement, "
                                       "then re-run the compliance scan.",
                ))
    db.commit()
    return found
