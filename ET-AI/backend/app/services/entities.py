"""Lightweight industrial entity extraction (regex NER).

Production path: spaCy + custom-trained industrial NER model. The regex
rules below cover the entity classes the platform indexes: equipment tags,
work orders, dates, process parameters, regulation references, people.
"""
import re

_EQUIPMENT = re.compile(r"\b[A-Z]{1,3}-\d{2,4}[A-Z]?\b")
_WORK_ORDER = re.compile(r"\bWO-\d{4}-\d{3,4}\b")
_INCIDENT = re.compile(r"\bINC-\d{4}-\d{3,4}\b")
_DATE = re.compile(
    r"\b(?:\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}"
    r"|\d{4}-\d{2}-\d{2}"
    r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b"
)
_PARAMETER = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:bar(?:g)?|°C|deg\s?C|mm/s|RPM|rpm|kW|MW|kg/h|m3/h|Hz|%|hours|hrs|psi|lpm)\b"
)
_REGULATION = re.compile(
    r"\b(?:OISD[-\s]?\d+|ISO\s?\d{4,5}(?::\d{4})?|IS\s?\d{3,5}|Factory\s?Act(?:\s?1948)?|PESO|IBR\s?1950)\b",
    re.IGNORECASE,
)
_PERSON = re.compile(
    r"(?:Technician|Engineer|Inspector|Approved by|Reported by|Supervisor)[:\s]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)"
)


def extract_entities(text: str) -> dict:
    def uniq(matches):
        seen, out = set(), []
        for m in matches:
            if m not in seen:
                seen.add(m)
                out.append(m)
        return out[:25]

    work_orders = uniq(_WORK_ORDER.findall(text)) + uniq(_INCIDENT.findall(text))
    equipment = [e for e in uniq(_EQUIPMENT.findall(text)) if not e.startswith(("WO-", "INC-"))]
    return {
        "equipment_ids": equipment,
        "work_orders": work_orders,
        "dates": uniq(_DATE.findall(text)),
        "parameters": uniq(_PARAMETER.findall(text)),
        "regulations": uniq(_REGULATION.findall(text)),
        "people": uniq(_PERSON.findall(text)),
    }
