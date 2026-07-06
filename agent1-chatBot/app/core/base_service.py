"""
app/core/base_service.py

WHY THIS FILE EXISTS
---------------------
This is the single most important file for the spec's "MOST IMPORTANT
REQUIREMENT" - that Agent 1's capabilities (Embedding Service,
Retrieval Service, Prompt Builder, Citation Builder, Confidence
Engine, Conversation Memory) be reusable by a future Agent
Orchestrator and by Agent 2/3/4 WITHOUT code duplication.

Every service class in the upcoming `app/services/` folder (and the
lower-level building blocks in `embeddings/`, `retrieval/`, `prompts/`,
`citations/`, `confidence/`) inherits from `BaseService`. That gives
every single one of them, for free:

    1. A UNIFORM constructor contract - `__init__(self, settings)` -
       so dependency injection (FastAPI `Depends`, or an orchestrator
       constructing these directly in-process) never has to special-
       case how a particular service is built.
    2. A `logger` bound with the service's own class name, so log
       lines are automatically attributable without every subclass
       repeating `get_logger(__name__)` boilerplate.
    3. A mandatory `health_check()` contract - the upcoming GET
       /health endpoint calls `health_check()` on every registered
       service to report granular subsystem health (e.g. "embedding
       model loaded: true, vector store reachable: true, Groq
       reachable: true") rather than a single opaque "OK".
    4. A `service_name` identity string usable in logs, health
       responses, and (eventually) orchestrator service discovery.

WHY an ABC (not a Protocol): services here are meant to be
INHERITED from - they share concrete behavior (the bound logger,
settings storage) in addition to the abstract contract. A `Protocol`
would only express the interface shape, forcing every subclass to
re-implement the constructor/logger wiring by hand.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from app.config.logging_config import get_logger
from app.config.settings import Settings


class BaseService(ABC):
    """
    Abstract base class for every business-logic service in this
    codebase.

    Subclasses MUST implement `health_check()`. Everything else
    (settings storage, a pre-bound logger, the `service_name`
    property) is provided here so subclasses stay focused purely on
    their own domain logic.
    """

    def __init__(self, settings: Settings) -> None:
        """
        Args:
            settings: The validated application `Settings` instance
                (see app/config/settings.py::get_settings). Passed in
                explicitly rather than each service calling
                `get_settings()` itself - this is what allows Agent
                2/3/4 or a future orchestrator to construct this same
                service with THEIR OWN settings object (e.g. a
                different GROQ_MODEL or a different ChromaDB
                collection) without subclassing or monkey-patching
                anything.
        """
        self.settings = settings
        # WHY bind `service=self.service_name` here: every log line
        # emitted via `self.logger` from ANY subclass automatically
        # carries which service produced it, with zero extra
        # boilerplate in each subclass.
        self.logger = get_logger(self.__class__.__module__).bind(
            service=self.service_name
        )
        self.logger.debug(f"{self.service_name} initialized")

    @property
    def service_name(self) -> str:
        """
        Human-readable service identity, defaults to the class name.

        WHY overridable rather than always hardcoded to
        `self.__class__.__name__`: some subclasses may want a more
        descriptive name for health-check/orchestrator-facing output
        (e.g. "embedding-service-v1") than their raw Python class name.
        Subclasses are free to override this property; the default
        below means MOST subclasses never have to.
        """
        return self.__class__.__name__

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Report this service's operational health.

        WHY every service must implement this individually rather
        than a generic "am I instantiated" check: real health for,
        say, the embedding service means "is the sentence-transformers
        model loaded and can it encode a test string", while for the
        LLM service it means "can we reach Groq". A one-size-fits-all
        check in the base class would be meaningless for most
        services, so the CONTRACT is enforced here (every service
        must answer this question) while the IMPLEMENTATION is always
        left to the subclass that actually knows what "healthy" means
        for its domain.

        Returns:
            A dict of the shape:
                {
                    "service": "EmbeddingService",
                    "healthy": True,
                    "details": {...service-specific diagnostics...}
                }
            This exact shape is aggregated by GET /health (upcoming
            `api/` folder) across every registered service.
        """
        raise NotImplementedError
