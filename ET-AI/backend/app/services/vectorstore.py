"""Vector store with two interchangeable backends.

Preferred: ChromaDB persistent collection (if installed).
Fallback: built-in JSON-persisted store with pure-python cosine search.

Both store per-chunk metadata (document, page, doc_type, equipment tags) so
retrieval results always carry citation info.
"""
import json
import uuid
from pathlib import Path

from ..config import VECTORSTORE_DIR
from .embeddings import cosine, embed_texts, tokenize
from .entities import extract_entities


class LocalVectorStore:
    """Dependency-free persistent vector store (JSON on disk, RAM at runtime)."""

    def __init__(self, path: Path):
        self.path = path
        self.chunks: list[dict] = []
        if path.exists():
            try:
                self.chunks = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self.chunks = []

    def _save(self):
        self.path.write_text(json.dumps(self.chunks), encoding="utf-8")

    def add_chunks(self, doc_id, doc_name, doc_type, department, chunks) -> list[str]:
        vectors = embed_texts([c["text"] for c in chunks])
        ids = []
        for c, vec in zip(chunks, vectors):
            cid = f"ch_{uuid.uuid4().hex[:10]}"
            tags = extract_entities(c["text"]).get("equipment_ids", [])
            self.chunks.append({
                "chunk_id": cid,
                "doc_id": doc_id,
                "document": doc_name,
                "doc_type": doc_type,
                "department": department,
                "page": c["page"],
                "text": c["text"],
                "equipment_tags": tags,
                "vector": vec,
            })
            ids.append(cid)
        self._save()
        return ids

    def delete_doc(self, doc_id: str) -> int:
        before = len(self.chunks)
        self.chunks = [c for c in self.chunks if c["doc_id"] != doc_id]
        self._save()
        return before - len(self.chunks)

    def count(self) -> int:
        return len(self.chunks)

    def search(self, query: str, top_k: int = 15, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        qvec = embed_texts([query])[0]
        qterms = set(tokenize(query))
        results = []
        for c in self.chunks:
            if filters.get("doc_type") and c["doc_type"] != filters["doc_type"]:
                continue
            if filters.get("equipment_id"):
                eq = filters["equipment_id"].upper()
                if eq not in c["equipment_tags"] and eq not in c["text"].upper():
                    continue
            sim = cosine(qvec, c["vector"])
            overlap = 0.0
            if qterms:
                cterms = set(tokenize(c["text"]))
                overlap = len(qterms & cterms) / len(qterms)
            score = 0.6 * sim + 0.4 * overlap
            results.append({**{k: c[k] for k in (
                "chunk_id", "doc_id", "document", "doc_type", "department", "page", "text")},
                "score": round(score, 4)})
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]


class ChromaStore:
    """ChromaDB-backed store using our embedding function (no ONNX download)."""

    def __init__(self, path: Path):
        import chromadb  # noqa: F401 — raises if unavailable

        self._client = chromadb.PersistentClient(path=str(path / "chroma"))
        self._col = self._client.get_or_create_collection(
            "intelliplant", metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, doc_id, doc_name, doc_type, department, chunks) -> list[str]:
        vectors = embed_texts([c["text"] for c in chunks])
        ids = [f"ch_{uuid.uuid4().hex[:10]}" for _ in chunks]
        self._col.add(
            ids=ids,
            embeddings=vectors,
            documents=[c["text"] for c in chunks],
            metadatas=[{
                "doc_id": doc_id,
                "document": doc_name,
                "doc_type": doc_type,
                "department": department,
                "page": c["page"],
                "equipment_tags": ",".join(extract_entities(c["text"]).get("equipment_ids", [])),
            } for c in chunks],
        )
        return ids

    def delete_doc(self, doc_id: str) -> int:
        got = self._col.get(where={"doc_id": doc_id})
        ids = got.get("ids", [])
        if ids:
            self._col.delete(ids=ids)
        return len(ids)

    def count(self) -> int:
        return self._col.count()

    def search(self, query: str, top_k: int = 15, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        where = {"doc_type": filters["doc_type"]} if filters.get("doc_type") else None
        qvec = embed_texts([query])[0]
        n = min(max(top_k * 3, top_k), max(self._col.count(), 1))
        res = self._col.query(query_embeddings=[qvec], n_results=n, where=where)
        out = []
        for cid, text, meta, dist in zip(
            res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]
        ):
            if filters.get("equipment_id"):
                eq = filters["equipment_id"].upper()
                if eq not in (meta.get("equipment_tags") or "") and eq not in text.upper():
                    continue
            qterms = set(tokenize(query))
            overlap = len(qterms & set(tokenize(text))) / len(qterms) if qterms else 0.0
            sim = max(0.0, 1.0 - dist)
            out.append({
                "chunk_id": cid,
                "doc_id": meta["doc_id"],
                "document": meta["document"],
                "doc_type": meta["doc_type"],
                "department": meta.get("department", ""),
                "page": meta.get("page", 1),
                "text": text,
                "score": round(0.6 * sim + 0.4 * overlap, 4),
            })
        out.sort(key=lambda r: r["score"], reverse=True)
        return out[:top_k]


_store = None
_backend_name = None


def get_store():
    global _store, _backend_name
    if _store is None:
        try:
            _store = ChromaStore(VECTORSTORE_DIR)
            _backend_name = "chromadb"
        except Exception:
            _store = LocalVectorStore(VECTORSTORE_DIR / "chunks.json")
            _backend_name = "local-json"
    return _store


def get_store_backend() -> str:
    get_store()
    return _backend_name
