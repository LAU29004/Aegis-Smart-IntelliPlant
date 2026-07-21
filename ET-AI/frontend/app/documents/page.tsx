"use client";

import { useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import { api, ApiError, useApi } from "@/lib/api";
import { docTypeLabel, formatDate } from "@/lib/format";
import type {
  DocumentDetail,
  DocumentItem,
  IngestStatus,
  UploadResponse,
} from "@/lib/types";
import { Badge, ErrorBanner, Skeleton, StatusBadge } from "@/components/ui";

export default function DocumentsPage() {
  const docs = useApi<{ documents: DocumentItem[] }>("/documents");
  const [files, setFiles] = useState<FileList | null>(null);
  const [docType, setDocType] = useState("maintenance_log");
  const [equipmentId, setEquipmentId] = useState("");
  const [job, setJob] = useState<IngestStatus | null>(null);
  const [uploadError, setUploadError] = useState<ApiError | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState<DocumentDetail | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  async function upload() {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadError(null);
    setJob(null);
    const fd = new FormData();
    Array.from(files).forEach((f) => fd.append("files", f));
    fd.append("doc_type", docType);
    fd.append("equipment_id", equipmentId);
    try {
      const res = await api.upload<UploadResponse>("/ingest/upload", fd);
      poll(res.job_id);
    } catch (e) {
      setUploadError(e instanceof ApiError ? e : new ApiError("Upload failed"));
      setUploading(false);
    }
  }

  function poll(jobId: string) {
    pollRef.current = setInterval(async () => {
      try {
        const st = await api.get<IngestStatus>(`/ingest/status/${jobId}`);
        setJob(st);
        if (st.status === "completed" || st.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          setUploading(false);
          setFiles(null);
          if (fileRef.current) fileRef.current.value = "";
          docs.reload();
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current);
        setUploading(false);
      }
    }, 2000);
  }

  async function openDetails(docId: string) {
    try {
      setSelected(await api.get<DocumentDetail>(`/documents/${docId}`));
    } catch {
      /* ignore */
    }
  }

  return (
    <AppShell>
      <div className="page-title">Document Library</div>
      <div className="page-subtitle">
        Upload anything — PDFs, logs, SOPs, spreadsheets. IntelliPlant parses,
        extracts entities and indexes it for search.
      </div>

      <div className="card mb-16">
        <div className="card-title">Upload documents</div>
        <div className="form-row">
          <div className="field" style={{ flex: 2 }}>
            <label>Files (PDF, TXT, MD, XLSX, CSV)</label>
            <input
              ref={fileRef}
              className="input"
              type="file"
              multiple
              accept=".pdf,.txt,.md,.xlsx,.csv,.log"
              onChange={(e) => setFiles(e.target.files)}
            />
          </div>
          <div className="field">
            <label>Document type</label>
            <select
              className="select"
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
            >
              <option value="manual">Manual</option>
              <option value="maintenance_log">Maintenance Log</option>
              <option value="sop">SOP</option>
              <option value="inspection">Inspection</option>
              <option value="incident">Incident</option>
              <option value="regulation">Regulation</option>
              <option value="certificate">Certificate</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div className="field">
            <label>Equipment ID (optional)</label>
            <input
              className="input"
              placeholder="e.g. P-101"
              value={equipmentId}
              onChange={(e) => setEquipmentId(e.target.value)}
            />
          </div>
          <div className="field" style={{ justifyContent: "flex-end" }}>
            <label>&nbsp;</label>
            <button
              className="btn btn-primary"
              onClick={upload}
              disabled={uploading || !files || files.length === 0}
            >
              {uploading ? "Processing…" : "Upload & Index"}
            </button>
          </div>
        </div>
        {uploadError && (
          <div className="mt-8">
            <ErrorBanner error={uploadError} />
          </div>
        )}
        {job && (
          <div className="mt-16">
            <div className="spread small" style={{ marginBottom: 6 }}>
              <span className="muted">
                Job <span className="mono">{job.job_id}</span> — {job.status}
                {job.error_message ? ` · ${job.error_message}` : ""}
              </span>
              <span className="muted">{job.progress}%</span>
            </div>
            <div className="progress-track">
              <div
                className={`progress-fill ${job.status}`}
                style={{ width: `${job.progress}%` }}
              />
            </div>
            {job.status === "completed" && (
              <div className="small text-green mt-8">
                ✓ Indexed — the new content is immediately queryable in Copilot.
              </div>
            )}
          </div>
        )}
      </div>

      <div className="section-title">Indexed documents</div>
      {docs.loading && <Skeleton height={220} />}
      {docs.error && <ErrorBanner error={docs.error} onRetry={docs.reload} />}
      {docs.data && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Equipment</th>
                <th>Department</th>
                <th>Uploaded</th>
                <th>Chunks</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {docs.data.documents.map((d) => (
                <tr
                  key={d.doc_id}
                  className="clickable"
                  onClick={() => openDetails(d.doc_id)}
                >
                  <td style={{ fontWeight: 600 }}>{d.name}</td>
                  <td>
                    <Badge tone="blue">{docTypeLabel(d.doc_type)}</Badge>
                  </td>
                  <td className="mono small">
                    {d.equipment_tags.slice(0, 3).join(", ") || "—"}
                  </td>
                  <td>{d.department || "—"}</td>
                  <td>{formatDate(d.uploaded_at)}</td>
                  <td>{d.chunk_count}</td>
                  <td>
                    <StatusBadge status={d.processing_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <>
          <div className="drawer-overlay" onClick={() => setSelected(null)} />
          <div className="drawer">
            <button className="drawer-close" onClick={() => setSelected(null)}>
              ✕
            </button>
            <div className="card-title">{selected.name}</div>
            <div className="row mb-16">
              <Badge tone="blue">{docTypeLabel(selected.doc_type)}</Badge>
              <StatusBadge status={selected.processing_status} />
              <span className="small muted">
                {selected.chunk_count} chunks
              </span>
            </div>
            {(
              [
                ["Equipment IDs", selected.entities.equipment_ids],
                ["Dates", selected.entities.dates],
                ["Parameters", selected.entities.parameters],
                ["Regulations", selected.entities.regulations],
                ["People", selected.entities.people],
              ] as [string, string[]][]
            ).map(([label, items]) => (
              <div key={label}>
                <div className="detail-section-label">{label}</div>
                <div className="row">
                  {items && items.length > 0 ? (
                    items.map((it) => (
                      <Badge key={it} tone="gray">
                        {it}
                      </Badge>
                    ))
                  ) : (
                    <span className="small faint">none detected</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </AppShell>
  );
}
