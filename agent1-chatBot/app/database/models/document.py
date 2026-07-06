"""
app/database/models/document.py

WHY THIS FILE EXISTS
---------------------
The system of record for every file ingested into IntelliPlant. While
ChromaDB stores the VECTORS for a document's chunks, this table stores
everything relational: which department it belongs to, what equipment
it relates to, its ingestion status, and a content hash used to
detect and reject duplicate uploads. `GET /documents` and
`DELETE /document/{id}` (per the spec's API design) are both backed
directly by this table.
"""

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.constants import DocumentType
from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import DocumentStatus

if TYPE_CHECKING:  # pragma: no cover - import-cycle avoidance only
    from app.database.models.chunk import Chunk
    from app.database.models.user import User


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single ingested source file (PDF, scanned PDF, image, or -
    future - Excel workbook) and its ingestion metadata.

    WHY `content_hash` is unique+indexed: prevents the same physical
    document from being ingested twice (wasting embedding compute and
    polluting retrieval with duplicate chunks) if someone uploads the
    same PDF a second time, possibly under a different filename.

    WHY `department` and `equipment_id` are stored HERE and also
    denormalized onto every `Chunk` row (see chunk.py): metadata
    filtering (a named stage in the query pipeline, right after Vector
    Search) needs to filter ChromaDB results by department/equipment
    without a join back to this table for every one of the top-15
    candidates. Denormalization here is a deliberate read-performance
    trade-off, not an oversight.
    """

    __tablename__ = "documents"

    filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Sanitized filename as stored on disk / in object storage.",
    )
    original_filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="The filename as originally uploaded by the user, preserved "
        "for display purposes even after sanitization.",
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type", native_enum=False, length=20),
        nullable=False,
    )
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    equipment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    file_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        doc="Absolute or object-storage path to the original uploaded file, "
        "used for re-processing or audit purposes.",
    )
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_hash: Mapped[str] = mapped_column(
        String(64),  # SHA-256 hex digest length
        unique=True,
        nullable=False,
        index=True,
        doc="SHA-256 hash of the file's raw bytes, used to detect and "
        "reject duplicate uploads before they consume ingestion resources.",
    )
    total_pages: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Total page count for PDFs; null for single-page image uploads.",
    )
    total_chunks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Denormalized count of this document's chunks, updated once "
        "ingestion completes - avoids a COUNT(*) query for GET /documents.",
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", native_enum=False, length=20),
        default=DocumentStatus.PENDING,
        nullable=False,
        index=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Populated when status=FAILED, holding the human-readable "
        "reason (e.g. from an OCRProcessingError or TextExtractionError) "
        "so GET /documents can surface WHY ingestion failed.",
    )
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="WHY ON DELETE SET NULL rather than CASCADE: deleting a user "
        "account must never silently delete the documents they uploaded - "
        "those documents remain part of the plant's knowledge base.",
    )

    # --- Relationships ---------------------------------------------
    uploaded_by_user: Mapped[Optional["User"]] = relationship(
        back_populates="uploaded_documents",
        foreign_keys=[uploaded_by],
    )
    chunks: Mapped[List["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        # WHY cascade delete-orphan HERE (but not on the user relationship
        # above): a Chunk has no meaning without its parent Document - if
        # a document is deleted (DELETE /document/{id}), its chunks must
        # be deleted too, both here in Postgres AND in ChromaDB (handled
        # explicitly by the service layer, since ChromaDB is a separate
        # store SQLAlchemy cascades cannot reach).
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return (
            f"<Document id={self.id} filename={self.filename!r} "
            f"status={self.status.value} chunks={self.total_chunks}>"
        )
