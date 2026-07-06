"""
app/ingestion/chunking_service.py

WHY THIS FILE EXISTS
---------------------
Implements the "Chunking" stage: a 512-token sliding window with
50-token overlap over a document's FULL, continuous token stream
(spanning all pages), per the spec. WHY the whole document is
tokenized as one continuous stream rather than chunking each page
independently: independent per-page chunking would produce awkward,
undersized final chunks for every short page and would never let a
sentence spanning a page break be captured coherently in one chunk -
exactly the kind of content fragmentation RAG systems are notorious
for. Operating on one continuous stream, while still tracking which
page each token originated from, gets both natural chunk boundaries
AND accurate page-number citations.

WHY TOKENIZATION IS WORD-BASED, NOT A REAL BPE TOKENIZER
-----------------------------------------------------------
An earlier version of this service used `tiktoken` for token
counting. That was rejected: `tiktoken`'s encodings are NOT bundled
with the package - `tiktoken.get_encoding("cl100k_base")` downloads a
multi-megabyte vocabulary file from an external CDN
(openaipublic.blob.core.windows.net) on first use, and caches it
locally. That is an unacceptable hidden runtime dependency for this
service:

    1. IntelliPlant is an on-prem INDUSTRIAL platform. Plant-floor
       deployments are frequently air-gapped or sit behind strict
       egress allow-lists for exactly the security reasons that make
       an industrial knowledge base worth building in the first
       place - a chunker that silently fails (as ChunkingError, via
       this exact code path) the first time it's asked to tokenize
       anything, purely because outbound internet to a third-party
       CDN was blocked, is not production-ready.
    2. Even where network access exists, tying chunk BOUNDARIES (and
       therefore which chunks exist in the vector store at all) to
       the success of an unrelated third-party network call
       introduces non-determinism this pipeline should never have -
       the exact same document should always produce the exact same
       chunks, every time, everywhere it's deployed.

Instead, this service counts and slides its window over WHITESPACE-
SEPARATED WORDS. This is not a true subword tokenizer, but for the
purpose this component actually serves - producing consistently-
sized, overlapping context windows - a word is a perfectly reasonable
unit, is exactly reproducible with zero dependencies, and (English
technical text averaging roughly 0.75 words per GPT-style BPE token)
keeps chunk sizes in a similar practical ballpark to what "512 tokens"
would mean under a real subword tokenizer, without ever risking a
network call.
"""

from typing import List, Tuple

from app.config.settings import Settings
from app.core.base_service import BaseService
from app.core.constants import PipelineStage
from app.core.exceptions import ChunkingError
from app.ingestion.schemas import ChunkRecord


class _OfflineWordTokenizer:
    """
    A minimal, dependency-free, fully offline "tokenizer" - splits text
    into whitespace-separated words and rejoins them with single
    spaces.

    WHY this is its own small class rather than inlining `.split()` /
    `" ".join(...)` calls directly into `ChunkingService`: giving it an
    `.encode()` / `.decode()` interface mirroring a real tokenizer
    means `ChunkingService`'s sliding-window logic below doesn't need
    to know or care that "tokens" here are actually just words - if
    this is ever swapped for a real, network-free local tokenizer
    (e.g. a vocabulary file bundled directly into the Docker image
    rather than fetched at runtime), only this class changes.
    """

    def encode(self, text: str) -> List[str]:
        return text.split()

    def decode(self, tokens: List[str]) -> str:
        return " ".join(tokens)


