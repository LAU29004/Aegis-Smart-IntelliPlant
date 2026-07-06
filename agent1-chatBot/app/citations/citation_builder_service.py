"""
app/citations/citation_builder_service.py

WHY THIS FILE EXISTS
---------------------
Implements the "Citation Builder" pipeline stage: parses the `[n]`
markers the LLM was instructed (by `PromptBuilderService`'s system
prompt) to embed in its answer, and resolves each one back to the
`SourceReference` it refers to - the SAME numbering
`ContextBuilderService` assigned when building the context block the
LLM was given. This is the ONE place that numbering round-trip
happens; everywhere else in the pipeline either ASSIGNS the numbering
(`ContextBuilderService`) or just passes `SourceReference`/`Citation`
objects through without reinterpreting the numbers.

WHY an LLM citing a number that doesn't exist in `sources` is handled
gracefully (logged and skipped) rather than raising
`CitationBuildError`: LLMs occasionally hallucinate a citation number
slightly wrong (e.g. citing `[6]` when only 5 sources were provided)
even when firmly instructed not to. Failing the ENTIRE request over
one malformed citation marker - when the answer text itself may still
be perfectly accurate and grounded - would be a worse user experience
than silently dropping the one unresolvable citation and keeping
every valid one. `CitationBuildError` is reserved for genuine
programming errors (e.g. malformed input types), not LLM output
quirks this stage is specifically designed to tolerate.
"""

import re
from typing import Dict, List

from app.core.base_service import BaseService
from app.core.constants import PipelineStage
from app.core.exceptions import CitationBuildError
from app.citations.schemas import Citation, RelatedDocument
from app.prompts.schemas import SourceReference

# WHY this pattern: matches a bracketed group of one or more digits,
# optionally comma-separated - covers every citation style the system
# prompt might reasonably produce: "[1]", "[1, 2]", "[1,2,3]", and
# (since each bracket group is matched independently) "[1][2]" as two
# separate matches.
_CITATION_MARKER_PATTERN = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


