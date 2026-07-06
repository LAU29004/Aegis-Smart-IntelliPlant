"""
IntelliPlant - Agent 1 (RAG Copilot Agent)

This package is a standalone, independently deployable microservice.
It is one of four agents in the IntelliPlant Multi-Agent Industrial
Knowledge Intelligence Platform:

    Agent 1 - RAG Copilot                     (THIS SERVICE)
    Agent 2 - Maintenance Intelligence Agent
    Agent 3 - Compliance Intelligence Agent
    Agent 4 - Failure Pattern & Lessons Learned Agent

WHY this package exists as a top-level `app`:
    All four agents will eventually sit behind a central Agent
    Orchestrator. To make that orchestration trivial later, this
    service is built so that every capability (embedding, retrieval,
    prompt construction, citation building, confidence scoring,
    conversation memory) is exposed as an importable, dependency
    injected service class under `app.services`. Nothing here is a
    throwaway script - it is a library-grade component that other
    agents (or the orchestrator) can import directly, or call over
    HTTP via the FastAPI routes in `app.api`.
"""

__version__ = "1.0.0"