"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import AppShell from "@/components/AppShell";
import { api, ApiError, useApi } from "@/lib/api";
import { docTypeLabel, formatDate } from "@/lib/format";
import type {
  Alert,
  DocumentItem,
  EquipmentDetail,
  HistoryEvent,
  RcaResponse,
} from "@/lib/types";
import {
  Badge,
  ErrorBanner,
  HealthRing,
  Skeleton,
  StatusBadge,
} from "@/components/ui";

const EVENT_COLORS: Record<string, string> = {
  failure: "var(--red)",
  repair: "var(--accent)",
  inspection: "var(--amber)",
  pm: "var(--green)",
};

type Tab = "timeline" | "alerts" | "documents" | "rca";

export default function EquipmentDetailPage() {
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);
  const [tab, setTab] = useState<Tab>("timeline");

  const detail = useApi<EquipmentDetail>(`/equipment/${id}`);
  const history = useApi<{ events: HistoryEvent[] }>(`/equipment/${id}/history`);
  const alerts = useApi<{ alerts: Alert[] }>(`/equipment/${id}/alerts`);
  const docs = useApi<{ documents: DocumentItem[] }>(`/equipment/${id}/documents`);

  const [symptom, setSymptom] = useState("");
  const [rca, setRca] = useState<RcaResponse | null>(null);
  const [rcaBusy, setRcaBusy] = useState(false);
  const [rcaError, setRcaError] = useState<ApiError | null>(null);

  async function runRca() {
    if (!symptom.trim()) return;
    setRcaBusy(true);
    setRcaError(null);
    try {
      setRca(
        await api.get<RcaResponse>(
          `/equipment/${id}/rca?symptom=${encodeURIComponent(symptom)}`
        )
      );
    } catch (e) {
      setRcaError(e instanceof ApiError ? e : new ApiError("RCA failed"));
    } finally {
      setRcaBusy(false);
    }
  }

  const eq = detail.data;

  return (
    <AppShell>
      {detail.loading && <Skeleton height={120} />}
      {detail.error && (
        <ErrorBanner error={detail.error} onRetry={detail.reload} />
      )}
      {eq && (
        <div className="card">
          <div className="row" style={{ gap: 20 }}>
            <HealthRing score={eq.health_score} size="lg" />
            <div style={{ flex: 1, minWidth: 220 }}>
              <div className="row">
                <span className="page-title" style={{ marginBottom: 0 }}>
                  {eq.name}
                </span>
                <StatusBadge status={eq.status} />
              </div>
              <div className="muted small mt-8">
                <span className="mono">{eq.equipment_id}</span> · {eq.type} ·{" "}
                {eq.location} · {eq.manufacturer} {eq.model}
              </div>
              <div className="muted small">{eq.description}</div>
            </div>
            <dl className="kv" style={{ minWidth: 240 }}>
              <dt>Last serviced</dt>
              <dd>{formatDate(eq.last_serviced)}</dd>
              <dt>Next due</dt>
              <dd>{formatDate(eq.next_due)}</dd>
              <dt>Open alerts</dt>
              <dd
                className={eq.open_alerts_count > 0 ? "text-red" : "text-green"}
              >
                {eq.open_alerts_count}
              </dd>
            </dl>
          </div>
        </div>
      )}

      <div className="tabs">
        {(
          [
            ["timeline", "Timeline"],
            ["alerts", "Alerts"],
            ["documents", "Documents"],
            ["rca", "RCA Assistant"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            className={`tab ${tab === key ? "active" : ""}`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "timeline" && (
        <>
          {history.loading && <Skeleton height={200} />}
          {history.error && (
            <ErrorBanner error={history.error} onRetry={history.reload} />
          )}
          {history.data && (
            <div className="timeline">
              {history.data.events.map((ev) => (
                <div className="timeline-item" key={ev.event_id}>
                  <span
                    className="timeline-dot"
                    style={{
                      background: EVENT_COLORS[ev.event_type] ?? "var(--muted)",
                    }}
                  />
                  <div className="row">
                    <span className="timeline-title">{ev.title}</span>
                    <StatusBadge status={ev.event_type} />
                  </div>
                  <div className="timeline-date">{formatDate(ev.date)}</div>
                  {ev.description && (
                    <div className="timeline-desc">{ev.description}</div>
                  )}
                  <div className="timeline-refs">
                    {ev.work_order && (
                      <Badge tone="gray">{ev.work_order}</Badge>
                    )}
                    {ev.document && <Badge tone="blue">📄 {ev.document}</Badge>}
                  </div>
                </div>
              ))}
              {history.data.events.length === 0 && (
                <div className="muted">No maintenance history recorded.</div>
              )}
            </div>
          )}
        </>
      )}

      {tab === "alerts" && (
        <>
          {alerts.loading && <Skeleton height={120} />}
          {alerts.error && (
            <ErrorBanner error={alerts.error} onRetry={alerts.reload} />
          )}
          {alerts.data && (
            <div className="stack">
              {alerts.data.alerts.length === 0 && (
                <div className="card muted">No alerts for this equipment.</div>
              )}
              {alerts.data.alerts.map((a) => (
                <div key={a.alert_id} className={`alert-item sev-${a.severity}`}>
                  <div style={{ flex: 1 }}>
                    <div className="row">
                      <span className="alert-title">{a.title}</span>
                      <StatusBadge status={a.severity} />
                      <StatusBadge status={a.status} />
                    </div>
                    <div className="alert-sub">{a.description}</div>
                    {a.recommended_action && (
                      <div className="small mt-8">
                        <strong>Recommended:</strong> {a.recommended_action}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === "documents" && (
        <>
          {docs.loading && <Skeleton height={120} />}
          {docs.error && <ErrorBanner error={docs.error} onRetry={docs.reload} />}
          {docs.data && (
            <div className="grid-3">
              {docs.data.documents.map((d) => (
                <div key={d.doc_id} className="card">
                  <div className="card-title">📄 {d.name}</div>
                  <div className="row">
                    <Badge tone="blue">{docTypeLabel(d.doc_type)}</Badge>
                    <span className="small muted">
                      {formatDate(d.uploaded_at)}
                    </span>
                  </div>
                </div>
              ))}
              {docs.data.documents.length === 0 && (
                <div className="card muted">
                  No documents tagged to this equipment yet.
                </div>
              )}
            </div>
          )}
        </>
      )}

      {tab === "rca" && (
        <div>
          <div className="card mb-16">
            <div className="card-title">Root Cause Analysis Assistant</div>
            <div className="row">
              <input
                className="input"
                style={{ flex: 1, minWidth: 240 }}
                placeholder="Describe the symptom… e.g. high vibration on drive end"
                value={symptom}
                onChange={(e) => setSymptom(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && runRca()}
              />
              <button
                className="btn btn-primary"
                onClick={runRca}
                disabled={rcaBusy || !symptom.trim()}
              >
                {rcaBusy ? "Analysing…" : "Analyse"}
              </button>
            </div>
            {rcaError && (
              <div className="mt-8">
                <ErrorBanner error={rcaError} />
              </div>
            )}
          </div>

          {rca && (
            <>
              <div className="section-title">
                Probable causes for “{rca.symptom}”
              </div>
              <div className="stack">
                {rca.probable_causes.length === 0 && (
                  <div className="card muted">
                    No similar past failures found — try describing the symptom
                    differently.
                  </div>
                )}
                {rca.probable_causes.map((c, i) => (
                  <div key={i} className="card">
                    <div className="row">
                      <strong>
                        {i + 1}. {c.cause}
                      </strong>
                      <Badge
                        tone={
                          c.likelihood === "high"
                            ? "red"
                            : c.likelihood === "medium"
                              ? "amber"
                              : "gray"
                        }
                      >
                        {c.likelihood} likelihood
                      </Badge>
                    </div>
                    <div className="small muted mt-8">{c.evidence}</div>
                    <div className="small mt-8">
                      <strong>Action:</strong> {c.recommended_action}
                    </div>
                  </div>
                ))}
              </div>
              {rca.sources.length > 0 && (
                <div className="msg-meta mt-16">
                  {rca.sources.map((s) => (
                    <span key={s.chunk_id} className="source-chip" title={s.snippet}>
                      📄 {s.document} · p.{s.page}
                    </span>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </AppShell>
  );
}