class ChunkingService(BaseService):
    """
    Splits cleaned, page-tagged document text into fixed-size,
    overlapping word-count chunks, per `Settings.CHUNK_SIZE_TOKENS` /
    `Settings.CHUNK_OVERLAP_TOKENS`.
    """

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._tokenizer = _OfflineWordTokenizer()

    def chunk_pages(self, cleaned_pages: List[Tuple[int, str]]) -> List[ChunkRecord]:
        """
        Chunk a document's cleaned, per-page text into overlapping
        512-word windows.

        Args:
            cleaned_pages: Ordered list of `(page_number, cleaned_text)`
                tuples - typically the output of `TextCleaningService.clean`
                applied to each `ExtractedPage.text`. Pages with empty
                text (e.g. a page that failed both native extraction
                and OCR) should be excluded by the caller before this
                is called.

        Returns:
            An ordered list of `ChunkRecord` objects covering the
            entire document, each carrying the page number its content
            BEGINS on.

        Raises:
            ChunkingError: if `cleaned_pages` is empty, if
                `CHUNK_OVERLAP_TOKENS >= CHUNK_SIZE_TOKENS` (already
                validated at the Settings layer, but re-checked here
                as a defensive guard against a Settings object being
                constructed directly, bypassing validation, in a
                test), or if the tokenizer itself fails.
        """
        if not cleaned_pages:
            raise ChunkingError(
                "Cannot chunk a document with zero pages of extractable text.",
                stage=PipelineStage.CHUNKING,
            )

        chunk_size = self.settings.CHUNK_SIZE_TOKENS
        overlap = self.settings.CHUNK_OVERLAP_TOKENS
        if overlap >= chunk_size:
            # See Settings._overlap_must_be_smaller_than_chunk - this
            # should never trip in production since Settings already
            # validates it, but chunking with a non-advancing or
            # backwards-sliding window would infinite-loop below, so a
            # defensive check here converts that into a clean,
            # immediate error rather than a hung ingestion job.
            raise ChunkingError(
                f"CHUNK_OVERLAP_TOKENS ({overlap}) must be smaller than "
                f"CHUNK_SIZE_TOKENS ({chunk_size}).",
                stage=PipelineStage.CHUNKING,
            )

        # --- Build one continuous token stream, tagging each token
        # with the page number it came from. ------------------------
        all_tokens: List[str] = []
        token_page_numbers: List[int] = []
        try:
            for page_number, page_text in cleaned_pages:
                if not page_text or not page_text.strip():
                    continue
                page_tokens = self._tokenizer.encode(page_text)
                all_tokens.extend(page_tokens)
                token_page_numbers.extend([page_number] * len(page_tokens))
                # WHY a page-boundary token is NOT inserted between
                # pages: keeping the raw token stream unbroken means
                # decoding any arbitrary slice of it back to text (see
                # below) never has to special-case stripping an
                # artificial separator token first.
        except Exception as exc:
            raise ChunkingError(
                "Failed to tokenize document text for chunking.",
                stage=PipelineStage.CHUNKING,
                original_exception=exc,
            ) from exc

        if not all_tokens:
            raise ChunkingError(
                "Document contains no non-empty page text to chunk.",
                stage=PipelineStage.CHUNKING,
            )

        # --- Slide the 512-token window across the stream, stepping
        # by (chunk_size - overlap) each time. -------------------------
        step = chunk_size - overlap
        chunks: List[ChunkRecord] = []
        start = 0
        total_tokens = len(all_tokens)

        while start < total_tokens:
            end = min(start + chunk_size, total_tokens)
            window_tokens = all_tokens[start:end]

            try:
                window_text = self._tokenizer.decode(window_tokens)
            except Exception as exc:
                raise ChunkingError(
                    "Failed to decode a token window back into text.",
                    stage=PipelineStage.CHUNKING,
                    details={"chunk_index": len(chunks), "start": start, "end": end},
                    original_exception=exc,
                ) from exc

            stripped_text = window_text.strip()
            if stripped_text:
                # WHY the starting token's page number is used (not,
                # say, the page of the MIDDLE or LAST token): a reader
                # following a citation wants to land on the page where
                # this chunk's content begins, which is the most useful
                # single page number to surface when a chunk happens to
                # straddle a page boundary.
                chunks.append(
                    ChunkRecord(
                        chunk_index=len(chunks),
                        content=stripped_text,
                        token_count=len(window_tokens),
                        page_number=token_page_numbers[start],
                    )
                )

            if end == total_tokens:
                break
            start += step

        if not chunks:
            raise ChunkingError(
                "Chunking produced zero chunks from non-empty input text - "
                "this should not happen and indicates a bug in the sliding "
                "window logic.",
                stage=PipelineStage.CHUNKING,
                details={"total_tokens": total_tokens},
            )

        self.logger.bind(stage=PipelineStage.CHUNKING.value).info(
            f"Chunked {len(cleaned_pages)} page(s) / {total_tokens} token(s) "
            f"into {len(chunks)} chunk(s) (size={chunk_size}, overlap={overlap})"
        )
        return chunks

    def health_check(self) -> dict:
        """
        Verifies the tokenizer and sliding-window chunker produce sane
        output on a small probe document.
        """
        try:
            probe_pages = [(1, "This is a short health check probe sentence for the chunker.")]
            chunks = self.chunk_pages(probe_pages)
            healthy = len(chunks) == 1 and chunks[0].page_number == 1
            return {
                "service": self.service_name,
                "healthy": healthy,
                "details": {
                    "tokenizer": "offline word-based (see module docstring)",
                    "chunk_size_tokens": self.settings.CHUNK_SIZE_TOKENS,
                    "chunk_overlap_tokens": self.settings.CHUNK_OVERLAP_TOKENS,
                    "probe_chunk_count": len(chunks),
                },
            }
        except ChunkingError as exc:
            return {
                "service": self.service_name,
                "healthy": False,
                "details": {"error": exc.message},
            }
