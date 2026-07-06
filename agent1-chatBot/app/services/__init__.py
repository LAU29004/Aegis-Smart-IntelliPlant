"""
app/services package.

WHY a dedicated `services` package: this is the COMPOSITION ROOT for
Agent 1 - the only place where the independently-reusable building
blocks from every other folder (`retrieval/`, `prompts/`, `llm/`,
`citations/`, `confidence/`, `suggestions/`, `ingestion/`,
`embeddings/`) get wired together into the two end-to-end use cases
the spec's API actually exposes: answering a query
(`QueryPipelineService`) and ingesting a document
(`DocumentUploadPipelineService`) - plus `ConversationMemoryService`,
reusable independently of either pipeline.

`app/api/` (upcoming folder) depends ONLY on the three services
exported here for its route handlers. It never reaches into
`retrieval/`, `llm/`, etc. directly - that would bypass the
orchestration (persistence, error handling, graceful degradation)
this layer is responsible for.
"""

from app.services.conversation_memory_service import ConversationMemoryService
from app.services.document_upload_pipeline_service import DocumentUploadPipelineService
from app.services.query_pipeline_service import QueryPipelineService
from app.services.schemas import QueryPipelineResult, UploadPipelineResult

__all__ = [
    "ConversationMemoryService",
    "DocumentUploadPipelineService",
    "QueryPipelineService",
    "QueryPipelineResult",
    "UploadPipelineResult",
]
