"use client";

import Link from "next/link";
import AppShell from "@/components/AppShell";
import EquipmentCard from "@/components/EquipmentCard";
import { useApi } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import type { Alert, AnalyticsOverview, Equipment } from "@/lib/types";
import {
  ErrorBanner,
  SkeletonCards,
  StatCard,
  StatusBadge,
} from "@/components/ui";

export default function DashboardPage() {
  const overview = useApi<AnalyticsOverview>("/analytics/overview");
  const equipment = useApi<{ equipment: Equipment[] }>("/equipment");
  const alerts = useApi<{ alerts: Alert[] }>("/alerts?status=open");

  const kpis = overview.data?.kpis;

  return (
    <AppShell>
      <div className="page-title">Plant Dashboard</div>
      <div className="page-subtitle">
        PLANT-01 · live knowledge, health and compliance overview
      </div>

      {overview.error && (
        <div className="mb-16">
          <ErrorBanner error={overview.error} onRetry={overview.reload} />
        </div>
      )}

      <div className="kpi-row">
        <StatCard label="Documents Indexed" value={kpis?.documents_indexed ?? "—"} />
        <StatCard label="Queries This Week" value={kpis?.queries_this_week ?? "—"} />
        <StatCard
          label="Avg Confidence"
          value={kpis?.avg_confidence ?? "—"}
          unit="%"
          tone={
            kpis ? (kpis.avg_confidence >= 80 ? "green" : "amber") : undefined
          }
        />
        <StatCard
          label="Open Alerts"
          value={kpis?.open_alerts ?? "—"}
          tone={kpis && kpis.open_alerts > 0 ? "red" : "green"}
        />
        <StatCard
          label="Compliance Score"
          value={kpis?.compliance_score ?? "—"}
          unit="%"
          tone={
            kpis
              ? kpis.compliance_score >= 80
                ? "green"
                : kpis.compliance_score >= 60
                  ? "amber"
                  : "red"
              : undefined
          }
        />
        <StatCard
          label="Equipment Healthy"
          value={kpis?.equipment_healthy_pct ?? "—"}
          unit="%"
        />
      </div>

      <div className="dash-columns">
        <section>
          <div className="section-title">Equipment Health</div>
          {equipment.loading && <SkeletonCards count={6} />}
          {equipment.error && (
            <ErrorBanner error={equipment.error} onRetry={equipment.reload} />
          )}
          {equipment.data && (
            <div className="grid-2">
              {equipment.data.equipment.map((eq) => (
                <EquipmentCard key={eq.equipment_id} eq={eq} />
              ))}
            </div>
          )}
        </section>

        <section>
          <div className="section-title">Active Alerts</div>
          {alerts.loading && <SkeletonCards count={4} height={64} />}
          {alerts.error && (
            <ErrorBanner error={alerts.error} onRetry={alerts.reload} />
          )}
          {alerts.data && (
            <div className="stack">
              {alerts.data.alerts.length === 0 && (
                <div className="card muted">No open alerts. 🎉</div>
              )}
              {alerts.data.alerts.map((a) => (
                <Link
                  key={a.alert_id}
                  href={`/incidents?alert=${a.alert_id}`}
                  style={{ color: "inherit" }}
                >
                  <div className={`alert-item sev-${a.severity}`}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="alert-title">{a.title}</div>
                      <div className="alert-sub">
                        <span className="mono">{a.equipment_id}</span> ·{" "}
                        {timeAgo(a.triggered_at)}
                      </div>
                    </div>
                    <StatusBadge status={a.severity} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
