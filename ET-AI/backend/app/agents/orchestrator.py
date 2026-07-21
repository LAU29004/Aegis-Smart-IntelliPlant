"""Agent Orchestrator — routes each query and enriches RAG context with
structured knowledge from the specialist agents when relevant."""
import re

from sqlalchemy.orm import Session

from ..services.rag import answer_query
from . import compliance, maintenance

_EQ_ID = re.compile(r"\b([A-Z]{1,3}-\d{2,4})\b", re.IGNORECASE)
_MAINT_HINTS = ("fail", "history", "maintenance", "repair", "breakdown", "work order",
                "serviced", "rca", "root cause")
_COMPLIANCE_HINTS = ("compliance", "regulation", "oisd", "factory act", "peso", "iso",
                     "certificat", "license", "licence", "audit", "expir")


def handle_query(db: Session, query: str, history: list[dict] | None = None,
                 filters: dict | None = None) -> dict:
    """Main entry: RAG answer, with agent-provided structured context appended
    to the answer when the query clearly calls for it."""
    result = answer_query(query, history=history, filters=filters)
    lowered = query.lower()

    eq_match = _EQ_ID.search(query)
    if eq_match and any(h in lowered for h in _MAINT_HINTS):
        eq_id = eq_match.group(1).upper()
        events = maintenance.timeline(db, eq_id)
        failures = [e for e in events if e["event_type"] == "failure"][:5]
        if failures:
            lines = [f"- **{e['date']}** — {e['title']}"
                     + (f" ({e['work_order']})" if e['work_order'] else "")
                     for e in failures]
            result["answer"] += (
                f"\n\n**{eq_id} — recent failure records (Maintenance Agent):**\n"
                + "\n".join(lines)
            )
            result["confidence"] = max(result["confidence"], 85)
            result["confidence_level"] = "high"

    if any(h in lowered for h in _COMPLIANCE_HINTS):
        expiring = compliance.expiring_certifications(db)[:5]
        if expiring:
            lines = [f"- {c['name']} — expires {c['expiry_date']} "
                     f"({c['days_remaining']} days, {c['department']})" for c in expiring]
            result["answer"] += (
                "\n\n**Expiring certifications (Compliance Agent):**\n" + "\n".join(lines)
            )
    return result
