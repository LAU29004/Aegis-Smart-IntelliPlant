"""SQLAlchemy engine/session and ORM models (SQLite for the prototype;
swap DATABASE_URL to PostgreSQL in production)."""
from datetime import datetime, timezone

from sqlalchemy import create_engine, String, Integer, Float, Text, DateTime, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import DATABASE_URL


if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
    )

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    plant_id: Mapped[str] = mapped_column(String, default="PLANT-01")
    department: Mapped[str] = mapped_column(String, default="Maintenance")


class Document(Base):
    __tablename__ = "documents"
    doc_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    doc_type: Mapped[str] = mapped_column(String, default="other")
    equipment_tags: Mapped[list] = mapped_column(JSON, default=list)
    department: Mapped[str] = mapped_column(String, default="")
    file_path: Mapped[str] = mapped_column(String)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    processing_status: Mapped[str] = mapped_column(String, default="processing")
    entities: Mapped[dict] = mapped_column(JSON, default=dict)


class IngestJob(Base):
    __tablename__ = "ingest_jobs"
    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(String, default="")
    file_names: Mapped[list] = mapped_column(JSON, default=list)
    doc_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Equipment(Base):
    __tablename__ = "equipment"
    equipment_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    location: Mapped[str] = mapped_column(String)
    department: Mapped[str] = mapped_column(String)
    manufacturer: Mapped[str] = mapped_column(String, default="")
    model: Mapped[str] = mapped_column(String, default="")
    installed_on: Mapped[str] = mapped_column(String, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    last_serviced: Mapped[str] = mapped_column(String, default="")
    next_due: Mapped[str] = mapped_column(String, default="")


class MaintenanceEvent(Base):
    __tablename__ = "maintenance_events"
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String, index=True)
    date: Mapped[str] = mapped_column(String)  # ISO date
    event_type: Mapped[str] = mapped_column(String)  # failure|repair|inspection|pm
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    work_order: Mapped[str] = mapped_column(String, default="")
    document: Mapped[str] = mapped_column(String, default="")


class Alert(Base):
    __tablename__ = "alerts"
    alert_id: Mapped[str] = mapped_column(String, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String, index=True)
    severity: Mapped[str] = mapped_column(String)  # critical|warning|info
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String, default="open")
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    ai_explanation: Mapped[str] = mapped_column(Text, default="")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[str] = mapped_column(String, default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class Certification(Base):
    __tablename__ = "certifications"
    cert_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    expiry_date: Mapped[str] = mapped_column(String)  # ISO date
    department: Mapped[str] = mapped_column(String)
    document_link: Mapped[str] = mapped_column(String, default="")


class Incident(Base):
    __tablename__ = "incidents"
    incident_id: Mapped[str] = mapped_column(String, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String, default="medium")
    incident_type: Mapped[str] = mapped_column(String, default="incident")  # incident|near-miss
    date: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="closed")
    outcome: Mapped[str] = mapped_column(Text, default="")
    resolution: Mapped[str] = mapped_column(Text, default="")


class LessonCard(Base):
    __tablename__ = "lesson_cards"
    card_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    equipment_type: Mapped[str] = mapped_column(String, default="")
    what_happened: Mapped[str] = mapped_column(Text, default="")
    root_cause: Mapped[str] = mapped_column(Text, default="")
    what_was_done: Mapped[str] = mapped_column(Text, default="")
    watch_for: Mapped[str] = mapped_column(Text, default="")


class ComplianceGap(Base):
    __tablename__ = "compliance_gaps"
    gap_id: Mapped[str] = mapped_column(String, primary_key=True)
    regulation: Mapped[str] = mapped_column(String)
    requirement: Mapped[str] = mapped_column(Text)
    department: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String, default="medium")
    what_is_missing: Mapped[str] = mapped_column(Text, default="")
    recommended_action: Mapped[str] = mapped_column(Text, default="")


class QueryLog(Base):
    __tablename__ = "query_logs"
    query_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, default="")
    query: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0)
    rating: Mapped[int] = mapped_column(Integer, default=0)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[str] = mapped_column(
        String,
        index=True,
    )

    device_id: Mapped[str] = mapped_column(
        String,
        index=True,
    )

    token: Mapped[str] = mapped_column(
        Text,
        unique=True,
    )

    platform: Mapped[str] = mapped_column(
        String,
        default="android",
    )

    app_version: Mapped[str] = mapped_column(
        String,
        default="1.0.0",
    )

    is_active: Mapped[bool] = mapped_column(
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
    )

def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
