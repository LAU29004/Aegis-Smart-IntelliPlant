"""Demo seed data: users, equipment, maintenance history, alerts,
certifications, incidents, lessons, compliance gaps, query logs — plus
auto-ingestion of the sample_docs corpus on first startup."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .config import SAMPLE_DOCS_DIR
from .database import (Alert, Certification, ComplianceGap, Document, Equipment,
                       Incident, LessonCard, MaintenanceEvent, QueryLog,
                       SessionLocal, User)
from .security import hash_password
from .services.ingestion import ingest_file
from uuid import uuid4

SAMPLE_DOC_TYPES = {
    "OEM_Manual_Pump_P-101.md": ("manual", "P-101", "Maintenance"),
    "Maintenance_Log_June_2026.txt": ("maintenance_log", "", "Maintenance"),
    "Maintenance_History_P-101_Bearings.txt": ("maintenance_log", "P-101", "Maintenance"),
    "SOP_Boiler_B-02_Safe_Shutdown.md": ("sop", "B-02", "Operations"),
    "SOP_Hot_Work_Permit.md": ("sop", "", "Safety"),
    "OISD-118_Requirements_Extract.md": ("regulation", "", "Safety"),
    "Incident_Report_INC-2023-0814_HE-01.txt": ("incident", "HE-01", "Operations"),
    "Inspection_Report_Q2_2026.txt": ("inspection", "", "Maintenance"),
}


def seed_all() -> None:
    db = SessionLocal()
    try:
        if db.scalars(select(User)).first() is None:
            _seed_users(db)
            _seed_equipment(db)
            _seed_events(db)
            _seed_alerts(db)
            _seed_certifications(db)
            _seed_incidents(db)
            _seed_lessons(db)
            _seed_gaps(db)
            _seed_query_logs(db)
            db.commit()
        if db.scalars(select(Document)).first() is None:
            _ingest_sample_docs(db)
    finally:
        db.close()


def _seed_users(db):
    pw = hash_password("demo123")
    users = [
        ("u_admin", "Aditya Vadgave", "admin@intelliplant.io", "Admin", "IT"),
        ("u_manager", "Priya Sharma", "manager@intelliplant.io", "Plant Manager", "Management"),
        ("u_engineer", "Rohan Mehta", "engineer@intelliplant.io", "Engineer", "Maintenance"),
        ("u_safety", "Kavita Rao", "safety@intelliplant.io", "Safety Officer", "Safety"),
        ("u_tech", "Suresh Patil", "tech@intelliplant.io", "Field Technician", "Maintenance"),
    ]
    for uid, name, email, role, dept in users:
        db.add(User(user_id=uid, name=name, email=email, password_hash=pw,
                    role=role, plant_id="PLANT-01", department=dept))


def _seed_equipment(db):
    rows = [
        ("P-101", "Cooling Water Pump", "Centrifugal Pump", "Utility Block, Line 3",
         "Maintenance", "FlowServe Industries", "CP-450X", "2019-03-12",
         "Primary cooling water circulation pump for Line 3.", "2026-06-16", "2026-09-16"),
        ("P-102", "Cooling Water Pump (Standby)", "Centrifugal Pump", "Utility Block, Line 3",
         "Maintenance", "FlowServe Industries", "CP-450X", "2019-03-12",
         "Standby pump for P-101.", "2026-05-20", "2026-08-20"),
        ("B-02", "Package Boiler", "Boiler", "Utility Block",
         "Operations", "Thermax", "PB-8TPH", "2017-11-02",
         "8 TPH package boiler, 10.5 barg design.", "2026-06-09", "2026-09-09"),
        ("HE-01", "Shell & Tube Heat Exchanger", "Heat Exchanger", "Line 3",
         "Operations", "Alfa Laval", "ST-320", "2018-06-25",
         "Process cooler on Line 3, cooling water service.", "2025-12-10", "2026-06-10"),
        ("C-201", "Air Compressor", "Compressor", "Compressor House",
         "Maintenance", "Atlas Copco", "GA-90", "2020-01-18",
         "Plant instrument air compressor.", "2026-06-03", "2026-09-03"),
        ("M-305", "Conveyor Motor", "Motor", "Packing Line",
         "Operations", "ABB", "M3BP-132", "2021-08-30",
         "Drive motor for packing conveyor.", "2026-06-27", "2026-09-27"),
        ("T-401", "Storage Tank", "Tank", "Tank Farm",
         "Operations", "L&T", "FB-500KL", "2016-04-10",
         "500 KL Class-A product storage tank.", "2026-04-18", "2027-03-18"),
        ("CT-01", "Cooling Tower", "Cooling Tower", "Utility Block",
         "Maintenance", "Paharpur", "CT-1200", "2018-02-14",
         "Induced draft cooling tower serving Line 3.", "2026-05-12", "2026-08-12"),
    ]
    for r in rows:
        db.add(Equipment(equipment_id=r[0], name=r[1], type=r[2], location=r[3],
                         department=r[4], manufacturer=r[5], model=r[6],
                         installed_on=r[7], description=r[8],
                         last_serviced=r[9], next_due=r[10]))


def _seed_events(db):
    rows = [
        # P-101
        ("ev_p101_1", "P-101", "2026-06-14", "failure",
         "Mechanical seal failure — pump tripped on high seal leakage",
         "Dry running due to low suction pressure caused by a blocked strainer. "
         "Seal faces heat-damaged.", "WO-2026-0614", "Maintenance_Log_June_2026.txt"),
        ("ev_p101_2", "P-101", "2026-06-16", "repair",
         "Seal assembly MS-101-B replaced, strainer cleaned and flushed",
         "Suction pressure verified at 2.1 bar before restart. Returned to service "
         "after 48-hour observation.", "WO-2026-0614", "Maintenance_Log_June_2026.txt"),
        ("ev_p101_3", "P-101", "2025-11-20", "failure",
         "Drive-end bearing failure (third in 15 months)",
         "Water ingress detected in grease — seal water spray entering bearing "
         "housing. Deflector installed as interim.", "WO-2025-1120",
         "Maintenance_History_P-101_Bearings.txt"),
        ("ev_p101_4", "P-101", "2025-04-12", "failure",
         "Drive-end bearing failure",
         "Vibration rose from 4.2 to 8.5 mm/s over two weeks. Soft foot corrected.",
         "WO-2025-0412", "Maintenance_History_P-101_Bearings.txt"),
        ("ev_p101_5", "P-101", "2024-09-05", "failure",
         "Drive-end bearing failure",
         "High vibration 9.8 mm/s, bearing housing 92 degC. Grease contamination "
         "suspected.", "WO-2024-0905", "Maintenance_History_P-101_Bearings.txt"),
        ("ev_p101_6", "P-101", "2026-07-01", "inspection",
         "Post-repair inspection satisfactory",
         "Suction pressure 2.1 bar, vibration 3.1 mm/s. Bearing inspection within "
         "30 days recommended.", "", "Inspection_Report_Q2_2026.txt"),
        ("ev_p101_7", "P-101", "2026-03-14", "pm",
         "Quarterly preventive maintenance",
         "Strainer cleaned, alignment checked, bearings regreased.", "WO-2026-0314", ""),
        # B-02
        ("ev_b02_1", "B-02", "2026-06-09", "inspection",
         "Monthly boiler inspection — satisfactory",
         "Safety valve lift test OK. Statutory hydrotest due September 2026.",
         "WO-2026-0609", "Maintenance_Log_June_2026.txt"),
        ("ev_b02_2", "B-02", "2026-02-20", "pm",
         "Burner service and combustion tuning", "", "WO-2026-0220", ""),
        # HE-01
        ("ev_he01_1", "HE-01", "2023-08-14", "failure",
         "Severe fouling — Line 3 down 22 hours",
         "Tube bundle heavily fouled. Precursors: ambient >38 degC 6 days, cooling "
         "water flow 82% of design.", "", "Incident_Report_INC-2023-0814_HE-01.txt"),
        ("ev_he01_2", "HE-01", "2026-06-21", "inspection",
         "Outlet temperature trending high — watch item raised",
         "Cooling water flow 87% of design. Strainer inspection recommended.",
         "WO-2026-0621", "Maintenance_Log_June_2026.txt"),
        ("ev_he01_3", "HE-01", "2025-12-10", "pm",
         "Tube bundle cleaning and gasket replacement", "", "WO-2025-1210", ""),
        # C-201
        ("ev_c201_1", "C-201", "2026-06-03", "pm",
         "Quarterly PM — filter, oil, belt tension",
         "Discharge pressure steady at 7.2 bar.", "WO-2026-0603",
         "Maintenance_Log_June_2026.txt"),
        ("ev_c201_2", "C-201", "2026-05-30", "inspection",
         "Vibration above guideline (5.2 mm/s vs 4.5 mm/s)",
         "Trend monitoring initiated; alignment check planned.", "",
         "Inspection_Report_Q2_2026.txt"),
        # Others
        ("ev_m305_1", "M-305", "2026-06-27", "repair",
         "Cooling fan cowl replaced", "No production impact.", "WO-2026-0627",
         "Maintenance_Log_June_2026.txt"),
        ("ev_t401_1", "T-401", "2026-04-18", "inspection",
         "External visual inspection satisfactory",
         "Next OISD-129 external inspection due March 2027.", "", ""),
        ("ev_ct01_1", "CT-01", "2026-05-12", "pm",
         "Fill and drift eliminator check",
         "Drift eliminators partially clogged; cleaning recommended.", "WO-2026-0512", ""),
    ]
    for r in rows:
        db.add(MaintenanceEvent(event_id=r[0], equipment_id=r[1], date=r[2],
                                event_type=r[3], title=r[4], description=r[5],
                                work_order=r[6], document=r[7]))


def _seed_alerts(db):
    now = datetime.now(timezone.utc)
    rows = [
        ("AL-001", "P-101", "warning",
         "Recurring bearing failure pattern detected",
         "Three drive-end bearing failures at ~7 month intervals (Sep 2024, Apr 2025, "
         "Nov 2025). Current interval has exceeded the historical average.",
         "Schedule bearing inspection within 30 days. Reference OEM Manual "
         "Section 4.3 — Bearing Replacement Interval.",
         "The Maintenance Intelligence Agent detected that P-101 drive-end bearings "
         "fail roughly every 7 months. Grease analysis found water ingress from seal "
         "spray — replacing bearings without fixing the water path will not break the "
         "cycle. A permanent seal-water deflector is recommended.", 4),
        ("AL-002", "HE-01", "critical",
         "Fouling precursor conditions matched on Line 3",
         "Ambient above 38°C for 5+ consecutive days and cooling water flow below "
         "85% of design — the same precursor pattern seen before the 2021, 2022 and "
         "2023 fouling outages.",
         "Inspect HE-01 cooling water inlet strainer immediately. Reference Incident "
         "Report INC-2023-0814.",
         "The Failure Pattern Agent matched today's operating conditions against "
         "historical incident precursors. All three past HE-01 fouling events were "
         "preceded by exactly these conditions and caused 18–24 hours of unplanned "
         "downtime.", 1),
        ("AL-003", "HE-01", "warning",
         "Cooling water outlet temperature trending high",
         "Outlet temperature 4°C above normal for current ambient; flow at 87% of "
         "design (inspection WO-2026-0621).",
         "Verify strainer condition and biocide dosing this week.",
         "", 25),
        ("AL-004", "C-201", "warning",
         "Vibration above guideline",
         "5.2 mm/s measured against a 4.5 mm/s guideline during Q2 inspection.",
         "Perform alignment check in the next PM window; continue weekly trend "
         "readings.", "", 40),
        ("AL-005", "B-02", "info",
         "Statutory pressure vessel hydrotest due September 2026",
         "Boiler B-02 hydrotest must be completed by a competent person before the "
         "statutory deadline.",
         "Schedule the test with the competent person and block a maintenance "
         "window in August.", "", 30),
    ]
    for aid, eq, sev, title, desc, action, expl, days_ago in rows:
        db.add(Alert(alert_id=aid, equipment_id=eq, severity=sev, title=title,
                     description=desc, recommended_action=action,
                     ai_explanation=expl, status="open",
                     triggered_at=now - timedelta(days=days_ago)))


def _seed_certifications(db):
    rows = [
        ("cert_1", "Boiler Operating Certificate (IBR) — B-02", "2026-08-25", "Operations"),
        ("cert_2", "Pressure Vessel Test Certificate — Air Receiver", "2026-08-10", "Maintenance"),
        ("cert_3", "PESO Petroleum Storage License — Tank Farm", "2026-09-05", "Operations"),
        ("cert_4", "Fire NOC — PLANT-01", "2026-07-10", "Safety"),
        ("cert_5", "Consent to Operate (Environment)", "2026-12-01", "Safety"),
        ("cert_6", "Lifting Tackle Test Certificates — EOT Crane", "2026-11-15", "Maintenance"),
    ]
    for cid, name, exp, dept in rows:
        db.add(Certification(cert_id=cid, name=name, expiry_date=exp, department=dept))


def _seed_incidents(db):
    rows = [
        ("INC-2021-0722", "HE-01", "Heat exchanger fouling — Line 3 outage",
         "HE-01 fouling after sustained high ambient temperature and low cooling "
         "water flow. Line 3 down 18 hours.", "high", "incident", "2021-07-22",
         "18 hours unplanned downtime", "Tube bundle cleaned; strainer cleaning "
         "frequency reviewed."),
        ("INC-2022-0918", "HE-01", "Heat exchanger fouling recurrence",
         "Second fouling event under the same precursor conditions: ambient above "
         "38 degC and cooling water flow below 85% of design. 24 hours downtime.",
         "high", "incident", "2022-09-18", "24 hours unplanned downtime",
         "Chemical cleaning; low-flow monitoring proposed."),
        ("INC-2023-0814", "HE-01", "Severe fouling of HE-01 — Line 3 down 22 hours",
         "Tube bundle heavily fouled with scale and biological growth. Precursors: "
         "ambient above 38 degC for six days, cooling water flow 82% of design due "
         "to partially blocked inlet strainer.", "high", "incident", "2023-08-14",
         "22 hours unplanned downtime, ~180 t production loss",
         "Hydro-jetted bundle, weekly summer strainer cleaning, 88% low-flow alarm, "
         "biocide program review."),
        ("INC-2026-0614", "P-101", "Mechanical seal failure on cooling water pump",
         "Pump tripped on high seal leakage at 02:15. Dry running due to low suction "
         "pressure from a blocked suction strainer.", "medium", "incident",
         "2026-06-14", "52 hours downtime (standby P-102 carried the load)",
         "Seal assembly MS-101-B replaced; strainer cleaned; suction pressure "
         "verified 2.1 bar; strainer DP added to daily round."),
        ("INC-2025-1105", "T-401", "Near-miss: hot work started before repeat gas test",
         "Welding near tank farm resumed after lunch without the 2-hourly repeat gas "
         "test required by SOP-SAF-007. Stopped by fire watcher. No ignition.",
         "medium", "near-miss", "2025-11-05", "No injury or damage — work stopped in time",
         "Permit retraining conducted; repeat gas test made a hold point."),
    ]
    for r in rows:
        db.add(Incident(incident_id=r[0], equipment_id=r[1], title=r[2],
                        description=r[3], severity=r[4], incident_type=r[5],
                        date=r[6], outcome=r[7], resolution=r[8], status="closed"))


def _seed_lessons(db):
    rows = [
        ("lc_1", "Heat exchanger fouling follows a predictable precursor pattern",
         "Heat Exchanger",
         "HE-01 fouled three times (2021, 2022, 2023), each causing 18–24 hours of "
         "unplanned Line 3 downtime.",
         "Sustained ambient above 38°C combined with cooling water flow below 85% of "
         "design accelerates scale and biofouling; a blocked inlet strainer was the "
         "initiating condition each time.",
         "Weekly summer strainer cleaning, 88% low-flow alarm, biocide program review.",
         "Ambient >38°C for 5+ days AND cooling water flow <85% of design — inspect "
         "the inlet strainer immediately."),
        ("lc_2", "Never restart a pump after a low-suction event without checking the seal",
         "Centrifugal Pump",
         "P-101 mechanical seal destroyed by dry running after a blocked strainer "
         "dropped suction pressure below 1.5 bar (June 2026, 52 hours downtime).",
         "Mechanical seals are water-lubricated; more than 30 seconds of dry running "
         "destroys the faces (OEM manual Section 3).",
         "Seal replaced, strainer cleaned, suction pressure verified at 2.1 bar "
         "before restart, strainer DP added to daily rounds.",
         "Suction strainer DP above 0.4 bar, falling suction pressure, or any seal "
         "weep after a low-suction event."),
        ("lc_3", "Repeat bearing failures are a symptom, not the problem",
         "Rotating Equipment",
         "P-101 drive-end bearing failed three times at ~7 month intervals despite "
         "replacement with identical bearings.",
         "Grease analysis found water ingress from seal spray — the bearing was "
         "never the root cause. OEM manual: failures at <12 month intervals demand "
         "root cause investigation.",
         "Interim deflector installed; permanent seal-water deflector and RCA "
         "recommended.",
         "Any bearing that fails twice within a year on the same machine — trigger "
         "an RCA instead of a third replacement."),
    ]
    for r in rows:
        db.add(LessonCard(card_id=r[0], title=r[1], equipment_type=r[2],
                          what_happened=r[3], root_cause=r[4],
                          what_was_done=r[5], watch_for=r[6]))


def _seed_gaps(db):
    rows = [
        ("gap_seed_oisd_1", "OISD-118",
         "Inter-facility spacing between storage tanks must be verified and documented",
         "Safety", "high",
         "No documented spacing verification exists for the tank farm after the "
         "2024 pipe-rack modification.",
         "Conduct a spacing survey against OISD-118 Table 3 and file the verification "
         "record; re-verify after every facility modification."),
        ("gap_seed_oisd_2", "OISD-118",
         "Firewater network flow test to be conducted and recorded every 6 months",
         "Safety", "high",
         "Last recorded firewater flow test is more than 6 months old; no record "
         "for the current cycle.",
         "Schedule the firewater flow test within 15 days and log flow/pressure "
         "readings in the compliance register."),
        ("gap_seed_fact_1", "Factory Act 1948",
         "Pressure vessels must be tested by a competent person at prescribed intervals",
         "Maintenance", "high",
         "Boiler B-02 statutory hydrotest is due September 2026 and is not yet "
         "scheduled with a competent person.",
         "Book the competent person and block an August maintenance window; attach "
         "the test certificate once complete."),
    ]
    for r in rows:
        db.add(ComplianceGap(gap_id=r[0], regulation=r[1], requirement=r[2],
                             department=r[3], severity=r[4],
                             what_is_missing=r[5], recommended_action=r[6]))


def _seed_query_logs(db):
    now = datetime.now(timezone.utc)
    rows = [
        ("q_seed_1", "What failed on Pump P-101 last month?", 94, 0),
        ("q_seed_2", "Boiler B-02 safe shutdown procedure", 91, 1),
        ("q_seed_3", "bearing failure history P-101", 88, 1),
        ("q_seed_4", "hot work permit gas test frequency", 84, 2),
        ("q_seed_5", "spare parts list for compressor C-201", 42, 2),
        ("q_seed_6", "P&ID drawing for Line 3 cooling circuit", 35, 3),
        ("q_seed_7", "spare parts list for compressor C-201", 44, 4),
        ("q_seed_8", "vibration limits for centrifugal pumps", 82, 5),
        ("q_seed_9", "which certifications expire soon", 86, 6),
    ]
    for qid, q, conf, days_ago in rows:
        db.add(QueryLog(query_id=qid, user_id="u_engineer", query=q,
                        answer="(seeded demo query)", confidence=conf,
                        created_at=now - timedelta(days=days_ago, hours=3)))


def _ingest_sample_docs(db):
    if not SAMPLE_DOCS_DIR.exists():
        return
    for path in sorted(SAMPLE_DOCS_DIR.iterdir()):
        if path.suffix.lower() not in (".md", ".txt", ".pdf", ".xlsx", ".csv"):
            continue
        doc_type, eq_id, dept = SAMPLE_DOC_TYPES.get(path.name, ("other", "", ""))
        try:
            ingest_file(path, doc_type, eq_id, dept, db=db)
            print(f"[seed] indexed {path.name}")
        except Exception as e:
            print(f"[seed] FAILED to index {path.name}: {e}")
