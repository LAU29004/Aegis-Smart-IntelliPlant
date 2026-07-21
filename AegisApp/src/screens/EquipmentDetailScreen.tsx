import React, { useState } from 'react';
import { StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import { Card, Row, Screen, SectionTitle, Spread } from '../components/Layout';
import { Badge, ErrorBanner, HealthRing, Skeleton, StatusBadge } from '../components/ui';
import { api, ApiError, useApi } from '../lib/api';
import { docTypeLabel, formatDate } from '../lib/format';
import type {
  Alert,
  DocumentItem,
  EquipmentDetail,
  HistoryEvent,
  RcaResponse,
} from '../lib/types';
import type { EquipmentStackParamList } from '../navigation/types';
import { colors, radius, spacing, toneColor, typography } from '../theme/colors';

type DetailRoute = RouteProp<EquipmentStackParamList, 'EquipmentDetail'>;

const EVENT_COLORS: Record<string, string> = {
  failure: colors.red,
  repair: colors.accent,
  inspection: colors.amber,
  pm: colors.green,
};

const EVENT_ICONS: Record<string, string> = {
  failure: '⚠️',
  repair: '🔧',
  inspection: '🔍',
  pm: '🛠️',
};

type Tab = 'timeline' | 'alerts' | 'documents' | 'rca';

const TABS: [Tab, string, string][] = [
  ['timeline', 'Timeline', '🕒'],
  ['alerts', 'Alerts', '🔔'],
  ['documents', 'Documents', '📄'],
  ['rca', 'RCA', '🧠'],
];

export default function EquipmentDetailScreen() {
  const { params } = useRoute<DetailRoute>();
  const id = params.id;
  const [tab, setTab] = useState<Tab>('timeline');

  const detail = useApi<EquipmentDetail>(`/equipment/${id}`);
  const history = useApi<{ events: HistoryEvent[] }>(`/equipment/${id}/history`);
  const alerts = useApi<{ alerts: Alert[] }>(`/equipment/${id}/alerts`);
  const docs = useApi<{ documents: DocumentItem[] }>(`/equipment/${id}/documents`);

  const [symptom, setSymptom] = useState('');
  const [symptomFocused, setSymptomFocused] = useState(false);
  const [rca, setRca] = useState<RcaResponse | null>(null);
  const [rcaBusy, setRcaBusy] = useState(false);
  const [rcaError, setRcaError] = useState<ApiError | null>(null);

  async function runRca() {
    if (!symptom.trim()) return;
    setRcaBusy(true);
    setRcaError(null);
    try {
      setRca(await api.get<RcaResponse>(`/equipment/${id}/rca?symptom=${encodeURIComponent(symptom)}`));
    } catch (e) {
      setRcaError(e instanceof ApiError ? e : new ApiError('RCA failed'));
    } finally {
      setRcaBusy(false);
    }
  }

  const eq = detail.data;

  return (
    <Screen>
      {detail.loading && <Skeleton height={140} />}
      {detail.error && <ErrorBanner error={detail.error} onRetry={detail.reload} />}
      {eq && (
        <Card style={styles.heroCard}>
          <Row style={{ alignItems: 'center', gap: spacing.lg }}>
            <View style={styles.ringWrap}>
              <HealthRing score={eq.health_score} size="lg" />
            </View>
            <View style={{ flex: 1, minWidth: 0 }}>
              <Row style={{ marginBottom: 4, alignItems: 'center' }}>
                <Text style={styles.eqName} numberOfLines={1}>
                  {eq.name}
                </Text>
                <StatusBadge status={eq.status} />
              </Row>
              <Text style={styles.eqSub} numberOfLines={1}>
                {eq.equipment_id} · {eq.type} · {eq.location}
              </Text>
              <Text style={styles.eqSub} numberOfLines={1}>
                {eq.manufacturer} {eq.model}
              </Text>
              {!!eq.description && (
                <Text style={styles.eqDesc} numberOfLines={2}>
                  {eq.description}
                </Text>
              )}
            </View>
          </Row>
          <View style={styles.kv}>
            <Spread style={styles.kvRow}>
              <Text style={styles.kvKey}>Last serviced</Text>
              <Text style={styles.kvVal}>{formatDate(eq.last_serviced)}</Text>
            </Spread>
            <Spread style={styles.kvRow}>
              <Text style={styles.kvKey}>Next due</Text>
              <Text style={styles.kvVal}>{formatDate(eq.next_due)}</Text>
            </Spread>
            <Spread style={styles.kvRow}>
              <Text style={styles.kvKey}>Open alerts</Text>
              <View
                style={[
                  styles.alertCountPill,
                  { backgroundColor: eq.open_alerts_count > 0 ? colors.red + '22' : colors.green + '22' },
                ]}
              >
                <Text style={[styles.kvVal, { color: eq.open_alerts_count > 0 ? colors.red : colors.green }]}>
                  {eq.open_alerts_count}
                </Text>
              </View>
            </Spread>
          </View>
        </Card>
      )}

      <View style={styles.tabs}>
        {TABS.map(([key, label, icon]) => (
          <TouchableOpacity
            key={key}
            activeOpacity={0.75}
            style={[styles.tab, tab === key && styles.tabActive]}
            onPress={() => setTab(key)}
          >
            <Text style={styles.tabIcon}>{icon}</Text>
            <Text style={[styles.tabText, tab === key && styles.tabTextActive]}>{label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {tab === 'timeline' && (
        <>
          {history.loading && <Skeleton height={200} />}
          {history.error && <ErrorBanner error={history.error} onRetry={history.reload} />}
          {history.data?.events.map((ev, idx) => (
            <View
              key={ev.event_id}
              style={[
                styles.timelineItem,
                idx === (history.data?.events.length ?? 0) - 1 && { borderLeftColor: 'transparent' },
              ]}
            >
              <View style={[styles.timelineDot, { backgroundColor: EVENT_COLORS[ev.event_type] ?? colors.gray }]}>
                <Text style={styles.timelineDotIcon}>{EVENT_ICONS[ev.event_type] ?? '•'}</Text>
              </View>
              <View style={styles.timelineCard}>
                <Row style={{ alignItems: 'center' }}>
                  <Text style={styles.timelineTitle}>{ev.title}</Text>
                  <StatusBadge status={ev.event_type} />
                </Row>
                <Text style={styles.timelineDate}>{formatDate(ev.date)}</Text>
                {ev.description && <Text style={styles.timelineDesc}>{ev.description}</Text>}
                {(ev.work_order || ev.document) && (
                  <Row style={{ marginTop: spacing.sm, flexWrap: 'wrap', gap: 6 }}>
                    {ev.work_order && <Badge tone="gray">🗂️ {ev.work_order}</Badge>}
                    {ev.document && <Badge tone="blue">📄 {ev.document}</Badge>}
                  </Row>
                )}
              </View>
            </View>
          ))}
          {history.data?.events.length === 0 && (
            <Card style={styles.emptyCard}>
              <Text style={styles.emptyIcon}>🗒️</Text>
              <Text style={styles.muted}>No maintenance history recorded.</Text>
            </Card>
          )}
        </>
      )}

      {tab === 'alerts' && (
        <>
          {alerts.loading && <Skeleton height={120} />}
          {alerts.error && <ErrorBanner error={alerts.error} onRetry={alerts.reload} />}
          {alerts.data?.alerts.length === 0 && (
            <Card style={styles.emptyCard}>
              <Text style={styles.emptyIcon}>✅</Text>
              <Text style={styles.muted}>No alerts for this equipment.</Text>
            </Card>
          )}
          {alerts.data?.alerts.map((a) => (
            <Card
              key={a.alert_id}
            >
              <Row style={{ marginBottom: spacing.sm, alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
                <Text style={styles.alertTitle}>{a.title}</Text>
                <StatusBadge status={a.severity} />
                <StatusBadge status={a.status} />
              </Row>
              <Text style={styles.muted}>{a.description}</Text>
              {a.recommended_action && (
                <View style={styles.recommendedBox}>
                  <Text style={styles.recommended}>
                    <Text style={{ fontWeight: '700' }}>💡 Recommended: </Text>
                    {a.recommended_action}
                  </Text>
                </View>
              )}
            </Card>
          ))}
        </>
      )}

      {tab === 'documents' && (
        <>
          {docs.loading && <Skeleton height={120} />}
          {docs.error && <ErrorBanner error={docs.error} onRetry={docs.reload} />}
          {docs.data?.documents.map((d) => (
            <Card key={d.doc_id} style={styles.docCard}>
              <Row style={{ alignItems: 'center', gap: spacing.md }}>
                <View style={styles.docIconWrap}>
                  <Text style={styles.docIcon}>📄</Text>
                </View>
                <View style={{ flex: 1, minWidth: 0 }}>
                  <Text style={styles.docTitle} numberOfLines={1}>
                    {d.name}
                  </Text>
                  <Row style={{ alignItems: 'center', gap: 8 }}>
                    <Badge tone="blue">{docTypeLabel(d.doc_type)}</Badge>
                    <Text style={styles.muted}>{formatDate(d.uploaded_at)}</Text>
                  </Row>
                </View>
              </Row>
            </Card>
          ))}
          {docs.data?.documents.length === 0 && (
            <Card style={styles.emptyCard}>
              <Text style={styles.emptyIcon}>📭</Text>
              <Text style={styles.muted}>No documents tagged to this equipment yet.</Text>
            </Card>
          )}
        </>
      )}

      {tab === 'rca' && (
        <View>
          <Card style={styles.rcaCard}>
            <Row style={{ alignItems: 'center', marginBottom: spacing.md }}>
              <Text style={styles.cardTitleIcon}>🧠</Text>
              <Text style={styles.cardTitle}>Root Cause Analysis Assistant</Text>
            </Row>
            <Text style={styles.rcaHint}>Describe what you're observing and get likely causes from past cases.</Text>
            <Row style={{ marginBottom: spacing.sm, marginTop: spacing.md }}>
              <TextInput
                style={[styles.rcaInput, symptomFocused && styles.rcaInputFocused]}
                placeholder="e.g. high vibration, unusual noise, overheating…"
                placeholderTextColor={colors.textFaint}
                value={symptom}
                onChangeText={setSymptom}
                onSubmitEditing={runRca}
                onFocus={() => setSymptomFocused(true)}
                onBlur={() => setSymptomFocused(false)}
              />
            </Row>
            <TouchableOpacity
              activeOpacity={0.85}
              style={[styles.analyseBtn, (rcaBusy || !symptom.trim()) && styles.analyseBtnDisabled]}
              onPress={runRca}
              disabled={rcaBusy || !symptom.trim()}
            >
              <Text style={styles.analyseBtnText}>{rcaBusy ? '⏳ Analysing…' : '🔎 Analyse'}</Text>
            </TouchableOpacity>
            {rcaError && (
              <View style={{ marginTop: spacing.sm }}>
                <ErrorBanner error={rcaError} />
              </View>
            )}
          </Card>

          {rca && (
            <>
              <SectionTitle>Probable causes for "{rca.symptom}"</SectionTitle>
              {rca.probable_causes.length === 0 && (
                <Card style={styles.emptyCard}>
                  <Text style={styles.emptyIcon}>🤷</Text>
                  <Text style={styles.muted}>
                    No similar past failures found — try describing the symptom differently.
                  </Text>
                </Card>
              )}
              {rca.probable_causes.map((c, i) => (
                <Card key={i} style={styles.causeCard}>
                  <Row style={{ alignItems: 'center' }}>
                    <View style={styles.causeNumber}>
                      <Text style={styles.causeNumberText}>{i + 1}</Text>
                    </View>
                    <Text style={styles.causeTitle}>{c.cause}</Text>
                    <Badge tone={c.likelihood === 'high' ? 'red' : c.likelihood === 'medium' ? 'amber' : 'gray'}>
                      {c.likelihood} likelihood
                    </Badge>
                  </Row>
                  <Text style={[styles.muted, { marginTop: spacing.sm }]}>{c.evidence}</Text>
                  <View style={styles.recommendedBox}>
                    <Text style={styles.recommended}>
                      <Text style={{ fontWeight: '700' }}>✅ Action: </Text>
                      {c.recommended_action}
                    </Text>
                  </View>
                </Card>
              ))}
              {rca.sources.length > 0 && (
                <Row style={{ marginTop: spacing.sm, flexWrap: 'wrap', gap: 6 }}>
                  {rca.sources.map((s) => (
                    <View key={s.chunk_id} style={styles.sourceChip}>
                      <Text style={styles.sourceChipText}>
                        📄 {s.document} · p.{s.page}
                      </Text>
                    </View>
                  ))}
                </Row>
              )}
            </>
          )}
        </View>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  heroCard: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  ringWrap: {
    padding: 4,
    borderRadius: 999,
    backgroundColor: colors.surface2,
  },
  eqName: { ...typography.h2, color: colors.textPrimary, flexShrink: 1, marginRight: 8 },
  eqSub: { ...typography.small, color: colors.textSecondary, marginTop: 2 },
  eqDesc: { ...typography.small, color: colors.textFaint, marginTop: 6, fontStyle: 'italic' },
  kv: {
    marginTop: spacing.md,
    gap: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.md,
  },
  kvRow: { alignItems: 'center' },
  kvKey: { ...typography.small, color: colors.textFaint },
  kvVal: { ...typography.small, color: colors.textPrimary, fontWeight: '700' },
  alertCountPill: {
    paddingHorizontal: 10,
    paddingVertical: 2,
    borderRadius: radius.pill,
  },

  tabs: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: 4,
    marginBottom: spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 3,
    elevation: 1,
  },
  tab: { flex: 1, paddingVertical: 10, borderRadius: radius.sm, alignItems: 'center', gap: 2 },
  tabActive: {
    backgroundColor: colors.accentSoft,
    shadowColor: colors.accent,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.15,
    shadowRadius: 3,
    elevation: 1,
  },
  tabIcon: { fontSize: 13 },
  tabText: { ...typography.small, color: colors.textFaint, fontWeight: '600' },
  tabTextActive: { color: colors.accent },

  timelineItem: {
    borderLeftWidth: 2,
    borderLeftColor: colors.border,
    paddingLeft: spacing.lg,
    paddingBottom: spacing.lg,
    marginLeft: 10,
    position: 'relative',
  },
  timelineCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  timelineDot: {
    position: 'absolute',
    left: -13,
    top: 0,
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: colors.bg,
  },
  timelineDotIcon: { fontSize: 10 },
  timelineTitle: { color: colors.textPrimary, fontWeight: '700', flex: 1 },
  timelineDate: { ...typography.small, color: colors.textFaint, marginTop: 2 },
  timelineDesc: { ...typography.small, color: colors.textSecondary, marginTop: 6 },

  alertCard: { borderLeftWidth: 3 },
  alertTitle: { color: colors.textPrimary, fontWeight: '700', flex: 1 },
  muted: { ...typography.small, color: colors.textSecondary },
  recommendedBox: {
    marginTop: spacing.sm,
    backgroundColor: colors.amber + '14',
    borderRadius: radius.sm,
    padding: spacing.sm,
  },
  recommended: { ...typography.small, color: colors.amber },

  docCard: { paddingVertical: spacing.sm },
  docIconWrap: {
    width: 40,
    height: 40,
    borderRadius: radius.sm,
    backgroundColor: colors.surface2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  docIcon: { fontSize: 18 },
  docTitle: { color: colors.textPrimary, fontWeight: '600', marginBottom: 4 },

  emptyCard: { alignItems: 'center', paddingVertical: spacing.xl ?? 24, gap: 8 },
  emptyIcon: { fontSize: 28 },

  cardTitleIcon: { fontSize: 18, marginRight: 8 },
  cardTitle: { ...typography.h3, color: colors.textPrimary },
  rcaCard: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 6,
    elevation: 2,
  },
  rcaHint: { ...typography.small, color: colors.textFaint },
  rcaInput: {
    flex: 1,
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    color: colors.textPrimary,
  },
  rcaInputFocused: {
    borderColor: colors.accent,
    shadowColor: colors.accent,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
  },
  analyseBtn: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: 13,
    alignItems: 'center',
    shadowColor: colors.accent,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 2,
  },
  analyseBtnDisabled: { opacity: 0.5, shadowOpacity: 0 },
  analyseBtnText: { color: colors.white, fontWeight: '700' },

  causeCard: { gap: 2 },
  causeNumber: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.accentSoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
  },
  causeNumberText: { color: colors.accent, fontWeight: '700', fontSize: 12 },
  causeTitle: { color: colors.textPrimary, fontWeight: '700', flex: 1 },

  sourceChip: {
    backgroundColor: colors.surface3,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  sourceChipText: { ...typography.small, color: colors.textSecondary },
});