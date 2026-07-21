"use client";

import { useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import Markdown from "@/components/Markdown";
import { api, ApiError } from "@/lib/api";
import type { AskResponse } from "@/lib/types";
import { ConfidenceBadge, ErrorBanner } from "@/components/ui";

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  meta?: AskResponse;
}

const STARTERS = [
  "What failed on Pump P-101 last month and how was it fixed?",
  "Boiler B-02 safe shutdown procedure",
  "Show all bearing failures on P-101",
  "Which certifications expire in the next 60 days?",
];

export default function CopilotPage() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [equipmentFilter, setEquipmentFilter] = useState("");
  const [docTypeFilter, setDocTypeFilter] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, busy]);

  async function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    setInput("");
    setError(null);
    const next: ChatMsg[] = [...messages, { role: "user" as const, content: q }];
    setMessages(next);
    setBusy(true);
    try {
      const res = await api.post<AskResponse>("/query/ask", {
        query: q,
        conversation_history: next
          .slice(-10)
          .map((m) => ({ role: m.role, content: m.content })),
        filters: {
          ...(equipmentFilter ? { equipment_id: equipmentFilter } : {}),
          ...(docTypeFilter ? { doc_type: docTypeFilter } : {}),
        },
      });
      setMessages((cur) => [
        ...cur,
        { role: "assistant", content: res.answer, meta: res },
      ]);
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("Query failed"));
      setMessages((cur) => cur.slice(0, -1));
      setInput(q);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <div className="page-title">Copilot</div>
      <div className="page-subtitle">
        Ask any question about any equipment or procedure — answers with source
        citations in seconds.
      </div>

      <div className="chat-shell">
        <div className="chat-filters">
          <span>Filters:</span>
          <input
            className="input"
            placeholder="Equipment ID (e.g. P-101)"
            value={equipmentFilter}
            onChange={(e) => setEquipmentFilter(e.target.value)}
          />
          <select
            className="select"
            value={docTypeFilter}
            onChange={(e) => setDocTypeFilter(e.target.value)}
          >
            <option value="">All document types</option>
            <option value="manual">Manuals</option>
            <option value="maintenance_log">Maintenance logs</option>
            <option value="sop">SOPs</option>
            <option value="inspection">Inspections</option>
            <option value="incident">Incidents</option>
            <option value="regulation">Regulations</option>
          </select>
        </div>

        <div className="chat-scroll" ref={scrollRef}>
          {messages.length === 0 && (
            <div className="empty-hero">
              <div className="hero-icon">✦</div>
              <h2>Ask IntelliPlant anything</h2>
              <p>
                Every manual, log, SOP, inspection and incident report — one
                question away.
              </p>
              <div className="starter-grid">
                {STARTERS.map((s) => (
                  <button
                    key={s}
                    className="starter-card"
                    onClick={() => send(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`msg-row ${m.role}`}>
              <div className={`bubble ${m.role}`}>
                {m.role === "assistant" ? (
                  <>
                    <Markdown text={m.content} />
                    {m.meta && (
                      <>
                        <div className="msg-meta">
                          <ConfidenceBadge
                            confidence={m.meta.confidence}
                            level={m.meta.confidence_level}
                          />
                          {m.meta.sources.map((s) => (
                            <span
                              key={s.chunk_id}
                              className="source-chip"
                              title={s.snippet}
                            >
                              📄 {s.document} · p.{s.page}
                            </span>
                          ))}
                        </div>
                        {m.meta.confidence < 60 && (
                          <div
                            className="small text-amber"
                            style={{ marginTop: 6 }}
                          >
                            ⚠ Low confidence — verify with the source document.
                          </div>
                        )}
                        {i === messages.length - 1 &&
                          m.meta.follow_up_suggestions.length > 0 && (
                            <div className="followups">
                              {m.meta.follow_up_suggestions.map((f) => (
                                <button
                                  key={f}
                                  className="pill"
                                  onClick={() => send(f)}
                                >
                                  {f}
                                </button>
                              ))}
                            </div>
                          )}
                      </>
                    )}
                  </>
                ) : (
                  m.content
                )}
              </div>
            </div>
          ))}

          {busy && (
            <div className="msg-row">
              <div className="bubble assistant">
                <span className="typing-dots">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div style={{ paddingTop: 8 }}>
            <ErrorBanner error={error} />
          </div>
        )}

        <div className="chat-input-bar">
          <input
            className="input"
            placeholder="Ask about equipment, procedures, failures, compliance…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            disabled={busy}
          />
          <button
            className="btn btn-primary"
            onClick={() => send()}
            disabled={busy || !input.trim()}
          >
            Send ➤
          </button>
        </div>
      </div>
    </AppShell>
  );
}
