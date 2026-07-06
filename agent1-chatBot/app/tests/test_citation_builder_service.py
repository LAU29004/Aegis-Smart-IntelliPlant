"""
app/tests/test_citation_builder_service.py

Unit tests for `app.citations.citation_builder_service.CitationBuilderService`
- parsing `[n]` markers and resolving them against source references,
per the spec's explicit "Generate unit tests for ... Citation Builder"
requirement.
"""

import pytest

from app.citations.citation_builder_service import CitationBuilderService
from app.core.exceptions import CitationBuildError
from app.prompts.schemas import SourceReference


@pytest.fixture
def citation_builder(settings) -> CitationBuilderService:
    return CitationBuilderService(settings)


@pytest.fixture
def sources():
    return [
        SourceReference(index=1, chunk_id="c1", document_name="Pump Manual.pdf", page_number=3,
                         department="Maintenance", equipment_id="PUMP-101", relevance_score=4.0),
        SourceReference(index=2, chunk_id="c2", document_name="Pump Manual.pdf", page_number=4,
                         department="Maintenance", equipment_id="PUMP-101", relevance_score=2.5),
        SourceReference(index=3, chunk_id="c3", document_name="Inspection Log.pdf", page_number=12,
                         department="Maintenance", equipment_id=None, relevance_score=1.0),
    ]


class TestParseCitationNumbers:
    def test_single_marker(self, citation_builder):
        assert citation_builder.parse_citation_numbers("Fact stated here [1].") == [1]

    def test_multiple_separate_markers_preserve_first_appearance_order(self, citation_builder):
        assert citation_builder.parse_citation_numbers("[2] then [1] then [3]") == [2, 1, 3]

    def test_comma_separated_marker(self, citation_builder):
        assert citation_builder.parse_citation_numbers("Supported by [2, 3].") == [2, 3]

    def test_adjacent_bracket_markers(self, citation_builder):
        assert citation_builder.parse_citation_numbers("Claim here [1][2].") == [1, 2]

    def test_duplicate_markers_are_deduplicated(self, citation_builder):
        assert citation_builder.parse_citation_numbers("[1] and again [1] and [2]") == [1, 2]

    def test_no_markers_returns_empty_list(self, citation_builder):
        assert citation_builder.parse_citation_numbers("No citations here at all.") == []

    def test_non_string_input_raises_citation_build_error(self, citation_builder):
        with pytest.raises(CitationBuildError):
            citation_builder.parse_citation_numbers(12345)


class TestBuildCitations:
    def test_resolves_valid_citations_in_order_of_appearance(self, citation_builder, sources):
        answer = "First claim [1]. Second claim [2, 3]. Repeated claim [3][1]."
        citations = citation_builder.build_citations(answer, sources)
        assert [c.number for c in citations] == [1, 2, 3]

    def test_resolved_citation_carries_full_source_metadata(self, citation_builder, sources):
        citations = citation_builder.build_citations("Claim [1].", sources)
        assert citations[0].document_name == "Pump Manual.pdf"
        assert citations[0].page_number == 3
        assert citations[0].equipment_id == "PUMP-101"

    def test_hallucinated_citation_number_is_gracefully_skipped(self, citation_builder, sources):
        citations = citation_builder.build_citations("This cites a source that does not exist [99].", sources)
        assert citations == []

    def test_mixed_valid_and_invalid_citations_keeps_only_valid_ones(self, citation_builder, sources):
        answer = "Valid [1]. Invalid [99]. Also valid [2]."
        citations = citation_builder.build_citations(answer, sources)
        assert [c.number for c in citations] == [1, 2]

    def test_answer_with_no_citations_returns_empty_list(self, citation_builder, sources):
        citations = citation_builder.build_citations("No relevant information found in indexed documents.", sources)
        assert citations == []


class TestBuildRelatedDocuments:
    def test_aggregates_chunks_from_same_document(self, citation_builder, sources):
        related = citation_builder.build_related_documents(sources)
        pump_manual = next(r for r in related if r.document_name == "Pump Manual.pdf")
        assert pump_manual.page_numbers == [3, 4]
        assert pump_manual.chunk_count == 2

    def test_distinct_documents_produce_separate_entries(self, citation_builder, sources):
        related = citation_builder.build_related_documents(sources)
        assert len(related) == 2

    def test_preserves_order_of_first_appearance(self, citation_builder, sources):
        related = citation_builder.build_related_documents(sources)
        assert related[0].document_name == "Pump Manual.pdf"
        assert related[1].document_name == "Inspection Log.pdf"


class TestHealthCheck:
    def test_health_check_reports_healthy(self, citation_builder):
        assert citation_builder.health_check()["healthy"] is True
