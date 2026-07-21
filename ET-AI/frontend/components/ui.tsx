"use client";

import { ApiError, BACKEND_DOWN_MESSAGE } from "@/lib/api";

// ---------- Badges ----------

type Tone = "green" | "amber" | "red" | "blue" | "gray";

export function Badge({
  tone,
  children,
  dot = false,
}: {
  tone: Tone;
  children: React.ReactNode;
  dot?: boolean;
}) {
  return (
    <span className={`badge badge-${tone}`}>
      {dot && <span className="dot" />}
      {children}
    </span>
  );
}

export function statusTone(status: string): Tone {
  switch (status) {
    case "healthy":
    case "compliant":
    case "indexed":
    case "completed":
    case "resolved":
      return "green";
    case "warning":
    case "partial":
    case "expiring":
    case "medium":
    case "processing":
    case "queued":
      return "amber";
    case "critical":
    case "gap":
    case "high":
    case "failed":
    case "failure":
    case "expired":
      return "red";
    case "info":
    case "low":
    case "open":
    case "reported":
      return "blue";
    default:
      return "gray";
  }
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={statusTone(status)} dot>
      {status.replace(/_/g, " ")}
    </Badge>
  );
}

export function confidenceTone(confidence: number): Tone {
  if (confidence >= 80) return "green";
  if (confidence >= 60) return "amber";
  return "red";
}

export function ConfidenceBadge({
  confidence,
  level,
}: {
  confidence: number;
  level?: string;
}) {
  const label =
    level ??
    (confidence >= 80 ? "High" : confidence >= 60 ? "Medium" : "Low");
  return (
    <Badge tone={confidenceTone(confidence)} dot>
      {confidence}%{" "}
      {label.charAt(0).toUpperCase() + label.slice(1).toLowerCase()}
    </Badge>
  );
}

// ---------- Stat card ----------

export function StatCard({
  label,
  value,
  unit,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  unit?: string;
  tone?: Tone;
}) {
  const color =
    tone === "green"
      ? "var(--green)"
      : tone === "amber"
        ? "var(--amber)"
        : tone === "red"
          ? "var(--red)"
          : tone === "blue"
            ? "var(--accent)"
            : undefined;
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={color ? { color } : undefined}>
        {value}
        {unit && <span className="stat-unit">{unit}</span>}
      </div>
    </div>
  );
}

// ---------- Loading ----------

export function Spinner() {
  return <span className="spinner" aria-label="Loading" />;
}

export function Skeleton({
  height = 16,
  width = "100%",
  style,
}: {
  height?: number;
  width?: number | string;
  style?: React.CSSProperties;
}) {
  return <div className="skeleton" style={{ height, width, ...style }} />;
}

export function SkeletonCards({ count = 3, height = 90 }: { count?: number; height?: number }) {
  return (
    <div className="grid-3">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} height={height} />
      ))}
    </div>
  );
}

// ---------- Errors ----------

export function ErrorBanner({
  error,
  onRetry,
}: {
  error: ApiError | Error | string;
  onRetry?: () => void;
}) {
  const isDown =
    error instanceof ApiError
      ? error.backendDown
      : typeof error === "string"
        ? error === BACKEND_DOWN_MESSAGE
        : false;
  const message = typeof error === "string" ? error : error.message;

  if (isDown) {
    return (
      <div className="error-banner">
        <span style={{ fontSize: 18 }}>&#9888;</span>
        <span>
          Backend not running — start it with <code>uvicorn app.main:app</code>
        </span>
        {onRetry && (
          <button className="btn btn-sm" onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
    );
  }
  return (
    <div className="error-banner hard">
      <span style={{ fontSize: 18 }}>&#10060;</span>
      <span>{message}</span>
      {onRetry && (
        <button className="btn btn-sm" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

// ---------- Health ring ----------

export function HealthRing({
  score,
  size = "sm",
}: {
  score: number;
  size?: "sm" | "lg";
}) {
  const color =
    score >= 80 ? "var(--green)" : score >= 60 ? "var(--amber)" : "var(--red)";
  const px = size === "lg" ? 84 : 56;
  const stroke = size === "lg" ? 7 : 5;
  const r = (px - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, score));
  return (
    <div className={`health-ring ${size === "lg" ? "lg" : ""}`}>
      <svg width={px} height={px}>
        <circle
          cx={px / 2}
          cy={px / 2}
          r={r}
          fill="none"
          stroke="var(--surface-3)"
          strokeWidth={stroke}
        />
        <circle
          cx={px / 2}
          cy={px / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - clamped / 100)}
        />
      </svg>
      <div className="ring-label" style={{ color }}>
        {clamped}
      </div>
    </div>
  );
}

// ---------- Toast ----------

export function Toast({
  message,
  kind = "success",
}: {
  message: string;
  kind?: "success" | "error";
}) {
  return <div className={`toast ${kind === "error" ? "error" : ""}`}>{message}</div>;
}
