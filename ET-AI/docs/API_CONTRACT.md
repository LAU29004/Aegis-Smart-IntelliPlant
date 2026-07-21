# IntelliPlant API Contract (v1)

Backend base URL: `http://localhost:8000/api/v1`

Every JSON response uses this envelope:

```json
{ "success": true, "data": { ... }, "error": null, "timestamp": "2026-07-16T10:00:00Z" }
```

On error: `success=false`, `error` is a human-readable string, `data` is null.

All endpoints except `POST /auth/login` require header `Authorization: Bearer <JWT>`.

## Auth

### POST /auth/login
Body (JSON): `{ "email": "engineer@intelliplant.io", "password": "demo123" }`
Data: `{ "access_token": str, "token_type": "bearer", "user": { "user_id", "name", "email", "role", "plant_id", "department" } }`

Demo users (all password `demo123`):
- `admin@intelliplant.io` — role `Admin`
- `manager@intelliplant.io` — role `Plant Manager`
- `engineer@intelliplant.io` — role `Engineer`
- `safety@intelliplant.io` — role `Safety Officer`
- `tech@intelliplant.io` — role `Field Technician`

### GET /auth/me
Data: same `user` object as login.

## Ingestion

### POST /ingest/upload
multipart/form-data: `files` (one or more), fields `doc_type` (manual|maintenance_log|sop|inspection|incident|regulation|certificate|other), optional `equipment_id`, `department`.
Data: `{ "job_id": str, "status": "queued", "files": [str] }`

### GET /ingest/status/{job_id}
Data: `{ "job_id", "status": "queued"|"processing"|"completed"|"failed", "progress": 0-100, "error_message": str|null, "doc_ids": [str] }`

### GET /ingest/jobs
Data: `{ "jobs": [ { "job_id", "status", "progress", "file_names": [str], "created_at" } ] }`

## Query / Copilot

### POST /query/ask
Body: `{ "query": str, "conversation_history": [ { "role": "user"|"assistant", "content": str } ], "filters": { "equipment_id"?: str, "doc_type"?: str } }`
Data:
```json
{
  "query_id": "q_ab12",
  "answer": "markdown string",
  "sources": [ { "doc_id", "document": "Maintenance Log June 2025", "page": 3, "chunk_id", "snippet": str } ],
  "confidence": 94,
  "confidence_level": "high" | "medium" | "low",
  "follow_up_suggestions": ["...", "...", "..."]
}
```

### GET /query/history?limit=20
Data: `{ "queries": [ { "query_id", "query", "answer", "confidence", "created_at" } ] }`

### POST /query/feedback
Body: `{ "query_id": str, "rating": 1 | -1, "comment"?: str }` → Data: `{ "ok": true }`

## Equipment

### GET /equipment
Data: `{ "equipment": [ { "equipment_id": "P-101", "name", "type", "location", "department", "health_score": 0-100, "status": "healthy"|"warning"|"critical", "last_serviced", "next_due", "open_alerts_count" } ] }`

### GET /equipment/{id}
Data: single object as above plus `{ "manufacturer", "model", "installed_on", "description" }`

### GET /equipment/{id}/history
Data: `{ "events": [ { "event_id", "date", "event_type": "failure"|"repair"|"inspection"|"pm", "title", "description", "work_order", "document" } ] }` (newest first)

### GET /equipment/{id}/alerts
Data: `{ "alerts": [alert objects, see /alerts] }`

### GET /equipment/{id}/documents
Data: `{ "documents": [ { "doc_id", "name", "doc_type", "uploaded_at" } ] }`

### GET /equipment/{id}/rca?symptom=high+vibration
Data: `{ "symptom", "probable_causes": [ { "cause", "likelihood": "high"|"medium"|"low", "evidence": str, "recommended_action": str } ], "sources": [source objects] }`

## Compliance

### GET /compliance/matrix
Data: `{ "regulations": [str], "departments": [str], "cells": [ { "regulation", "department", "status": "compliant"|"gap"|"partial"|"expiring"|"not_assessed", "gap_count" } ], "overall_score": 0-100 }`

### GET /compliance/gaps
Data: `{ "gaps": [ { "gap_id", "regulation", "requirement", "department", "severity": "high"|"medium"|"low", "what_is_missing", "recommended_action" } ] }`

### POST /compliance/scan
Body: `{ "department"?: str }` → Data: `{ "scan_job_id", "status": "queued" }`

### GET /compliance/expiring?days=60
Data: `{ "certifications": [ { "cert_id", "name", "expiry_date", "days_remaining", "department", "status": "expiring"|"expired" } ] }`

## Alerts

### GET /alerts
Data: `{ "alerts": [ { "alert_id", "equipment_id", "severity": "critical"|"warning"|"info", "title", "description", "triggered_at", "status": "open"|"acknowledged", "recommended_action" } ] }`

### GET /alerts/{id}
Data: alert object plus `{ "ai_explanation": str, "similar_past_incidents": [ { "incident_id", "title", "date", "outcome" } ] }`

### POST /alerts/{id}/acknowledge
Body: `{ "notes"?: str }` → Data: `{ "alert_id", "status": "acknowledged", "acknowledged_at" }`

### GET /alerts/patterns
Data: `{ "patterns": [ { "pattern_id", "equipment_id", "title", "description", "frequency", "risk_level": "high"|"medium"|"low", "evidence": [str], "recommended_action" } ] }`

### GET /alerts/warnings
Data: `{ "warnings": [ { "warning_id", "title", "matching_factors": [str], "past_outcome": str, "recommended_action": str, "urgency": "high"|"medium", "reference": str } ] }`

## Documents

### GET /documents?doc_type=&equipment_id=
Data: `{ "documents": [ { "doc_id", "name", "doc_type", "equipment_tags": [str], "department", "uploaded_at", "chunk_count", "processing_status": "indexed"|"processing"|"failed" } ] }`

### GET /documents/{id}
Data: document object plus `{ "entities": { "equipment_ids": [], "dates": [], "parameters": [], "regulations": [], "people": [] } }`

### GET /documents/{id}/download
Returns the raw file (binary response, not the envelope).

## Incidents & Lessons

### POST /incidents/report
Body: `{ "equipment_id", "description", "severity": "high"|"medium"|"low", "incident_type": "incident"|"near-miss" }`
Data: `{ "incident_id", "status": "reported" }`

### GET /incidents
Data: `{ "incidents": [ { "incident_id", "equipment_id", "title", "description", "severity", "incident_type", "date", "status" } ] }`

### GET /incidents/{id}/similar
Data: `{ "similar_incidents": [ { "incident_id", "title", "similarity_score": 0-1, "outcome", "resolution" } ] }`

### GET /lessons-learned
Data: `{ "cards": [ { "card_id", "title", "equipment_type", "what_happened", "root_cause", "what_was_done", "watch_for" } ] }`

## Analytics

### GET /analytics/knowledge-gaps
Data: `{ "unanswered_queries": [ { "query", "frequency", "avg_confidence", "suggested_document": str } ] }`

### GET /analytics/overview
Data: `{ "kpis": { "documents_indexed": int, "queries_this_week": int, "avg_confidence": int, "open_alerts": int, "compliance_score": int, "equipment_healthy_pct": int }, "query_volume": [ { "date", "count" } ], "top_topics": [ { "topic", "count" } ] }`
