import React, { useState } from 'react';
import { StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import Icon from 'react-native-vector-icons/Feather';
import { Card, PageHeader, Row, Screen, SectionTitle } from '../components/Layout';
import { Select } from '../components/Form';
import { Badge, ErrorBanner, Skeleton, StatusBadge, Toast } from '../components/ui';
import { api, useApi } from '../lib/api';
import { formatDate } from '../lib/format';
import type { Equipment, Incident, LessonCard, Warning } from '../lib/types';
import { colors, radius, spacing, typography } from '../theme/colors';

const SEVERITY_ICON: Record<string, string> = {
  high: 'alert-circle',
  medium: 'alert-triangle',
  low: 'info',
};

const LESSON_ROW_ICON: Record<string, string> = {
  'What happened': 'file-text',
  'Root cause': 'search',
  'What was done': 'tool',
  'Watch for': 'eye',
};

export default function IncidentsScreen() {
  const incidents = useApi<{ incidents: Incident[] }>('/incidents');
  const lessons = useApi<{ cards: LessonCard[] }>('/lessons-learned');
  const warnings = useApi<{ warnings: Warning[] }>('/alerts/warnings');
  const equipment = useApi<{ equipment: Equipment[] }>('/equipment');

  const [equipmentId, setEquipmentId] = useState('');
  const [description, setDescription] = useState('');
  const [severity, setSeverity] = useState('medium');
  const [incidentType, setIncidentType] = useState('incident');
  const [submitting, setSubmitting] = useState(false);
  const [descFocused, setDescFocused] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const equipmentOptions = [
    { label: 'Select equipment…', value: '' },
    ...(equipment.data?.equipment ?? []).map((eq) => ({
      label: `${eq.equipment_id} — ${eq.name}`,
      value: eq.equipment_id,
    })),
  ];

  async function submitReport() {
    if (!equipmentId || !description.trim()) return;
    setSubmitting(true);
    try {
      const res = await api.post<{ incident_id: string }>('/incidents/report', {
        equipment_id: equipmentId,
        description,
        severity,
        incident_type: incidentType,
      });
      setToast(`Reported as ${res.incident_id}`);
      setDescription('');
      incidents.reload();
    } catch {
      setToast('Failed to submit report');
    } finally {
      setSubmitting(false);
      setTimeout(() => setToast(null), 4000);
    }
  }

  return (
    <Screen>
      <PageHeader
        title="Incidents & Lessons Learned"
        subtitle="Patterns across incidents, lessons extracted, and warnings when today matches yesterday's disasters."
      />

      {warnings.data &&
        warnings.data.warnings.length > 0 &&
        warnings.data.warnings.map((w) => {
          const tone = w.urgency === 'high' ? colors.red : colors.amber;
          return (
            <Card key={w.warning_id} style={{ borderColor: tone, borderWidth: 1.5 }}>
              <Row style={{ alignItems: 'center', marginBottom: spacing.sm }}>
                <View style={[styles.warningIconWrap, { backgroundColor: tone + '22' }]}>
                  <Icon name="alert-triangle" size={16} color={tone} />
                </View>
                <Text style={[styles.warningTitle, { color: tone }]}>PROACTIVE WARNING</Text>
              </Row>
              <Text style={styles.warningHeadline}>{w.title}</Text>

              <View style={styles.wbBlock}>
                <Row style={{ alignItems: 'center', gap: 6 }}>
                  <Icon name="link" size={12} color={colors.textFaint} />
                  <Text style={styles.wbLabel}>Matching factors</Text>
                </Row>
                {w.matching_factors.map((f) => (
                  <View key={f} style={styles.bulletRow}>
                    <View style={styles.bulletDot} />
                    <Text style={styles.wbItem}>{f}</Text>
                  </View>
                ))}
              </View>

              <View style={styles.wbBlock}>
                <Row style={{ alignItems: 'center', gap: 6 }}>
                  <Icon name="clock" size={12} color={colors.textFaint} />
                  <Text style={styles.wbLabel}>Past outcome</Text>
                </Row>
                <Text style={styles.wbText}>{w.past_outcome}</Text>
              </View>

              <View style={[styles.wbBlock, styles.recommendedBox, { borderColor: tone + '55' }]}>
                <Row style={{ alignItems: 'center', gap: 6 }}>
                  <Icon name="check-circle" size={12} color={tone} />
                  <Text style={[styles.wbLabel, { color: tone }]}>Recommended</Text>
                </Row>
                <Text style={styles.wbText}>
                  <Text style={{ fontWeight: '700', color: colors.textPrimary }}>{w.recommended_action}</Text>
                  {w.reference ? ` · ${w.reference}` : ''}
                </Text>
              </View>
            </Card>
          );
        })}

      <SectionTitle>Report an issue</SectionTitle>
      <Card>
        <Select label="Equipment" value={equipmentId} onChange={setEquipmentId} options={equipmentOptions} />
        <View style={{ marginBottom: spacing.md }}>
          <Text style={styles.label}>What happened?</Text>
          <TextInput
            style={[styles.textarea, descFocused && styles.textareaFocused]}
            placeholder="Describe the issue or near-miss…"
            placeholderTextColor={colors.textFaint}
            value={description}
            onChangeText={setDescription}
            onFocus={() => setDescFocused(true)}
            onBlur={() => setDescFocused(false)}
            multiline
            numberOfLines={4}
          />
        </View>
        <Row>
          <View style={{ flex: 1 }}>
            <Select
              label="Severity"
              value={severity}
              onChange={setSeverity}
              options={[
                { label: 'High', value: 'high' },
                { label: 'Medium', value: 'medium' },
                { label: 'Low', value: 'low' },
              ]}
            />
          </View>
          <View style={{ flex: 1 }}>
            <Select
              label="Type"
              value={incidentType}
              onChange={setIncidentType}
              options={[
                { label: 'Incident', value: 'incident' },
                { label: 'Near-miss', value: 'near-miss' },
              ]}
            />
          </View>
        </Row>
        <TouchableOpacity
          activeOpacity={0.85}
          style={[styles.submitBtn, (submitting || !equipmentId || !description.trim()) && styles.submitBtnDisabled]}
          onPress={submitReport}
          disabled={submitting || !equipmentId || !description.trim()}
        >
          {submitting ? (
            <Text style={styles.submitBtnText}>Submitting…</Text>
          ) : (
            <Row style={{ alignItems: 'center', gap: 6 }}>
              <Icon name="send" size={15} color={colors.white} />
              <Text style={styles.submitBtnText}>Submit report</Text>
            </Row>
          )}
        </TouchableOpacity>
      </Card>

      <SectionTitle>Incident log</SectionTitle>
      {incidents.loading && <Skeleton height={160} />}
      {incidents.error && <ErrorBanner error={incidents.error} onRetry={incidents.reload} />}
      {incidents.data?.incidents.length === 0 && (
        <Card style={styles.emptyCard}>
          <Icon name="clipboard" size={24} color={colors.textFaint} />
          <Text style={styles.muted}>No incidents logged yet.</Text>
        </Card>
      )}
      {incidents.data?.incidents.map((inc) => {
        const sevTone = inc.severity === 'high' ? colors.red : inc.severity === 'medium' ? colors.amber : colors.gray;
        return (
          <Card key={inc.incident_id}>
            <Row style={{ alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
              <View style={styles.monoChip}>
                <Icon name="hash" size={11} color={colors.textFaint} />
                <Text style={styles.mono}>{inc.incident_id}</Text>
              </View>
              <Badge tone={inc.severity === 'high' ? 'red' : inc.severity === 'medium' ? 'amber' : 'gray'}>
                {inc.severity}
              </Badge>
              <Badge tone={inc.incident_type === 'near-miss' ? 'blue' : 'gray'}>{inc.incident_type}</Badge>
              <StatusBadge status={inc.status} />
            </Row>
            <Row style={{ alignItems: 'center', marginTop: spacing.sm, gap: 6 }}>
              <Icon name={SEVERITY_ICON[inc.severity] ?? 'info'} size={14} color={sevTone} />
              <Text style={styles.incTitle}>{inc.title}</Text>
            </Row>
            <Text style={styles.muted}>{inc.description}</Text>
            <Row style={{ alignItems: 'center', marginTop: spacing.sm, gap: 6 }}>
              <Icon name="tool" size={11} color={colors.textFaint} />
              <Text style={styles.faint}>{inc.equipment_id}</Text>
              <Text style={styles.faint}>·</Text>
              <Icon name="calendar" size={11} color={colors.textFaint} />
              <Text style={styles.faint}>{formatDate(inc.date)}</Text>
            </Row>
          </Card>
        );
      })}

      <SectionTitle>Lessons learned</SectionTitle>
      {lessons.loading && <Skeleton height={140} />}
      {lessons.error && <ErrorBanner error={lessons.error} onRetry={lessons.reload} />}
      {lessons.data?.cards.length === 0 && (
        <Card style={styles.emptyCard}>
          <Icon name="book-open" size={24} color={colors.textFaint} />
          <Text style={styles.muted}>No lessons captured yet.</Text>
        </Card>
      )}
      {lessons.data?.cards.map((c) => (
        <Card key={c.card_id}>
          <Row style={{ alignItems: 'center', marginBottom: spacing.sm }}>
            <View style={styles.lessonIconWrap}>
              <Icon name="zap" size={16} color={colors.accent} />
            </View>
            <Text style={styles.lessonTitle}>{c.title}</Text>
          </Row>
          <Badge tone="gray">{c.equipment_type}</Badge>
          {(
            [
              ['What happened', c.what_happened],
              ['Root cause', c.root_cause],
              ['What was done', c.what_was_done],
              ['Watch for', c.watch_for],
            ] as [string, string][]
          ).map(([label, text]) => (
            <View key={label} style={styles.lessonBlock}>
              <Row style={{ alignItems: 'center', gap: 6 }}>
                <Icon
                  name={LESSON_ROW_ICON[label] ?? 'circle'}
                  size={12}
                  color={label === 'Watch for' ? colors.amber : colors.textFaint}
                />
                <Text style={[styles.lbLabel, label === 'Watch for' && { color: colors.amber }]}>{label}</Text>
              </Row>
              <Text style={styles.lbText}>{text}</Text>
            </View>
          ))}
        </Card>
      ))}

      {toast && <Toast message={toast} />}
    </Screen>
  );
}

const styles = StyleSheet.create({
  warningIconWrap: {
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
  },
  warningTitle: { fontWeight: '800', letterSpacing: 0.4, fontSize: 12 },
  warningHeadline: { ...typography.h3, color: colors.textPrimary, marginBottom: spacing.sm },
  wbBlock: { marginTop: spacing.sm },
  wbLabel: { ...typography.small, color: colors.textFaint, fontWeight: '700' },
  wbItem: { ...typography.small, color: colors.textSecondary, flex: 1 },
  wbText: { ...typography.small, color: colors.textSecondary, marginTop: 4 },
  bulletRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 6, marginTop: 4, paddingLeft: 2 },
  bulletDot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.textFaint,
    marginTop: 6,
  },
  recommendedBox: {
    borderWidth: 1,
    borderRadius: radius.sm,
    padding: spacing.sm,
    backgroundColor: colors.surface2,
  },

  label: { ...typography.small, color: colors.textSecondary, marginBottom: 6, fontWeight: '600' },
  textarea: {
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    color: colors.textPrimary,
    minHeight: 90,
    textAlignVertical: 'top',
  },
  textareaFocused: {
    borderColor: colors.accent,
    shadowColor: colors.accent,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
  },
  submitBtn: {
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
  submitBtnDisabled: { opacity: 0.5, shadowOpacity: 0 },
  submitBtnText: { color: colors.white, fontWeight: '700' },

  emptyCard: { alignItems: 'center', gap: 8, paddingVertical: spacing.xl ?? 24 },

  incCard: { borderLeftWidth: 3 },
  monoChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.surface2,
    borderRadius: radius.pill,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  mono: { ...typography.small, color: colors.textFaint, fontFamily: 'Menlo' },
  incTitle: { color: colors.textPrimary, fontWeight: '700', flex: 1 },
  muted: { ...typography.small, color: colors.textSecondary, marginTop: spacing.sm },
  faint: { ...typography.small, color: colors.textFaint },

  lessonIconWrap: {
    width: 28,
    height: 28,
    borderRadius: radius.sm,
    backgroundColor: colors.accentSoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
  },
  lessonTitle: { ...typography.h3, color: colors.textPrimary, flex: 1 },
  lessonBlock: { marginTop: spacing.md },
  lbLabel: { ...typography.small, color: colors.textFaint, fontWeight: '700' },
  lbText: { ...typography.small, color: colors.textSecondary, marginTop: 4, marginLeft: 18 },
});