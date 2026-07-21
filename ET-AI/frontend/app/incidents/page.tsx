"use client";

import { useState } from "react";
import AppShell from "@/components/AppShell";
import { api, useApi } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Equipment, Incident, LessonCard, Warning } from "@/lib/types";
import {
  Badge,
  ErrorBanner,
  Skeleton,
  StatusBadge,
  Toast,
} from "@/components/ui";

export default function IncidentsPage() {
  const incidents = useApi<{ incidents: Incident[] }>("/incidents");
  const lessons = useApi<{ cards: LessonCard[] }>("/lessons-learned");
  const warnings = useApi<{ warnings: Warning[] }>("/alerts/warnings");
  const equipment = useApi<{ equipment: Equipment[] }>("/equipment");

  const [equipmentId, setEquipmentId] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState("medium");
  const [incidentType, setIncidentType] = useState("incident");
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  async function submitReport(e: React.FormEvent) {
    e.preventDefault();
    if (!equipmentId || !description.trim()) return;
    setSubmitting(true);
    try {
      const res = await api.post<{ incident_id: string }>("/incidents/report", {
        equipment_id: equipmentId,
        description,
        severity,
        incident_type: incidentType,
      });
      setToast(`Reported as ${res.incident_id}`);
      setDescription("");
      incidents.reload();
    } catch {
      setToast("Failed to submit report");
    } finally {
      setSubmitting(false);
      setTimeout(() => setToast(null), 4000);
    }
  }

  return (
    <AppShell>
      <div className="page-title">Incidents & Lessons Learned</div>
      <div className="page-subtitle">
        The Failure Pattern Agent clusters incidents, extracts lessons and
        warns when today matches yesterday's disasters.
      </div>

      {warnings.data && warnings.data.warnings.length > 0 && (
        <div className="stack mb-16">
          {warnings.data.warnings.map((w) => (
            <div
              key={w.warning_id}
              className={`warning-banner ${w.urgency === "high" ? "high" : ""}`}
            >
              <div className="wb-title">⚠ PROACTIVE WARNING — {w.title}</div>
              <div className="wb-label">Matching factors</div>
              <ul>
                {w.matching_factors.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
              <div className="wb-label">Past outcome</div>
              <div className="small">{w.past_outcome}</div>
              <div className="wb-label">Recommended</div>
              <div className="small">
                <strong>{w.recommended_action}</strong>
                {w.reference && (
                  <span className="muted"> · {w.reference}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="dash-columns">
        <section>
          <div className="section-title">Incident log</div>
          {incidents.loading && <Skeleton height={160} />}
          {incidents.error && (
            <ErrorBanner error={incidents.error} onRetry={incidents.reload} />
          )}
          {incidents.data && (
            <div className="stack">
              {incidents.data.incidents.map((inc) => (
                <div key={inc.incident_id} className="card">
                  <div className="row">
                    <span className="mono small muted">{inc.incident_id}</span>
                    <Badge
                      tone={
                        inc.severity === "high"
                          ? "red"
                          : inc.severity === "medium"
                            ? "amber"
                            : "gray"
                      }
                    >
                      {inc.severity}
                    </Badge>
                    <Badge tone={inc.incident_type === "near-miss" ? "blue" : "gray"}>
                      {inc.incident_type}
                    </Badge>
                    <StatusBadge status={inc.status} />
                  </div>
                  <div className="card-title mt-8">{inc.title}</div>
                  <div className="small muted">{inc.description}</div>
                  <div className="small faint mt-8">
                    <span className="mono">{inc.equipment_id}</span> ·{" "}
                    {formatDate(inc.date)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section>
          <div className="section-title">Report an issue</div>
          <form className="card stack" onSubmit={submitReport}>
            <div className="field">
              <label>Equipment</label>
              <select
                className="select"
                value={equipmentId}
                onChange={(e) => setEquipmentId(e.target.value)}
                required
              >
                <option value="">Select equipment…</option>
                {(equipment.data?.equipment ?? []).map((eq) => (
                  <option key={eq.equipment_id} value={eq.equipment_id}>
                    {eq.equipment_id} — {eq.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>What happened?</label>
              <textarea
                className="textarea"
                placeholder="Describe the issue or near-miss…"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                required
              />
            </div>
            <div className="form-row">
              <div className="field">
                <label>Severity</label>
                <select
                  className="select"
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value)}
                >
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
              <div className="field">
                <label>Type</label>
                <select
                  className="select"
                  value={incidentType}
                  onChange={(e) => setIncidentType(e.target.value)}
                >
                  <option value="incident">Incident</option>
                  <option value="near-miss">Near-miss</option>
                </select>
              </div>
            </div>
            <button
              className="btn btn-primary"
              type="submit"
              disabled={submitting}
            >
              {submitting ? "Submitting…" : "Submit report"}
            </button>
          </form>
        </section>
      </div>

      <div className="section-title">Lessons learned</div>
      {lessons.loading && <Skeleton height={140} />}
      {lessons.error && (
        <ErrorBanner error={lessons.error} onRetry={lessons.reload} />
      )}
      {lessons.data && (
        <div className="grid-3">
          {lessons.data.cards.map((c) => (
            <div key={c.card_id} className="card">
              <div className="card-title">💡 {c.title}</div>
              <Badge tone="gray">{c.equipment_type}</Badge>
              {(
                [
                  ["What happened", c.what_happened],
                  ["Root cause", c.root_cause],
                  ["What was done", c.what_was_done],
                  ["Watch for", c.watch_for],
                ] as [string, string][]
              ).map(([label, text]) => (
                <div className="lesson-block" key={label}>
                  <div
                    className="lb-label"
                    style={{
                      color:
                        label === "Watch for" ? "var(--amber)" : "var(--muted)",
                    }}
                  >
                    {label}
                  </div>
                  <div className="lb-text small">{text}</div>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {toast && <Toast message={toast} />}
    </AppShell>
  );
}
