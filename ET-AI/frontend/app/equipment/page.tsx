"use client";

import { useState } from "react";
import AppShell from "@/components/AppShell";
import EquipmentCard from "@/components/EquipmentCard";
import { useApi } from "@/lib/api";
import type { Equipment } from "@/lib/types";
import { ErrorBanner, SkeletonCards } from "@/components/ui";

export default function EquipmentPage() {
  const { data, loading, error, reload } =
    useApi<{ equipment: Equipment[] }>("/equipment");
  const [search, setSearch] = useState("");

  const filtered = (data?.equipment ?? []).filter((eq) => {
    const q = search.toLowerCase();
    return (
      eq.equipment_id.toLowerCase().includes(q) ||
      eq.name.toLowerCase().includes(q) ||
      eq.type.toLowerCase().includes(q)
    );
  });

  return (
    <AppShell>
      <div className="page-title">Equipment</div>
      <div className="page-subtitle">
        Health scores computed by the Maintenance Intelligence Agent from
        service history, failures and open alerts.
      </div>

      <div className="mb-16" style={{ maxWidth: 360 }}>
        <input
          className="input"
          placeholder="Search by ID, name or type…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {loading && <SkeletonCards count={8} />}
      {error && <ErrorBanner error={error} onRetry={reload} />}
      {data && (
        <div className="grid-2">
          {filtered.map((eq) => (
            <EquipmentCard key={eq.equipment_id} eq={eq} />
          ))}
          {filtered.length === 0 && (
            <div className="card muted">No equipment matches “{search}”.</div>
          )}
        </div>
      )}
    </AppShell>
  );
}
