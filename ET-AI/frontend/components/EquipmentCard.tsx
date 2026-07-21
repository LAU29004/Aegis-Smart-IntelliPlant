"use client";

import Link from "next/link";
import type { Equipment } from "@/lib/types";
import { Badge, HealthRing, StatusBadge } from "./ui";

export default function EquipmentCard({ eq }: { eq: Equipment }) {
  return (
    <Link
      href={`/equipment/${encodeURIComponent(eq.equipment_id)}`}
      style={{ color: "inherit", display: "block" }}
    >
      <div className="card clickable equip-card">
        <HealthRing score={eq.health_score} />
        <div className="equip-meta">
          <div className="equip-id">{eq.equipment_id}</div>
          <div className="equip-name">{eq.name}</div>
          <div className="equip-sub">
            {eq.type} &middot; {eq.location}
          </div>
          <div className="equip-footer">
            <StatusBadge status={eq.status} />
            {eq.open_alerts_count > 0 && (
              <Badge tone={eq.open_alerts_count > 1 ? "red" : "amber"}>
                {eq.open_alerts_count} alert{eq.open_alerts_count > 1 ? "s" : ""}
              </Badge>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}
