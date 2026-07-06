"""
app/core/domain_enums.py

WHY THIS FILE EXISTS
--------------------
Defines business-domain enumerations shared across the IntelliPlant
platform.

Unlike database enums (stored in app/database/enums.py), these enums
represent business concepts rather than persistence concerns.

All agents (RAG Copilot, Maintenance Intelligence, Compliance,
Failure Pattern Analysis) should import these enums instead of
creating their own definitions, ensuring a consistent vocabulary
throughout the platform.
"""

from enum import Enum


class Department(str, Enum):
    """Plant departments."""

    MAINTENANCE = "Maintenance"
    MECHANICAL = "Mechanical"
    ELECTRICAL = "Electrical"
    INSTRUMENTATION = "Instrumentation"
    PRODUCTION = "Production"
    QUALITY = "Quality"
    SAFETY = "Safety"
    UTILITIES = "Utilities"
    OPERATIONS = "Operations"
    GENERAL = "General"


class EquipmentCategory(str, Enum):
    """High-level equipment categories."""

    PUMP = "Pump"
    MOTOR = "Motor"
    VALVE = "Valve"
    CONVEYOR = "Conveyor"
    COMPRESSOR = "Compressor"
    GENERATOR = "Generator"
    BOILER = "Boiler"
    TURBINE = "Turbine"
    PIPELINE = "Pipeline"
    OTHER = "Other"


class DocumentCategory(str, Enum):
    """Industrial document categories."""

    SOP = "SOP"
    MANUAL = "Manual"
    MAINTENANCE_LOG = "Maintenance Log"
    INCIDENT_REPORT = "Incident Report"
    INSPECTION_REPORT = "Inspection Report"
    COMPLIANCE_DOCUMENT = "Compliance Document"
    DRAWING = "Drawing"
    SPECIFICATION = "Specification"
    TRAINING = "Training"
    OTHER = "Other"