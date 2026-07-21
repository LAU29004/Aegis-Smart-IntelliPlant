"use client";

import AppShell from "@/components/AppShell";
import { useApi } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type {
  AnalyticsOverview,
  KnowledgeGap,
  QueryHistoryItem,
} from "@/lib/types";
import { ConfidenceBadge, ErrorBanner, Skeleton } from "@/components/ui";

export default function AnalyticsPage() {
  const overview = useApi<AnalyticsOverview>("/analytics/overview");
  const gaps = useApi<{ unanswered_queries: KnowledgeGap[] }>(
    "/analytics/knowledge-gaps"
  );
  const history = useApi<{ queries: QueryHistoryItem[] }>(
    "/query/history?limit=10"
  );

  const volume = overview.data?.query_volume ?? [];
  const maxCount = Math.max(1, ...volume.map((v) => v.count));
  const topics = overview.data?.top_topics ?? [];
  const maxTopic = Math.max(1, ...topics.map((t) => t.count));

  return (
    <AppShell>
      <div className="page-title">Analytics</div>
      <div className="page-subtitle">
        How the plant uses its knowledge — and where the knowledge base has
        gaps.
      </div>

      {overview.error && (
        <ErrorBanner error={overview.error} onRetry={overview.reload} />
      )}

      <div className="dash-columns">
        <section>
          <div className="section-title">Query volume — last 7 days</div>
          <div className="card">
            {overview.loading && <Skeleton height={160} />}
            {volume.length > 0 && (
              <div className="bar-chart">
                {volume.map((v) => (
                  <div className="bar-col" key={v.date}>
                    <span className="bar-value">{v.count}</span>
                    <div
                      className="bar"
                      style={{
                        height: `${Math.max(4, (v.count / maxCount) * 100)}%`,
                      }}
                      title={`${v.date}: ${v.count} queries`}
                    />
                    <span className="bar-label">{v.date.slice(5)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="section-title">
            Knowledge gaps — low-confidence queries
          </div>
          {gaps.loading && <Skeleton height={120} />}
          {gaps.error && <ErrorBanner error={gaps.error} onRetry={gaps.reload} />}
          {gaps.data && (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Query</th>
                    <th>Asked</th>
                    <th>Avg conf.</th>
                    <th>Suggestion</th>
                  </tr>
                </thead>
                <tbody>
                  {gaps.data.unanswered_queries.map((g) => (
                    <tr key={g.query}>
                      <td style={{ fontWeight: 600 }}>{g.query}</td>
                      <td>{g.frequency}×</td>
                      <td>
                        <ConfidenceBadge confidence={g.avg_confidence} />
                      </td>
                      <td className="small muted">{g.suggested_document}</td>
                    </tr>
                  ))}
                  {gaps.data.unanswered_queries.length === 0 && (
                    <tr>
                      <td colSpan={4} className="muted">
                        No knowledge gaps detected yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section>
          <div className="section-title">Most queried topics</div>
          <div className="card">
            {topics.map((t) => (
              <div className="topic-row" key={t.topic}>
                <span className="topic-name">{t.topic}</span>
                <div className="topic-bar-track">
                  <div
                    className="topic-bar-fill"
                    style={{ width: `${(t.count / maxTopic) * 100}%` }}
                  />
                </div>
                <span className="topic-count">{t.count}</span>
              </div>
            ))}
            {topics.length === 0 && (
              <span className="muted small">No queries logged yet.</span>
            )}
          </div>

          <div className="section-title">Your recent queries</div>
          {history.loading && <Skeleton height={120} />}
          {history.error && (
            <ErrorBanner error={history.error} onRetry={history.reload} />
          )}
          {history.data && (
            <div className="stack">
              {history.data.queries.map((q) => (
                <div key={q.query_id} className="card">
                  <div className="spread">
                    <strong className="small">{q.query}</strong>
                    <ConfidenceBadge confidence={Math.round(q.confidence)} />
                  </div>
                  <div className="small faint mt-8">
                    {formatDateTime(q.created_at)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
