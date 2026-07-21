import React, { useState } from 'react';
import {
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import {
  Card,
  PageHeader,
  Row,
  Screen,
  SectionTitle,
  Spread,
} from '../components/Layout';
import {
  Badge,
  ErrorBanner,
  Skeleton,
  StatCard,
  Toast,
} from '../components/ui';
import { api, useApi } from '../lib/api';
import { formatDate } from '../lib/format';
import type {
  Certification,
  ComplianceGap,
  ComplianceMatrix,
} from '../lib/types';
import {
  colors,
  radius,
  spacing,
  toneColor,
  typography,
} from '../theme/colors';
import Feather from 'react-native-vector-icons/Feather';

const getStatusIcon = (status: string, color = '#000', size = 18) => {
  switch (status) {
    case 'compliant':
      return <Feather name="check-circle" size={size} color="#22C55E" />;

    case 'gap':
      return <Feather name="x-circle" size={size} color="#EF4444" />;

    case 'partial':
      return <Feather name="minus-circle" size={size} color="#F59E0B" />;

    case 'expiring':
      return <Feather name="clock" size={size} color="#F97316" />;

    case 'not_assessed':
      return <Feather name="help-circle" size={size} color="#9CA3AF" />;

    default:
      return <Feather name="circle" size={size} color={color} />;
  }
};

const CELL_TONE: Record<string, string> = {
  compliant: colors.green,
  gap: colors.red,
  partial: colors.amber,
  expiring: colors.amber,
  not_assessed: colors.gray,
};

const SEVERITY_TONE: Record<string, string> = {
  high: colors.red,
  medium: colors.amber,
  low: colors.gray,
};

export default function ComplianceScreen() {
  const matrix = useApi<ComplianceMatrix>('/compliance/matrix');
  const gaps = useApi<{ gaps: ComplianceGap[] }>('/compliance/gaps');
  const expiring = useApi<{ certifications: Certification[] }>(
    '/compliance/expiring?days=60',
  );
  const [toast, setToast] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);

  async function runScan() {
    setScanning(true);
    try {
      const res = await api.post<{ gaps_found: number }>(
        '/compliance/scan',
        {},
      );
      setToast(
        `Compliance scan complete — ${res.gaps_found} new gap${
          res.gaps_found === 1 ? '' : 's'
        } detected.`,
      );
      matrix.reload();
      gaps.reload();
    } catch {
      setToast('Scan failed — is the backend running?');
    } finally {
      setScanning(false);
      setTimeout(() => setToast(null), 4000);
    }
  }

  const m = matrix.data;

  return (
    <Screen>
      <Spread style={{ alignItems: 'flex-start' }}>
        <View style={{ flex: 1, marginRight: spacing.md }}>
          <PageHeader
            title="Compliance"
            subtitle="Regulation requirements mapped against indexed SOPs."
          />
        </View>
      </Spread>
      <TouchableOpacity
        style={[styles.scanBtn, scanning && styles.scanBtnDisabled]}
        onPress={runScan}
        disabled={scanning}
        activeOpacity={0.85}
      >
        <Text style={styles.scanBtnText}>
          {scanning ? 'Scanning…' : '▶  Run Compliance Scan'}
        </Text>
      </TouchableOpacity>

      {matrix.error && (
        <ErrorBanner error={matrix.error} onRetry={matrix.reload} />
      )}
      {matrix.loading && <Skeleton height={220} />}

      {m && (
        <>
          <View style={styles.kpiRow}>
            <StatCard
              label="Overall Compliance"
              value={m.overall_score}
              unit="%"
              tone={
                m.overall_score >= 80
                  ? 'green'
                  : m.overall_score >= 60
                  ? 'amber'
                  : 'red'
              }
            />
            <StatCard
              label="Open Gaps"
              value={gaps.data?.gaps.length ?? '—'}
              tone="red"
            />
            <StatCard
              label="Expiring ≤60d"
              value={expiring.data?.certifications.length ?? '—'}
              tone="amber"
            />
          </View>

          <SectionTitle>Regulation × Department matrix</SectionTitle>
          <View style={styles.matrixCard}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View>
                <View style={styles.matrixHeaderRow}>
                  <View style={styles.matrixRegCell} />
                  {m.departments.map(d => (
                    <View key={d} style={styles.matrixHeadCell}>
                      <Text style={styles.matrixHeadText}>{d}</Text>
                    </View>
                  ))}
                </View>
                {m.regulations.map((reg, ri) => (
                  <View
                    key={reg}
                    style={[
                      styles.matrixRow,
                      ri % 2 === 1 && styles.matrixRowAlt,
                    ]}
                  >
                    <View style={styles.matrixRegCell}>
                      <Text style={styles.matrixRegText} numberOfLines={2}>
                        {reg}
                      </Text>
                    </View>
                    {m.departments.map(dept => {
                      const cell = m.cells.find(
                        c => c.regulation === reg && c.department === dept,
                      );
                      const status = cell?.status ?? 'not_assessed';
                      const tone = CELL_TONE[status];
                      return (
                        <View key={dept} style={styles.matrixHeadCell}>
                          <View
                            style={[
                              styles.matrixCell,
                              {
                                borderColor: tone,
                                backgroundColor: `${tone}1A`,
                              },
                            ]}
                          >
                            <View
                              style={{
                                alignItems: 'center',
                                justifyContent: 'center',
                              }}
                            >
                              {getStatusIcon(status, tone)}

                              {cell && cell.gap_count > 0 && (
                                <Text
                                  style={{
                                    color: tone,
                                    fontWeight: '700',
                                    fontSize: 11,
                                    marginTop: 2,
                                  }}
                                >
                                  {cell.gap_count}
                                </Text>
                              )}
                            </View>
                          </View>
                        </View>
                      );
                    })}
                  </View>
                ))}
              </View>
            </ScrollView>
          </View>
          <Row style={{ marginTop: spacing.sm, flexWrap: 'wrap' }}>
            <View style={styles.legendChip}>
              <Text style={[styles.legendDot, { color: colors.green }]}>✓</Text>
              <Text style={styles.legend}>compliant</Text>
            </View>
            <View style={styles.legendChip}>
              <Text style={[styles.legendDot, { color: colors.red }]}>✗</Text>
              <Text style={styles.legend}>gap (count)</Text>
            </View>
            <View style={styles.legendChip}>
              <Text style={[styles.legendDot, { color: colors.amber }]}>
                ⏳
              </Text>
              <Text style={styles.legend}>expiring</Text>
            </View>
            <View style={styles.legendChip}>
              <Text style={[styles.legendDot, { color: colors.gray }]}>—</Text>
              <Text style={styles.legend}>not assessed</Text>
            </View>
          </Row>
        </>
      )}

      <SectionTitle>Detected gaps</SectionTitle>
      {gaps.loading && <Skeleton height={120} />}
      {gaps.error && <ErrorBanner error={gaps.error} onRetry={gaps.reload} />}
      {gaps.data?.gaps.map(g => (
        <Card key={g.gap_id} style={styles.gapCard}>
          <View
            style={[
              styles.gapAccent,
              { backgroundColor: SEVERITY_TONE[g.severity] ?? colors.gray },
            ]}
          />
          <View style={styles.gapBody}>
            <Row>
              <Badge
                tone={
                  g.severity === 'high'
                    ? 'red'
                    : g.severity === 'medium'
                    ? 'amber'
                    : 'gray'
                }
              >
                {g.severity}
              </Badge>
              <Text style={styles.gapReg}>{g.regulation}</Text>
              <Badge tone="gray">{g.department}</Badge>
            </Row>
            <Text style={styles.gapText}>
              <Text style={styles.gapTextLabel}>Requirement: </Text>
              {g.requirement}
            </Text>
            <Text style={styles.gapText}>
              <Text style={styles.gapTextLabel}>Missing: </Text>
              {g.what_is_missing}
            </Text>
            <Text style={[styles.gapText, { color: colors.amber }]}>
              <Text style={styles.gapTextLabel}>Action: </Text>
              {g.recommended_action}
            </Text>
          </View>
        </Card>
      ))}
      {gaps.data?.gaps.length === 0 && (
        <Card>
          <Text style={styles.muted}>No gaps detected. ✓</Text>
        </Card>
      )}

      <SectionTitle>Certifications expiring within 60 days</SectionTitle>
      {expiring.loading && <Skeleton height={100} />}
      {expiring.error && (
        <ErrorBanner error={expiring.error} onRetry={expiring.reload} />
      )}
      {expiring.data?.certifications.map(c => (
        <Card key={c.cert_id}>
          <Spread>
            <Text style={styles.certName}>{c.name}</Text>
            <View
              style={[
                styles.certDaysPill,
                {
                  backgroundColor:
                    c.days_remaining < 30
                      ? `${colors.red}1A`
                      : `${colors.amber}1A`,
                },
              ]}
            >
              <Text
                style={[
                  styles.certDays,
                  { color: c.days_remaining < 30 ? colors.red : colors.amber },
                ]}
              >
                {c.days_remaining < 0
                  ? `EXPIRED ${-c.days_remaining}d ago`
                  : `${c.days_remaining}d`}
              </Text>
            </View>
          </Spread>
          <Text style={styles.muted}>
            {formatDate(c.expiry_date)} · {c.department}
          </Text>
        </Card>
      ))}
      {expiring.data?.certifications.length === 0 && (
        <Card>
          <Text style={styles.muted}>
            Nothing expiring in the next 60 days.
          </Text>
        </Card>
      )}

      {toast && <Toast message={toast} />}
    </Screen>
  );
}

