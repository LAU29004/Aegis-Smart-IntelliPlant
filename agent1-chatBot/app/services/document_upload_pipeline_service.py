"""
app/services/document_upload_pipeline_service.py

WHY THIS FILE EXISTS
---------------------
Implements the spec's full ingestion pipeline end to end:

    Upload -> OCR if required -> Text Extraction -> Cleaning ->
    Chunking -> Metadata Extraction -> Embedding -> Store in
    ChromaDB -> Store Metadata in PostgreSQL

`DocumentIngestionService` (see `app/ingestion/`) already handles
everything through Metadata Extraction. This service picks up from
there: embeds the enriched chunks, generates the client-side UUIDs
that link a `Chunk` row to its ChromaDB vector (see
`app/database/base.py::UUIDPrimaryKeyMixin`'s docstring for why that
ordering matters), and writes to BOTH stores as one coordinated
operation - rolling the `Document` row's status back to `FAILED`
(with an explanatory `error_message`) if anything in that chain
breaks, rather than leaving a half-ingested document silently stuck
in `PROCESSING`.

WHY DOCUMENT DELETION ALSO LIVES HERE
-------------------------------------------
`DELETE /document/{id}` must remove a document from BOTH ChromaDB and
PostgreSQL. SQLAlchemy's cascade (`Document.chunks`,
`cascade="all, delete-orphan"`) already handles the PostgreSQL side
automatically, but - as documented directly on that relationship in
`app/database/models/document.py` - it CANNOT reach ChromaDB, a
completely separate store. This service is where that gap is closed:
`delete_document` explicitly deletes the ChromaDB vectors FIRST, then
lets the ORM cascade handle Postgres, keeping both stores consistent
even if a future crash occurs between the two steps (a document
partially deleted from Chroma but still fully present in Postgres is
recoverable by re-running deletion; the reverse - vectors surviving
in Chroma after the Postgres row is gone - would be a silent,
undetectable leak).
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.core.base_service import BaseService
from app.core.constants import DocumentType, PipelineStage
from app.core.exceptions import DuplicateRecordError, RecordNotFoundError
from app.database.enums import DocumentStatus
from app.database.models import Chunk, Document
from app.embeddings.embedding_service import EmbeddingService
from app.ingestion.document_ingestion_service import DocumentIngestionService
from app.retrieval.vector_store_service import VectorStoreService
from app.services.schemas import UploadPipelineResult
from app.utils.file_validation import validate_upload
from app.utils.filename_utils import build_storage_filename
from app.utils.hashing import sha256_hex
from app.utils.text_utils import truncate

# WHY this is the ONE place the PDF-vs-image ingestion routing
# decision is made: `Settings.ALLOWED_UPLOAD_EXTENSIONS` is the
# broader allow-list for "files this service accepts at all" (used by
# a future `api/` route for basic upload validation); THIS set is
# specifically about which ingestion METHOD (`ingest_pdf` vs
# `ingest_image`) applies to an already-accepted file.
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


class DocumentUploadPipelineService(BaseService):
    """
    Orchestrates the full ingestion pipeline: content-hash dedup,
    extraction/OCR/cleaning/chunking (via `DocumentIngestionService`),
    embedding, and coordinated persistence to both ChromaDB and
    PostgreSQL.
    """

    def __init__(
        self,
        settings: Settings,
        document_ingestion_service: DocumentIngestionService,
        embedding_service: EmbeddingService,
        vector_store_service: VectorStoreService,
    ) -> None:
        super().__init__(settings)
        self.document_ingestion_service = document_ingestion_service
        self.embedding_service = embedding_service
        self.vector_store_service = vector_store_service

    def upload_document(
        self,
        db: Session,
        file_bytes: bytes,
        filename: str,
        *,
        department: Optional[str] = None,
        equipment_id: Optional[str] = None,
        uploaded_by: Optional[uuid.UUID] = None,
    ) -> UploadPipelineResult:
        """
        Run one uploaded file through the complete ingestion pipeline.

        Args:
            db: Request-scoped SQLAlchemy session.
            file_bytes: Raw uploaded file content.
            filename: Original filename (used for both storage naming
                and the extension-based PDF/image routing decision).
            department, equipment_id: Optional document-level metadata.
            uploaded_by: Optional uploading user's id.

        Returns:
            An `UploadPipelineResult` describing the persisted
            document.

        Raises:
            DocumentValidationError: empty file, unsupported extension.
            DuplicateRecordError: a document with identical content
                (by SHA-256 hash) already exists.
            Any exception `DocumentIngestionService`, `EmbeddingService`,
                or `VectorStoreService` raises - the `Document` row is
                marked `FAILED` with the error message before
                re-raising, so the failure is durably recorded even
                though the request itself still surfaces the error.
        """
        # WHY `validate_upload` (from app.utils.file_validation) rather
        # than inline checks here: it enforces BOTH the extension
        # allow-list AND `Settings.MAX_UPLOAD_SIZE_MB` in one place,
        # shared with the upcoming `api/` route (which can call it even
        # earlier, against `Content-Length`, before reading the full
        # body). An earlier version of this method only checked for an
        # empty file and a hardcoded PDF/image extension set, silently
        # never enforcing a maximum size at all - a real gap this
        # retrofit closes.
        validate_upload(filename, len(file_bytes), self.settings)

        content_hash = sha256_hex(file_bytes)
        existing = db.query(Document).filter_by(content_hash=content_hash).first()
        if existing is not None:
            raise DuplicateRecordError(
                f"A document with identical content already exists "
                f"(uploaded as '{existing.original_filename}').",
                stage=PipelineStage.UPLOAD,
                details={"existing_document_id": str(existing.id)},
            )

        extension = Path(filename).suffix.lower()
        is_image = extension in _IMAGE_EXTENSIONS
        upload_date = datetime.now(timezone.utc).isoformat()
        document = Document(
            filename=build_storage_filename(content_hash, filename),
            original_filename=filename,
            document_type=DocumentType.IMAGE if is_image else DocumentType.PDF,
            department=department,
            equipment_id=equipment_id,
            file_path=f"{self.settings.UPLOAD_DIRECTORY}/{build_storage_filename(content_hash, filename)}",
            file_size_bytes=len(file_bytes),
            content_hash=content_hash,
            status=DocumentStatus.PROCESSING,
            uploaded_by=uploaded_by,
        )
        db.add(document)
        db.flush()  # assigns document.id, needed for chunk metadata below

        try:
            if is_image:
                ingestion_result = self.document_ingestion_service.ingest_image(
                    file_bytes, document_name=filename, department=department,
                    equipment_id=equipment_id, upload_date=upload_date,
                )
            else:
                ingestion_result = self.document_ingestion_service.ingest_pdf(
                    file_bytes, document_name=filename, department=department,
                    equipment_id=equipment_id, upload_date=upload_date,
                )
                # WHY document.document_type is updated here, AFTER
                # ingestion: only DocumentIngestionService can determine
                # whether OCR was actually needed (i.e. SCANNED_PDF vs
                # PDF) - see its own docstring for why that
                # classification happens during, not before, extraction.
                document.document_type = DocumentType(ingestion_result.chunks[0].document_type)

            chunk_texts = [c.content for c in ingestion_result.chunks]
            embeddings = self.embedding_service.embed_documents(chunk_texts)

            chunk_rows = []
            vector_ids, vector_embeddings, vector_documents, vector_metadatas = [], [], [], []
            for enriched_chunk, embedding in zip(ingestion_result.chunks, embeddings):
                chunk_id = uuid.uuid4()
                chunk_row = Chunk(
                    id=chunk_id,
                    document_id=document.id,
                    chunk_index=enriched_chunk.chunk_index,
                    content=enriched_chunk.content,
                    token_count=enriched_chunk.token_count,
                    page_number=enriched_chunk.page_number,
                    chroma_vector_id=str(chunk_id),
                    document_name=enriched_chunk.document_name,
                    document_type=enriched_chunk.document_type,
                    department=enriched_chunk.department,
                    equipment_id=enriched_chunk.equipment_id,
                    upload_date=enriched_chunk.upload_date,
                )
                chunk_rows.append(chunk_row)
                vector_ids.append(str(chunk_id))
                vector_embeddings.append(embedding)
                vector_documents.append(enriched_chunk.content)
                vector_metadatas.append({
                    "document_id": str(document.id),
                    "document_name": enriched_chunk.document_name,
                    "page_number": enriched_chunk.page_number,
                    "department": enriched_chunk.department,
                    "equipment_id": enriched_chunk.equipment_id,
                    "document_type": enriched_chunk.document_type,
                    "upload_date": enriched_chunk.upload_date,
                })

            # WHY ChromaDB is written BEFORE the Chunk rows are added to
            # the Postgres session: if the ChromaDB write fails, we want
            # to fail BEFORE any chunk rows exist in this transaction at
            # all (the `except` below marks the Document FAILED and the
            # transaction never commits chunk rows) - avoiding a state
            # where Postgres believes chunks exist that were never
            # actually embedded/indexed.
            self.vector_store_service.add_chunks(
                ids=vector_ids, embeddings=vector_embeddings,
                documents=vector_documents, metadatas=vector_metadatas,
            )
            db.add_all(chunk_rows)

            document.status = DocumentStatus.COMPLETED
            document.total_pages = ingestion_result.total_pages
            document.total_chunks = len(chunk_rows)
            db.flush()

        except Exception as exc:
            document.status = DocumentStatus.FAILED
            document.error_message = truncate(str(getattr(exc, "message", exc)), 2000)
            db.flush()
            raise

        self.logger.bind(stage=PipelineStage.METADATA_STORE_WRITE.value).info(
            f"Document '{filename}' ingested: {document.total_chunks} chunk(s), "
            f"{ingestion_result.ocr_page_count} page(s) via OCR"
        )
        return UploadPipelineResult(
            document_id=str(document.id),
            filename=filename,
            status=document.status,
            total_pages=document.total_pages,
            total_chunks=document.total_chunks,
            ocr_page_count=ingestion_result.ocr_page_count,
        )

    def delete_document(self, db: Session, document_id: uuid.UUID) -> None:
        """
        Delete a document from both ChromaDB and PostgreSQL.

        WHY ChromaDB is deleted FIRST, before the ORM delete: see
        module docstring - this ordering means a crash mid-deletion
        leaves an inconsistency that is safe (re-running deletion
        finishes the job) rather than unsafe (an undetectable orphaned
        vector left behind forever).

        Raises:
            RecordNotFoundError: no document with this id exists.
        """
        document = db.get(Document, document_id)
        if document is None:
            raise RecordNotFoundError(
                f"No document found with id '{document_id}'.",
                stage=PipelineStage.METADATA_STORE_WRITE,
                details={"document_id": str(document_id)},
            )

        self.vector_store_service.delete_by_document_id(str(document_id))
        db.delete(document)  # cascades to Chunk rows per the ORM relationship
        db.flush()

        self.logger.bind(stage=PipelineStage.METADATA_STORE_WRITE.value).info(
            f"Document '{document.original_filename}' ({document_id}) deleted "
            f"from both ChromaDB and PostgreSQL"
        )

    def health_check(self) -> dict:
        """Aggregates health across every sub-service this orchestrator depends on."""
        sub_checks = {
            "document_ingestion_service": self.document_ingestion_service.health_check(),
            "embedding_service": self.embedding_service.health_check(),
            "vector_store_service": self.vector_store_service.health_check(),
        }
        all_healthy = all(check["healthy"] for check in sub_checks.values())
        return {
            "service": self.service_name,
            "healthy": all_healthy,
            "details": sub_checks,
        }
