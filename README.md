# ⚡ IntelliPlant
**AI-Powered Industrial Knowledge Intelligence Platform**
ET AI Hackathon 2026 · Problem Statement 8

> Ask any question about any equipment or procedure — IntelliPlant finds the answer
> across all your documents in seconds, with source citations.

Industrial plants run on thousands of documents scattered across 7–12 disconnected systems. IntelliPlant ingests every document a plant produces, builds a unified searchable knowledge base, and layers four AI agents on top:

1. **RAG Copilot** — Context-aware chat with precise document and page-level citations.
2. **Maintenance Intelligence** — Asset profiles, work history, and root-cause analysis (RCA) suggestions.
3. **Compliance Intelligence** — Automated regulation-to-department coverage gap scanning and certification expiry tracking.
4. **Failure Pattern & Lessons Learned** — Incident logs, precursor pattern matching, and lessons-learned dashboards.

---

## 📂 Repository Structure

```
intelliplant/
├── backend/            FastAPI app (Python 3.12+)
│   ├── app/
│   │   ├── routers/    REST endpoints (/api/v1/…)
│   │   ├── services/   ingestion pipeline: parsing → chunking → entities → embeddings → vector store, RAG, LLM
│   │   ├── agents/     orchestrator + maintenance / compliance / failure-pattern agents
│   │   ├── main.py     app entry (uvicorn app.main:app)
│   │   └── seed.py     demo data + auto-ingestion of sample_docs on first run
│   └── storage/        SQLite DB, vector store, uploaded files (created at runtime)
├── frontend/           Next.js 15 web dashboard (TypeScript, App Router)
├── sample_docs/        demo corpus (OEM manual, logs, SOPs, OISD-118, incident reports)
└── docs/               API contract + architecture
```

---

---

# 🌐 Live Demo

### 🔗 Web Application
https://aegis-smart-intelli-plant-vert.vercel.app/

### 🚀 Backend API
https://aegis-smart-intelliplant.onrender.com/

### 📚 Interactive API Documentation (Swagger)
https://aegis-smart-intelliplant.onrender.com/docs

---
## 🚀 Quick Start

### 1. Backend (port 8000)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

> [!NOTE]
> First startup seeds the demo plant (users, equipment, history, alerts, certifications, incidents) and **auto-indexes everything in `sample_docs/`** — the Copilot is instantly usable.
>
> Interactive API docs: http://localhost:8000/docs

### 2. Frontend (port 3000)

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** and log in:

| Email | Role | Password |
|---|---|---|
| engineer@intelliplant.io | Engineer | demo123 |
| manager@intelliplant.io | Plant Manager | demo123 |
| safety@intelliplant.io | Safety Officer | demo123 |
| tech@intelliplant.io | Field Technician | demo123 |
| admin@intelliplant.io | Admin | demo123 |

### 3. Optional: full-power mode

The prototype runs with **zero external dependencies** using built-in fallbacks. Each layer upgrades automatically when available.

**Answer generation — 3 tiers, auto-selected at startup (first available wins):**