class CitationBuilderService(BaseService):
    """
    Parses `[n]` citation markers out of an LLM answer and resolves
    them against the authoritative `SourceReference` list, producing
    both the answer's specific `citations` and a document-level
    `related_documents` summary.
    """

    def parse_citation_numbers(self, answer_text: str) -> List[int]:
        """
        Extract every citation number referenced in `answer_text`, in
        order of first appearance, deduplicated.

        Args:
            answer_text: The LLM's generated answer.

        Returns:
            Ordered, deduplicated list of citation numbers as they
            first appear in the text (e.g. an answer citing
            `"...[2]... [1]... [2]..."` returns `[2, 1]`).

        Raises:
            CitationBuildError: if `answer_text` is not a string.
        """
        if not isinstance(answer_text, str):
            raise CitationBuildError(
                "parse_citation_numbers() received non-string input.",
                stage=PipelineStage.CITATION_BUILDING,
                details={"received_type": type(answer_text).__name__},
            )

        numbers_in_order: List[int] = []
        seen = set()
        for match in _CITATION_MARKER_PATTERN.finditer(answer_text):
            for raw_number in match.group(1).split(","):
                try:
                    number = int(raw_number.strip())
                except ValueError:
                    continue  # malformed digit group - ignore, don't fail the whole parse
                if number not in seen:
                    seen.add(number)
                    numbers_in_order.append(number)
        return numbers_in_order

    def build_citations(
        self, answer_text: str, sources: List[SourceReference]
    ) -> List[Citation]:
        """
        Resolve every citation marker in `answer_text` against
        `sources`, in order of first appearance in the text.

        Args:
            answer_text: The LLM's generated answer.
            sources: The authoritative `SourceReference` list from
                `ContextBuilderService.build(...).sources` - the SAME
                object passed to `PromptBuilderService.build_messages`
                for this exact query.

        Returns:
            `Citation` objects for every marker that resolved to a
            real source, in order of first appearance. Citation
            numbers with no matching source are logged and silently
            skipped (see module docstring for why).
        """
        source_by_number: Dict[int, SourceReference] = {s.index: s for s in sources}
        cited_numbers = self.parse_citation_numbers(answer_text)

        citations: List[Citation] = []
        for number in cited_numbers:
            source = source_by_number.get(number)
            if source is None:
                self.logger.bind(stage=PipelineStage.CITATION_BUILDING.value).warning(
                    f"Answer cited [{number}] but no source exists at that "
                    f"index (available: {sorted(source_by_number.keys())}) - skipping"
                )
                continue
            citations.append(
                Citation(
                    number=number,
                    chunk_id=source.chunk_id,
                    document_name=source.document_name,
                    page_number=source.page_number,
                    department=source.department,
                    equipment_id=source.equipment_id,
                    relevance_score=source.relevance_score,
                )
            )

        self.logger.bind(stage=PipelineStage.CITATION_BUILDING.value).debug(
            f"Resolved {len(citations)}/{len(cited_numbers)} cited marker(s) "
            f"against {len(sources)} available source(s)"
        )
        return citations

    def build_related_documents(
        self, sources: List[SourceReference]
    ) -> List[RelatedDocument]:
        """
        Aggregate the full source list (regardless of which ones the
        LLM actually cited inline) into one entry per distinct
        document, for the spec's `related_documents` response field.

        Args:
            sources: The same `SourceReference` list used for
                `build_citations` - typically the FULL reranked
                source list, not just the cited subset, since
                `related_documents` is meant to surface everything
                retrieval considered relevant.

        Returns:
            One `RelatedDocument` per distinct `document_name`, in
            order of first appearance, with page numbers aggregated
            and sorted, and a count of how many chunks from that
            document contributed to this query's context.
        """
        documents_in_order: List[str] = []
        aggregation: Dict[str, Dict] = {}

        for source in sources:
            key = source.document_name
            if key not in aggregation:
                documents_in_order.append(key)
                aggregation[key] = {
                    "department": source.department,
                    "equipment_id": source.equipment_id,
                    "page_numbers": set(),
                    "chunk_count": 0,
                }
            if source.page_number is not None:
                aggregation[key]["page_numbers"].add(source.page_number)
            aggregation[key]["chunk_count"] += 1

        return [
            RelatedDocument(
                document_name=name,
                department=aggregation[name]["department"],
                equipment_id=aggregation[name]["equipment_id"],
                page_numbers=sorted(aggregation[name]["page_numbers"]),
                chunk_count=aggregation[name]["chunk_count"],
            )
            for name in documents_in_order
        ]

    def health_check(self) -> dict:
        """
        Verifies citation parsing and resolution work correctly on a
        small, known-answer probe covering multiple marker styles and
        one deliberately unresolvable citation number.
        """
        probe_sources = [
            SourceReference(
                index=1,
                chunk_id="probe-1",
                document_name="Probe Manual.pdf",
                page_number=1,
                department="Maintenance",
                equipment_id=None,
                relevance_score=3.0,
            ),
            SourceReference(
                index=2,
                chunk_id="probe-2",
                document_name="Probe Manual.pdf",
                page_number=2,
                department="Maintenance",
                equipment_id=None,
                relevance_score=2.0,
            ),
        ]
        probe_answer = "First fact [1]. Second fact [2][1]. Unresolvable fact [99]."
        try:
            citations = self.build_citations(probe_answer, probe_sources)
            related = self.build_related_documents(probe_sources)
            healthy = (
                len(citations) == 2
                and citations[0].number == 1
                and citations[1].number == 2
                and len(related) == 1
                and related[0].page_numbers == [1, 2]
            )
            return {
                "service": self.service_name,
                "healthy": healthy,
                "details": {"citation_count": len(citations), "related_document_count": len(related)},
            }
        except CitationBuildError as exc:
            return {
                "service": self.service_name,
                "healthy": False,
                "details": {"error": exc.message},
            }
