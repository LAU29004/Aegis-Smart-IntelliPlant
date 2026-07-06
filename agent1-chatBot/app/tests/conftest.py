"""
app/tests/conftest.py

WHY THIS FILE EXISTS
---------------------
Shared pytest fixtures used across every test module in this package.
The most important one is `settings`: rather than each test module
constructing its own `Settings` (or worse, depending on a real `.env`
file / real environment variables), `settings` here builds an
explicitly isolated `Settings` instance directly - exactly the escape
hatch `app/config/settings.py::get_settings`'s docstring describes:
"Tests can bypass the cache entirely by constructing `Settings(**overrides)`
directly ... so the singleton never leaks between test cases."

WHY `tmp_path` IS THREADED INTO EVERY SETTINGS FIXTURE
------------------------------------------------------------
`Settings`'s own `model_validator` (`_ensure_runtime_directories_exist`)
creates `CHROMA_PERSIST_DIRECTORY`, `UPLOAD_DIRECTORY`, and
`LOG_DIRECTORY` on disk as a side effect of construction. Without
pointing these at pytest's per-test `tmp_path`, every test run would
create (and never clean up) `./data/chroma_store`, `./data/uploads`,
and `./logs` directories in whatever the current working directory
happens to be - `tmp_path` gives each test function its own
automatically-cleaned-up directory instead.

WHY THIS CODEBASE'S SERVICES ARE TESTED WITH FAKE MODEL BACKENDS
RATHER THAN THE REAL SENTENCE-TRANSFORMERS/CROSS-ENCODER/GROQ MODELS
------------------------------------------------------------------------
Every embedding/reranker/LLM-backed service in this codebase accepts
an injectable loader/factory specifically FOR this purpose (see
`EmbeddingService.__init__`'s `model_loader` parameter, etc.). Real
model weights require network access this test suite should not
depend on to run in CI, and real Groq calls cost real money - the
fakes below are deterministic, fast, and offline, while still
exercising every real line of business logic (batching, error
handling, response parsing) in the services under test.
"""

import hashlib
from typing import List

import pytest

from app.config.settings import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    """
    An isolated, fully-valid `Settings` instance for tests - small
    embedding dimension (matches the fake encoder below), SQLite
    database, and every filesystem path redirected into pytest's
    per-test temporary directory.
    """
    return Settings(
        DATABASE_URL=f"sqlite:///{tmp_path}/test.db",
        GROQ_API_KEY="test-key",
        EMBEDDING_DIMENSION=8,
        CHROMA_PERSIST_DIRECTORY=str(tmp_path / "chroma_store"),
        UPLOAD_DIRECTORY=str(tmp_path / "uploads"),
        LOG_DIRECTORY=str(tmp_path / "logs"),
    )


def _deterministic_vector(text: str, dimension: int = 8) -> List[float]:
    """
    WHY hash-based rather than random: two calls with the SAME text
    must always produce the SAME vector within a single test run (and
    across runs) for retrieval/similarity assertions to be meaningful
    and reproducible - a `random.random()`-based fake would make tests
    flaky by construction.
    """
    digest = hashlib.sha256(text.encode()).digest()
    return [b / 255.0 for b in digest[:dimension]]


class FakeEncoder:
    """
    Minimal stand-in for `sentence_transformers.SentenceTransformer`,
    matching exactly the subset of its interface
    `EmbeddingService` relies on (see `app/embeddings/embedding_service.py::_EncoderModel`).
    """

    def encode(self, sentences, batch_size, normalize_embeddings, show_progress_bar):
        return [_deterministic_vector(s) for s in sentences]


class FakeCrossEncoder:
    """
    Minimal stand-in for `sentence_transformers.CrossEncoder` -
    scores a (query, text) pair by their word-overlap count, giving
    reranking tests a simple, predictable relevance signal without any
    real model inference.
    """

    def predict(self, sentence_pairs):
        scores = []
        for query, text in sentence_pairs:
            overlap = len(set(query.lower().split()) & set(text.lower().split()))
            scores.append(float(overlap))
        return scores


@pytest.fixture
def fake_encoder_loader():
    """Factory suitable for `EmbeddingService(settings, model_loader=...)`."""
    return lambda model_name: FakeEncoder()


@pytest.fixture
def fake_cross_encoder_loader():
    """Factory suitable for `CrossEncoderRerankerService(settings, model_loader=...)`."""
    return lambda model_name: FakeCrossEncoder()
