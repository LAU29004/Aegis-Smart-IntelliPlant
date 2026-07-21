import React from 'react';
import { Platform, StyleSheet, Text, View } from 'react-native';
import { useApi } from '../lib/api';
import type { AnalyticsOverview, Equipment } from '../lib/types';
import { Card, PageHeader, Screen, SectionTitle } from '../components/Layout';
import { ErrorBanner, Skeleton, StatCard } from '../components/ui';
import EquipmentCard from '../components/EquipmentCard';
import { colors, radius, spacing, typography } from '../theme/colors';
import { useAuth } from '../context/AuthContext';

export default function DashboardScreen() {
  const { user } = useAuth();
  const overview = useApi<AnalyticsOverview>('/analytics/overview');
  const equipment = useApi<{ equipment: Equipment[] }>('/equipment');

  const k = overview.data?.kpis;
  const atRisk = (equipment.data?.equipment ?? [])
    .filter((e) => e.status !== 'healthy')
    .slice(0, 4);

  return (
    <Screen>
      <PageHeader
        title={`Welcome back${user?.name ? ', ' + user.name.split(' ')[0] : ''}`}
        subtitle="A live snapshot of the plant's knowledge base, compliance and equipment health."
      />

      {overview.error && <ErrorBanner error={overview.error} onRetry={overview.reload} />}
      {overview.loading && <Skeleton height={180} />}

      {k && (
        <View style={styles.kpiGrid}>
          <View style={styles.kpiHalf}>
            <StatCard label="Docs Indexed" value={k.documents_indexed} />
          </View>
          <View style={styles.kpiHalf}>
            <StatCard label="Queries This Week" value={k.queries_this_week} />
          </View>
          <View style={styles.kpiHalf}>
            <StatCard
              label="Avg Confidence"
              value={k.avg_confidence}
              unit="%"
              tone={k.avg_confidence >= 80 ? 'green' : k.avg_confidence >= 60 ? 'amber' : 'red'}
            />
          </View>
          <View style={styles.kpiHalf}>
            <StatCard label="Open Alerts" value={k.open_alerts} tone={k.open_alerts > 0 ? 'red' : 'green'} />
          </View>
          <View style={styles.kpiHalf}>
            <StatCard
              label="Compliance Score"
              value={k.compliance_score}
              unit="%"
              tone={k.compliance_score >= 80 ? 'green' : k.compliance_score >= 60 ? 'amber' : 'red'}
            />
          </View>
          <View style={styles.kpiHalf}>
            <StatCard label="Equipment Healthy" value={k.equipment_healthy_pct} unit="%" tone="blue" />
          </View>
        </View>
      )}

      <View style={styles.sectionHeaderRow}>
        <SectionTitle>Equipment needing attention</SectionTitle>
        {atRisk.length > 0 && (
          <View style={styles.countPill}>
            <Text style={styles.countPillText}>{atRisk.length}</Text>
          </View>
        )}
      </View>
      {equipment.loading && <Skeleton height={140} />}
      {equipment.error && <ErrorBanner error={equipment.error} onRetry={equipment.reload} />}
      {equipment.data && (
        <>
          {atRisk.map((eq) => (
            <EquipmentCard key={eq.equipment_id} eq={eq} />
          ))}
          {atRisk.length === 0 && (
            <Card style={styles.allClearCard}>
              <View style={styles.allClearIconWrap}>
                <Text style={styles.allClearIcon}>✓</Text>
              </View>
              <Text style={styles.allClearText}>All equipment is reporting healthy</Text>
            </Card>
          )}
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  kpiGrid: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -6, marginBottom: spacing.sm },
  kpiHalf: { width: '50%', padding: 6 },
  sectionHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  countPill: {
    backgroundColor: `${colors.red}1A`,
    borderRadius: radius.pill,
    minWidth: 22,
    height: 22,
    paddingHorizontal: 6,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: -4,
  },
  countPillText: { color: colors.red, fontWeight: '700', fontSize: 12 },
  allClearCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  allClearIconWrap: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: `${colors.green}1A`,
    alignItems: 'center',
    justifyContent: 'center',
  },
  allClearIcon: { color: colors.green, fontWeight: '700', fontSize: 15 },
  allClearText: { color: colors.textSecondary, ...typography.body, fontWeight: '500' },
});