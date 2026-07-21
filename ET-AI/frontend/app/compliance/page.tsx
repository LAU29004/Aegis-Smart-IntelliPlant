"use client";

import { useState } from "react";
import AppShell from "@/components/AppShell";
import { api, useApi } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type {
  Certification,
  ComplianceGap,
  ComplianceMatrix,
} from "@/lib/types";
import {
  Badge,
  ErrorBanner,
  Skeleton,
  StatCard,
  Toast,
} from "@/components/ui";

const CELL_LABEL: Record<string, string> = {
  compliant: "✓",
  gap: "✗",
  partial: "◐",
  expiring: "⏳",
  not_assessed: "—",
};

export default function CompliancePage() {
  const matrix = useApi<ComplianceMatrix>("/compliance/matrix");
  const gaps = useApi<{ gaps: ComplianceGap[] }>("/compliance/gaps");
  const expiring = useApi<{ certifications: Certification[] }>(
    "/compliance/expiring?days=60"
  );
  const [toast, setToast] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);

  async function runScan() {
    setScanning(true);
    try {
      const res = await api.post<{ gaps_found: number }>("/compliance/scan", {});
      setToast(
        `Compliance scan complete — ${res.gaps_found} new gap${
          res.gaps_found === 1 ? "" : "s"
        } detected.`
      );
      matrix.reload();
      gaps.reload();
    } catch {
      setToast("Scan failed — is the backend running?");
    } finally {
      setScanning(false);
      setTimeout(() => setToast(null), 4000);
    }
  }

  const m = matrix.data;

  return (
    <AppShell>
      <div className="spread">
        <div>
          <div className="page-title">Compliance Dashboard</div>
          <div className="page-subtitle">
            Regulation requirements mapped against indexed SOPs by the
            Compliance Intelligence Agent.
          </div>
        </div>
        <button className="btn btn-primary" onClick={runScan} disabled={scanning}>
          {scanning ? "Scanning…" : "▶ Run Compliance Scan"}
        </button>
      </div>

      {matrix.error && (
        <ErrorBanner error={matrix.error} onRetry={matrix.reload} />
      )}
      {matrix.loading && <Skeleton height={220} />}

      {m && (
        <>
          <div className="kpi-row" style={{ maxWidth: 480 }}>
            <StatCard
              label="Overall Compliance"
              value={m.overall_score}
              unit="%"
              tone={
                m.overall_score >= 80
                  ? "green"
                  : m.overall_score >= 60
                    ? "amber"
                    : "red"
              }
            />
            <StatCard
              label="Open Gaps"
              value={gaps.data?.gaps.length ?? "—"}
              tone="red"
            />
            <StatCard
              label="Expiring ≤60d"
              value={expiring.data?.certifications.length ?? "—"}
              tone="amber"
            />
          </div>

          <div className="section-title">Regulation × Department matrix</div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Regulation</th>
                  {m.departments.map((d) => (
                    <th key={d} style={{ textAlign: "center" }}>
                      {d}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {m.regulations.map((reg) => (
                  <tr key={reg}>
                    <td style={{ fontWeight: 600 }}>{reg}</td>
                    {m.departments.map((dept) => {
                      const cell = m.cells.find(
                        (c) => c.regulation === reg && c.department === dept
                      );
                      const status = cell?.status ?? "not_assessed";
                      return (
                        <td key={dept}>
                          <div
                            className={`matrix-cell cell-${status}`}
                            title={`${reg} / ${dept}: ${status.replace("_", " ")}`}
                          >
                            {CELL_LABEL[status]}
                            {cell && cell.gap_count > 0
                              ? ` ${cell.gap_count}`
                              : ""}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="row small muted mt-8">
            <span>✓ compliant</span>
            <span>✗ gap (count)</span>
            <span>⏳ expiring</span>
            <span>— not assessed</span>
          </div>
        </>
      )}

      <div className="section-title">Detected gaps</div>
      {gaps.loading && <Skeleton height={120} />}
      {gaps.error && <ErrorBanner error={gaps.error} onRetry={gaps.reload} />}
      {gaps.data && (
        <div className="stack">
          {gaps.data.gaps.map((g) => (
            <div key={g.gap_id} className="card">
              <div className="row">
                <Badge
                  tone={
                    g.severity === "high"
                      ? "red"
                      : g.severity === "medium"
                        ? "amber"
                        : "gray"
                  }
                >
                  {g.severity}
                </Badge>
                <strong>{g.regulation}</strong>
                <Badge tone="gray">{g.department}</Badge>
              </div>
              <div className="small mt-8">
                <strong>Requirement:</strong> {g.requirement}
              </div>
              <div className="small muted mt-8">
                <strong>Missing:</strong> {g.what_is_missing}
              </div>
              <div className="small mt-8 text-amber">
                <strong>Action:</strong> {g.recommended_action}
              </div>
            </div>
          ))}
          {gaps.data.gaps.length === 0 && (
            <div className="card muted">No gaps detected. ✓</div>
          )}
        </div>
      )}

      <div className="section-title">Certifications expiring within 60 days</div>
      {expiring.loading && <Skeleton height={100} />}
      {expiring.error && (
        <ErrorBanner error={expiring.error} onRetry={expiring.reload} />
      )}
      {expiring.data && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Certification</th>
                <th>Expiry date</th>
                <th>Days remaining</th>
                <th>Department</th>
              </tr>
            </thead>
            <tbody>
              {expiring.data.certifications.map((c) => (
                <tr key={c.cert_id}>
                  <td style={{ fontWeight: 600 }}>{c.name}</td>
                  <td>{formatDate(c.expiry_date)}</td>
                  <td
                    className={
                      c.days_remaining < 0
                        ? "text-red"
                        : c.days_remaining < 30
                          ? "text-red"
                          : "text-amber"
                    }
                    style={{ fontWeight: 700 }}
                  >
                    {c.days_remaining < 0
                      ? `EXPIRED ${-c.days_remaining}d ago`
                      : `${c.days_remaining}d`}
                  </td>
                  <td>{c.department}</td>
                </tr>
              ))}
              {expiring.data.certifications.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">
                    Nothing expiring in the next 60 days.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {toast && <Toast message={toast} />}
    </AppShell>
  );
}