const styles = StyleSheet.create({
  scanBtn: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: 13,
    alignItems: 'center',
    marginBottom: spacing.lg,
    ...Platform.select({
      ios: {
        shadowColor: colors.accent,
        shadowOpacity: 0.3,
        shadowRadius: 10,
        shadowOffset: { width: 0, height: 4 },
      },
      android: { elevation: 3 },
    }),
  },
  scanBtnDisabled: {
    opacity: 0.6,
    ...Platform.select({
      ios: { shadowOpacity: 0.1 },
      android: { elevation: 0 },
    }),
  },
  scanBtnText: { color: colors.white, fontWeight: '700', letterSpacing: 0.3 },
  kpiRow: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
  matrixCard: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.xs ?? 4,
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOpacity: 0.05,
        shadowRadius: 8,
        shadowOffset: { width: 0, height: 2 },
      },
      android: { elevation: 1 },
    }),
  },
  matrixHeaderRow: { flexDirection: 'row' },
  matrixRow: { flexDirection: 'row', borderRadius: radius.sm },
  matrixRowAlt: { backgroundColor: colors.surface2 },
  matrixRegCell: { width: 140, padding: spacing.sm, justifyContent: 'center' },
  matrixRegText: { color: colors.textPrimary, fontWeight: '600', fontSize: 12 },
  matrixHeadCell: {
    width: 84,
    padding: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  matrixHeadText: {
    color: colors.textFaint,
    fontSize: 11,
    fontWeight: '700',
    textAlign: 'center',
    letterSpacing: 0.3,
  },
  matrixCell: {
    width: 60,
    height: 40,
    borderWidth: 1.5,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  legendChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginRight: spacing.md,
    marginBottom: 4,
  },
  legendDot: { fontWeight: '700', fontSize: 12 },
  legend: { ...typography.small, color: colors.textFaint },
  gapCard: { flexDirection: 'row', overflow: 'hidden', padding: 0 },
  gapAccent: { width: 4 },
  gapBody: { flex: 1, padding: spacing.md },
  gapReg: { color: colors.textPrimary, fontWeight: '700', flex: 1 },
  gapText: {
    ...typography.small,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  gapTextLabel: { fontWeight: '700', color: colors.textPrimary },
  muted: { ...typography.small, color: colors.textSecondary },
  certName: { color: colors.textPrimary, fontWeight: '700' },
  certDaysPill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radius.sm,
  },
  certDays: { fontWeight: '700', fontSize: 12 },
});
