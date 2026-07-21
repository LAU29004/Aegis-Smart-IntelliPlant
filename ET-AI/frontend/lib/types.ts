// ---- Shared API types (mirrors docs/API_CONTRACT.md) ----

export interface User {
  user_id: string;
  name: string;
  email: string;
  role: string;
  plant_id: string;
  department: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// Ingestion
export interface UploadResponse {
  job_id: string;
  status: string;
  files: string[];
}

export interface IngestStatus {
  job_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  progress: number;
  error_message: string | null;
  doc_ids: string[];
}

// Query / Copilot
export interface Source {
  doc_id: string;
  document: string;
  page: number;
  chunk_id: string;
  snippet: string;
}

export interface AskResponse {
  query_id: string;
  answer: string;
  sources: Source[];
  confidence: number;
  confidence_level: "high" | "medium" | "low";
  follow_up_suggestions: string[];
}

export interface QueryHistoryItem {
  query_id: string;
  query: string;
  answer: string;
  confidence: number;
  created_at: string;
}

// Equipment
export interface Equipment {
  equipment_id: string;
  name: string;
  type: string;
  location: string;
  department: string;
  health_score: number;
  status: "healthy" | "warning" | "critical";
  last_serviced: string;
  next_due: string;
  open_alerts_count: number;
}

export interface EquipmentDetail extends Equipment {
  manufacturer: string;
  model: string;
  installed_on: string;
  description: string;
}

export interface HistoryEvent {
  event_id: string;
  date: string;
  event_type: "failure" | "repair" | "inspection" | "pm";
  title: string;
  description: string;
  work_order: string;
  document: string;
}

export interface ProbableCause {
  cause: string;
  likelihood: "high" | "medium" | "low";
  evidence: string;
  recommended_action: string;
}

export interface RcaResponse {
  symptom: string;
  probable_causes: ProbableCause[];
  sources: Source[];
}

// Compliance
export interface ComplianceCell {
  regulation: string;
  department: string;
  status: "compliant" | "gap" | "partial" | "expiring" | "not_assessed";
  gap_count: number;
}

export interface ComplianceMatrix {
  regulations: string[];
  departments: string[];
  cells: ComplianceCell[];
  overall_score: number;
}

export interface ComplianceGap {
  gap_id: string;
  regulation: string;
  requirement: string;
  department: string;
  severity: "high" | "medium" | "low";
  what_is_missing: string;
  recommended_action: string;
}

export interface Certification {
  cert_id: string;
  name: string;
  expiry_date: string;
  days_remaining: number;
  department: string;
  status: "expiring" | "expired";
}

// Alerts
export interface Alert {
  alert_id: string;
  equipment_id: string;
  severity: "critical" | "warning" | "info";
  title: string;
  description: string;
  triggered_at: string;
  status: "open" | "acknowledged";
  recommended_action: string;
}

export interface Warning {
  warning_id: string;
  title: string;
  matching_factors: string[];
  past_outcome: string;
  recommended_action: string;
  urgency: "high" | "medium";
  reference: string;
}

// Documents
export interface DocumentItem {
  doc_id: string;
  name: string;
  doc_type: string;
  equipment_tags: string[];
  department: string;
  uploaded_at: string;
  chunk_count: number;
  processing_status: "indexed" | "processing" | "failed";
}

export interface DocumentDetail extends DocumentItem {
  entities: {
    equipment_ids: string[];
    dates: string[];
    parameters: string[];
    regulations: string[];
    people: string[];
  };
}

// Incidents & lessons
export interface Incident {
  incident_id: string;
  equipment_id: string;
  title: string;
  description: string;
  severity: "high" | "medium" | "low";
  incident_type: "incident" | "near-miss";
  date: string;
  status: string;
}

export interface LessonCard {
  card_id: string;
  title: string;
  equipment_type: string;
  what_happened: string;
  root_cause: string;
  what_was_done: string;
  watch_for: string;
}

// Analytics
export interface KnowledgeGap {
  query: string;
  frequency: number;
  avg_confidence: number;
  suggested_document: string;
}

export interface AnalyticsOverview {
  kpis: {
    documents_indexed: number;
    queries_this_week: number;
    avg_confidence: number;
    open_alerts: number;
    compliance_score: number;
    equipment_healthy_pct: number;
  };
  query_volume: { date: string; count: number }[];
  top_topics: { topic: string; count: number }[];
}
