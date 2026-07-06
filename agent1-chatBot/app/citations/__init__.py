"""
app/citations package.

WHY a dedicated `citations` package: implements the "Citation
Builder" pipeline stage as its own service, consumed by `services/`
(upcoming folder) AFTER the LLM has generated its answer - `[n]`
markers only exist once `GroqLLMService.generate_completion(...)` has
returned text to parse. `CitationBuilderService` depends on
`app.prompts.schemas.SourceReference` (the numbering `prompts/`
assigned) but nothing in `prompts/` depends back on `citations/`,
keeping the pipeline's dependency direction strictly forward.
"""

from app.citations.citation_builder_service import CitationBuilderService
from app.citations.schemas import Citation, RelatedDocument

__all__ = [
    "CitationBuilderService",
    "Citation",
    "RelatedDocument",
]
