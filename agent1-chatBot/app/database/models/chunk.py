"""
app/database/models/chunk.py

WHY THIS FILE EXISTS
---------------------
Every 512-token (50-token overlap) chunk produced by the ingestion
pipeline gets ONE row here AND one vector entry in ChromaDB, linked
by `chroma_vector_id`. This table is what lets the query pipeline's
Citation Builder stage turn a ChromaDB search hit back into a
human-readable citation ("Document X, Page 4") without ChromaDB
itself needing to store rich relational data.
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.constants import DocumentType
from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:  # pragma: no cover - import-cycle avoidance only
    from app.database.models.document import Document


class Chunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single 512-token (50-token overlap) slice of a parent Document,
    carrying exactly the metadata fields the spec requires per chunk:
    Document Name, Page Number, Chunk ID, Department, Equipment ID,
    Upload Date, Document Type.

    WHY `content` is duplicated here AND embedded into ChromaDB rather
    than living ONLY in ChromaDB: Postgres is the durable, queryable,
    backup-friendly system of record. ChromaDB's persistence is
    optimized for vector similarity search, not for arbitrary
    relational queries or point-in-time recovery. Keeping the text
    here means the Context Builder pipeline stage can, if needed,
    re-fetch a chunk's exact content by primary key without depending
    on ChromaDB's metadata payload being perfectly in sync.

    WHY `chunk_id` (this row's `id`) is generated client-side (see
    `UUIDPrimaryKeyMixin`) BEFORE being written to ChromaDB: this is
    precisely so the SAME uuid can be used as the ChromaDB vector id,
    making the two stores trivially joinable by a single key with no
    separate mapping table required.
    """

    __tablename__ = "chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="0-based position of this chunk within its parent document's "
        "sliding-window split - used to reconstruct reading order and to "
        "fetch a chunk's immediate neighbors for extra context if needed.",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="The chunk's raw text (~512 tokens, 50-token overlap with "
        "adjacent chunks), post-cleaning, pre-embedding.",
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Actual token count of `content`, measured at chunking time - "
        "used to validate the chunker honored CHUNK_SIZE_TOKENS and to "
        "budget context length when building LLM prompts.",
    )
    page_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="1-indexed source page number, null for non-paginated sources "
        "like a single image.",
    )
    chroma_vector_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        doc="The id of this chunk's embedding inside ChromaDB - by "
        "convention this is `str(self.id)`, kept as an explicit column "
        "(rather than implicitly reusing `id`) so the join key is always "
        "visible and queryable without relying on an implicit convention.",
    )

    # --- Denormalized filtering/citation fields ------------------------
    # WHY denormalized from the parent Document (see document.py's
    # docstring for the full rationale): these are exactly the fields
    # the spec requires ChromaDB metadata filtering AND citation
    # building to use, and both of those stages operate on search hits
    # that only carry chunk-level data - a join back to `documents` for
    # every one of the top-15 vector search candidates, on every query,
    # would add unnecessary database load to the hottest code path in
    # the whole service.
    document_name: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(
        String(20), nullable=False  # plain string mirror of the Document's enum
    )
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    equipment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    upload_date: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        doc="ISO-8601 upload timestamp of the parent document, denormalized "
        "for display in citations without a join.",
    )

    # --- Relationships ---------------------------------------------
    document: Mapped["Document"] = relationship(back_populates="chunks")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return (
            f"<Chunk id={self.id} document_id={self.document_id} "
            f"index={self.chunk_index} page={self.page_number}>"
        )