| Priority | Tier | Internet? | Quality | How to enable |
|---|---|---|---|---|
| 1 | **Claude API** | Yes | Best | set `ANTHROPIC_API_KEY=sk-ant-…` before starting the backend |
| 2 | **Local LLM (Ollama)** | **No — fully offline** | Fluent | Install [Ollama](https://ollama.com) + `ollama pull qwen2.5:3b` (default model) |
| 3 | **Extractive** | No | Real sources, unpolished | Always available, no setup |

The offline local-LLM tier is what makes the "2 AM breakdown, no internet" case work with fluent answers. Override the model with `INTELLIPLANT_OLLAMA_MODEL` (e.g. `llama3.2:3b`, `qwen2.5:3b`), point elsewhere with `OLLAMA_HOST`, or force the extractive tier with `INTELLIPLANT_DISABLE_OLLAMA=1`. All three tiers get the same strict "answer only from the provided context" instruction — the real guard against hallucination.

**Other layers:**

| Layer | Default (works offline) | Upgrade | How |
|---|---|---|---|
| Embeddings | Hashing embedder (512-d) | **sentence-transformers** (multilingual) | `pip install -r requirements-full.txt` |
| Vector store | Built-in JSON store | **ChromaDB** | `pip install -r requirements-full.txt` |

The startup log shows which backends are active (`vector store: … | embeddings: … | llm: …`), also visible at `GET /`.

### Environment Variables

| Variable | Purpose |
|---|---|
| `INTELLIPLANT_DB` | Database URL (defaults to local SQLite `storage/intelliplant.db`) |
| `INTELLIPLANT_JWT_SECRET` | Secret key for signing JWT tokens |
| `INTELLIPLANT_DISABLE_OLLAMA` | Set to `1` to bypass Ollama and force extractive fallback |
| `INTELLIPLANT_OLLAMA_MODEL` | Target model (defaults to `qwen2.5:3b`) |
| `OLLAMA_HOST` | Point to a non-default Ollama host |
| `ANTHROPIC_API_KEY` | Enables the Claude API answer tier |

---

## 🧭 Demo Flow (3 minutes)

1. **Dashboard** — KPI cards, equipment health grid (P-101 amber, HE-01 red), live alert feed.
2. **Documents** — upload a maintenance PDF/TXT, watch the progress bar → *Indexed*.
3. **Copilot** — ask *"What failed on Pump P-101 last month and how was it fixed?"* → answer with citations (Maintenance Log June 2026, WO-2026-0614) + confidence badge, and the Maintenance Agent appends the failure record list.
4. Ask *"Boiler B-02 safe shutdown procedure"* → step-by-step from the SOP with page reference.
5. **Equipment → P-101** — full timeline, then **RCA Assistant**: type *"high vibration on drive end"* → ranked probable causes from historical work orders.
6. **Compliance** — traffic-light matrix (OISD-118 red), 3 high-severity gaps, expiring certifications (Fire NOC already expired). Hit **Run Compliance Scan**.
7. **Incidents** — proactive warning banner: today's Line 3 conditions match the HE-01 fouling precursor pattern (3 past occurrences, 18–24 h downtime each) + lessons-learned cards.
8. **Analytics** — query volume, low-confidence queries = knowledge gaps to close.

---

## 🏗️ Architecture (6 layers)

```
Input sources  →  Ingestion & processing  →  Storage  →  AI & intelligence  →  API  →  Clients
PDF TXT MD        parse → chunk(512/50) →     SQLite      RAG pipeline          FastAPI   Next.js
XLSX CSV          entity extraction →         vector      4 agents +            /api/v1   dashboard
uploads           embed → index               store       orchestrator          JWT/RBAC
```

- **Ingestion**: background jobs (FastAPI BackgroundTasks; production path Redis + Celery), per-page parsing so every chunk carries a page number for citations.
- **Entity extraction**: regex industrial NER (equipment tags, work orders, dates, parameters, regulation references, people); production path spaCy custom model.
- **RAG**: hybrid retrieval (vector similarity + keyword overlap re-rank) → top-5 context → answer with inline citations → confidence score (green ≥80 / amber 60–79 / red <60).
- **Agent orchestrator**: routes queries; enriches answers with structured agent data (equipment failure records, expiring certifications) when the question calls for it.
- **Maintenance agent**: health scores, recurring-failure interval detection, RCA from similar past events.
- **Compliance agent**: requirement→SOP coverage scan, gap register, expiry alerts.
- **Pattern agent**: incident clustering, precursor matching, lessons cards.

Full endpoint reference: [docs/API_CONTRACT.md](docs/API_CONTRACT.md)

---

## 📌 Hackathon Scope Notes

Deliberate prototype substitutions (all behind interfaces, swappable without API changes):

- SQLite ↔ PostgreSQL
- Built-in vector store ↔ ChromaDB
- BackgroundTasks ↔ Redis/Celery
- Local storage/uploads ↔ S3
- Regex NER ↔ spaCy model

OCR (Tesseract) and the React Native mobile app are documented extension points, not included in this prototype.

---

## 🛠️ Internal Links & Documentation

- **Frontend Configuration**: [frontend/README.md](frontend/README.md)
- **API Reference**: [docs/API_CONTRACT.md](docs/API_CONTRACT.md)
- **Main Backend Config**: [backend/app/config.py](backend/app/config.py)
