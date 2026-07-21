import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Card, PageHeader, Screen, SectionTitle, Spread } from '../components/Layout';
import { ConfidenceBadge, ErrorBanner, Skeleton } from '../components/ui';
import { useApi } from '../lib/api';
import { formatDateTime } from '../lib/format';
import type { AnalyticsOverview, KnowledgeGap, QueryHistoryItem } from '../lib/types';
import { colors, radius, spacing, typography } from '../theme/colors';

export default function AnalyticsScreen() {
  const overview = useApi<AnalyticsOverview>('/analytics/overview');
  const gaps = useApi<{ unanswered_queries: KnowledgeGap[] }>('/analytics/knowledge-gaps');
  const history = useApi<{ queries: QueryHistoryItem[] }>('/query/history?limit=10');

  const volume = overview.data?.query_volume ?? [];
  const maxCount = Math.max(1, ...volume.map((v) => v.count));
  const topics = overview.data?.top_topics ?? [];
  const maxTopic = Math.max(1, ...topics.map((t) => t.count));

  return (
    <Screen>
      <PageHeader
        title="Analytics"
        subtitle="How the plant uses its knowledge — and where the knowledge base has gaps."
      />

      {overview.error && <ErrorBanner error={overview.error} onRetry={overview.reload} />}

      <SectionTitle>Query volume — last 7 days</SectionTitle>
      <Card>
        {overview.loading && <Skeleton height={160} />}
        {volume.length > 0 && (
          <View style={styles.barChart}>
            {volume.map((v) => {
              const isPeak = v.count === maxCount && maxCount > 0;
              return (
                <View key={v.date} style={styles.barCol}>
                  <Text style={[styles.barValue, isPeak && styles.barValuePeak]}>{v.count}</Text>
                  <View style={styles.barTrack}>
                    <View
                      style={[
                        styles.bar,
                        isPeak && styles.barPeak,
                        { height: `${Math.max(4, (v.count / maxCount) * 100)}%` },
                      ]}
                    />
                  </View>
                  <Text style={styles.barLabel}>{v.date.slice(5)}</Text>
                </View>
              );
            })}
          </View>
        )}
      </Card>

      <SectionTitle>Most queried topics</SectionTitle>
      <Card>
        {topics.map((t, i) => (
          <View key={t.topic} style={[styles.topicRow, i === topics.length - 1 && styles.topicRowLast]}>
            <Text style={styles.topicRank}>{i + 1}</Text>
            <Text style={styles.topicName} numberOfLines={1}>
              {t.topic}
            </Text>
            <View style={styles.topicTrack}>
              <View style={[styles.topicFill, { width: `${(t.count / maxTopic) * 100}%` }]} />
            </View>
            <Text style={styles.topicCount}>{t.count}</Text>
          </View>
        ))}
        {topics.length === 0 && <Text style={styles.muted}>No queries logged yet.</Text>}
      </Card>

      <SectionTitle>Knowledge gaps — low-confidence queries</SectionTitle>
      {gaps.loading && <Skeleton height={120} />}
      {gaps.error && <ErrorBanner error={gaps.error} onRetry={gaps.reload} />}
      {gaps.data?.unanswered_queries.map((g) => (
        <Card key={g.query} style={styles.gapCard}>
          <View style={styles.gapAccent} />
          <View style={styles.gapBody}>
            <Text style={styles.gapQuery}>{g.query}</Text>
            <Spread style={{ marginTop: spacing.sm }}>
              <Text style={styles.muted}>{g.frequency}× asked</Text>
              <ConfidenceBadge confidence={g.avg_confidence} />
            </Spread>
            <Text style={styles.suggestion}>Suggested: {g.suggested_document}</Text>
          </View>
        </Card>
      ))}
      {gaps.data?.unanswered_queries.length === 0 && (
        <Card>
          <Text style={styles.muted}>No knowledge gaps detected yet.</Text>
        </Card>
      )}

      <SectionTitle>Your recent queries</SectionTitle>
      {history.loading && <Skeleton height={120} />}
      {history.error && <ErrorBanner error={history.error} onRetry={history.reload} />}
      {history.data?.queries.map((q) => (
        <Card key={q.query_id}>
          <Spread>
            <Text style={styles.queryText} numberOfLines={2}>
              {q.query}
            </Text>
            <ConfidenceBadge confidence={Math.round(q.confidence)} />
          </Spread>
          <Text style={styles.faint}>{formatDateTime(q.created_at)}</Text>
        </Card>
      ))}
    </Screen>
  );
}

const styles = StyleSheet.create({
  barChart: { flexDirection: 'row', justifyContent: 'space-between', height: 160, alignItems: 'flex-end' },
  barCol: { flex: 1, alignItems: 'center', gap: 6 },
  barValue: { ...typography.small, color: colors.textFaint, fontWeight: '600' },
  barValuePeak: { color: colors.accent, fontWeight: '800' },
  barTrack: { width: 20, height: 100, justifyContent: 'flex-end' },
  bar: {
    width: '100%',
    backgroundColor: colors.accent,
    opacity: 0.55,
    borderRadius: 6,
    minHeight: 4,
  },
  barPeak: { opacity: 1 },
  barLabel: { ...typography.small, color: colors.textFaint, fontSize: 10, letterSpacing: 0.3 },

  topicRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  topicRowLast: { marginBottom: 0, paddingBottom: 0, borderBottomWidth: 0 },
  topicRank: {
    ...typography.small,
    color: colors.textFaint,
    fontWeight: '700',
    width: 16,
    textAlign: 'center',
  },
  topicName: { width: 84, ...typography.small, color: colors.textSecondary, fontWeight: '500' },
  topicTrack: { flex: 1, height: 8, borderRadius: 4, backgroundColor: colors.surface3, overflow: 'hidden' },
  topicFill: { height: '100%', backgroundColor: colors.accent, borderRadius: 4 },
  topicCount: { ...typography.small, color: colors.textPrimary, fontWeight: '700', width: 28, textAlign: 'right' },

  gapCard: { flexDirection: 'row', overflow: 'hidden', padding: 0 },
  gapAccent: { width: 4, backgroundColor: colors.accent, opacity: 0.7 },
  gapBody: { flex: 1, padding: spacing.md },
  gapQuery: { color: colors.textPrimary, fontWeight: '700', letterSpacing: 0.1 },
  suggestion: { ...typography.small, color: colors.textFaint, marginTop: spacing.sm, fontStyle: 'italic' },
  muted: { ...typography.small, color: colors.textSecondary },
  queryText: { color: colors.textPrimary, fontWeight: '600', flex: 1, marginRight: spacing.sm },
  faint: { ...typography.small, color: colors.textFaint, marginTop: spacing.sm },
});