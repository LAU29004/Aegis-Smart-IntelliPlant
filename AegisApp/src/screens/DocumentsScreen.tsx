import React, { useEffect, useRef, useState } from 'react';
import { Modal, Platform, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { pick, types } from '@react-native-documents/picker';
import { Card, PageHeader, Row, Screen, SectionTitle, Spread } from '../components/Layout';
import { LabeledInput, Select } from '../components/Form';
import { Badge, ErrorBanner, Skeleton, StatusBadge } from '../components/ui';
import { api, ApiError, useApi } from '../lib/api';
import { docTypeLabel, formatDate } from '../lib/format';
import type { DocumentDetail, DocumentItem, IngestStatus, UploadResponse } from '../lib/types';
import { colors, radius, spacing, typography } from '../theme/colors';

const DOC_TYPE_OPTIONS = [
  { label: 'Manual', value: 'manual' },
  { label: 'Maintenance Log', value: 'maintenance_log' },
  { label: 'SOP', value: 'sop' },
  { label: 'Inspection', value: 'inspection' },
  { label: 'Incident', value: 'incident' },
  { label: 'Regulation', value: 'regulation' },
  { label: 'Certificate', value: 'certificate' },
  { label: 'Other', value: 'other' },
];

export default function DocumentsScreen() {
  const docs = useApi<{ documents: DocumentItem[] }>('/documents');
  const [pickedFile, setPickedFile] = useState<{ uri: string; name: string; type: string } | null>(null);
  const [docType, setDocType] = useState('maintenance_log');
  const [equipmentId, setEquipmentId] = useState('');
  const [job, setJob] = useState<IngestStatus | null>(null);
  const [uploadError, setUploadError] = useState<ApiError | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState<DocumentDetail | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  async function choosePicker() {
    try {
      const [res] = await pick({
        type: [types.pdf, types.plainText, types.csv, types.xlsx],
      });
      setPickedFile({ uri: res.uri, name: res.name ?? 'file', type: res.type ?? 'application/octet-stream' });
    } catch {
      // user cancelled
    }
  }

  async function upload() {
    if (!pickedFile) return;
    setUploading(true);
    setUploadError(null);
    setJob(null);
    const fd = new FormData();
    fd.append('files', {
      uri: pickedFile.uri,
      name: pickedFile.name,
      type: pickedFile.type,
    } as unknown as Blob);
    fd.append('doc_type', docType);
    fd.append('equipment_id', equipmentId);
    try {
      const res = await api.upload<UploadResponse>('/ingest/upload', fd);
      poll(res.job_id);
    } catch (e) {
      setUploadError(e instanceof ApiError ? e : new ApiError('Upload failed'));
      setUploading(false);
    }
  }

  function poll(jobId: string) {
    pollRef.current = setInterval(async () => {
      try {
        const st = await api.get<IngestStatus>(`/ingest/status/${jobId}`);
        setJob(st);
        if (st.status === 'completed' || st.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current);
          setUploading(false);
          setPickedFile(null);
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
    <Screen>
      <PageHeader
        title="Document Library"
        subtitle="Upload anything — PDFs, logs, SOPs, spreadsheets. IntelliPlant parses, extracts entities and indexes it for search."
      />

      <Card>
        <Text style={styles.cardTitle}>Upload documents</Text>

        <TouchableOpacity style={styles.pickBtn} onPress={choosePicker} activeOpacity={0.7}>
          {pickedFile ? (
            <View style={styles.pickedRow}>
              <View style={styles.pickedIconWrap}>
                <Text style={styles.pickedIcon}>📄</Text>
              </View>
              <Text style={styles.pickedName} numberOfLines={1}>
                {pickedFile.name}
              </Text>
            </View>
          ) : (
            <>
              <Text style={styles.pickBtnIcon}>📎</Text>
              <Text style={styles.pickBtnText}>Choose a file</Text>
              <Text style={styles.pickBtnHint}>PDF, TXT, CSV, XLSX</Text>
            </>
          )}
        </TouchableOpacity>

        <Select label="Document type" value={docType} onChange={setDocType} options={DOC_TYPE_OPTIONS} />

        <LabeledInput
          label="Equipment ID (optional)"
          placeholder="e.g. P-101"
          value={equipmentId}
          onChangeText={setEquipmentId}
          autoCapitalize="characters"
        />

        <TouchableOpacity
          style={[styles.uploadBtn, (!pickedFile || uploading) && styles.uploadBtnDisabled]}
          onPress={upload}
          disabled={uploading || !pickedFile}
          activeOpacity={0.85}
        >
          <Text style={styles.uploadBtnText}>{uploading ? 'Processing…' : 'Upload & Index'}</Text>
        </TouchableOpacity>

        {uploadError && (
          <View style={{ marginTop: spacing.sm }}>
            <ErrorBanner error={uploadError} />
          </View>
        )}

        {job && (
          <View style={styles.jobBox}>
            <Spread>
              <Text style={styles.muted}>
                Job {job.job_id} — {job.status}
                {job.error_message ? ` · ${job.error_message}` : ''}
              </Text>
              <Text style={styles.jobPct}>{job.progress}%</Text>
            </Spread>
            <View style={styles.progressTrack}>
              <View style={[styles.progressFill, { width: `${job.progress}%` }]} />
            </View>
            {job.status === 'completed' && (
              <Text style={styles.successText}>
                ✓ Indexed — the new content is immediately queryable in Copilot.
              </Text>
            )}
          </View>
        )}
      </Card>

      <SectionTitle>Indexed documents</SectionTitle>
      {docs.loading && <Skeleton height={220} />}
      {docs.error && <ErrorBanner error={docs.error} onRetry={docs.reload} />}
      {docs.data?.documents.map((d) => (
        <TouchableOpacity key={d.doc_id} style={styles.docRow} onPress={() => openDetails(d.doc_id)} activeOpacity={0.7}>
          <View style={styles.docIconWrap}>
            <Text style={styles.docIcon}>📄</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.docName} numberOfLines={1}>
              {d.name}
            </Text>
            <Row style={{ marginTop: 6 }}>
              <Badge tone="blue">{docTypeLabel(d.doc_type)}</Badge>
              <Text style={styles.muted}>{formatDate(d.uploaded_at)}</Text>
              <Text style={styles.muted}>{d.chunk_count} chunks</Text>
            </Row>
          </View>
          <StatusBadge status={d.processing_status} />
          <Text style={styles.docChevron}>›</Text>
        </TouchableOpacity>
      ))}
      {docs.data && docs.data.documents.length === 0 && (
        <Card>
          <Text style={styles.muted}>No documents indexed yet.</Text>
        </Card>
      )}

      <Modal visible={!!selected} animationType="slide" transparent onRequestClose={() => setSelected(null)}>
        <View style={styles.modalOverlay}>
          <View style={styles.drawer}>
            <View style={styles.drawerHandle} />
            <TouchableOpacity style={styles.drawerClose} onPress={() => setSelected(null)}>
              <Text style={{ color: colors.textPrimary, fontSize: 16 }}>✕</Text>
            </TouchableOpacity>
            {selected && (
              <ScrollView showsVerticalScrollIndicator={false}>
                <Text style={styles.cardTitle}>{selected.name}</Text>
                <Row style={{ marginBottom: spacing.md }}>
                  <Badge tone="blue">{docTypeLabel(selected.doc_type)}</Badge>
                  <StatusBadge status={selected.processing_status} />
                  <Text style={styles.muted}>{selected.chunk_count} chunks</Text>
                </Row>
                {(
                  [
                    ['Equipment IDs', selected.entities.equipment_ids],
                    ['Dates', selected.entities.dates],
                    ['Parameters', selected.entities.parameters],
                    ['Regulations', selected.entities.regulations],
                    ['People', selected.entities.people],
                  ] as [string, string[]][]
                ).map(([label, items], i) => (
                  <View
                    key={label}
                    style={[
                      styles.detailGroup,
                      i === 0 && { borderTopWidth: 0, paddingTop: 0 },
                    ]}
                  >
                    <Text style={styles.detailLabel}>{label}</Text>
                    <Row>
                      {items && items.length > 0 ? (
                        items.map((it) => (
                          <Badge key={it} tone="gray">
                            {it}
                          </Badge>
                        ))
                      ) : (
                        <Text style={styles.faint}>none detected</Text>
                      )}
                    </Row>
                  </View>
                ))}
              </ScrollView>
            )}
          </View>
        </View>
      </Modal>
    </Screen>
  );
}

const styles = StyleSheet.create({
  cardTitle: { ...typography.h3, color: colors.textPrimary, marginBottom: spacing.md, fontWeight: '700' },
  pickBtn: {
    borderWidth: 1.5,
    borderStyle: 'dashed',
    borderColor: colors.borderLight,
    borderRadius: radius.md,
    padding: spacing.lg,
    marginBottom: spacing.md,
    alignItems: 'center',
    backgroundColor: colors.surface2,
  },
  pickBtnIcon: { fontSize: 22, marginBottom: 4 },
  pickBtnText: { color: colors.textPrimary, ...typography.small, fontWeight: '700' },
  pickBtnHint: { color: colors.textFaint, ...typography.small, fontSize: 11, marginTop: 2 },
  pickedRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, width: '100%' },
  pickedIconWrap: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: `${colors.accent}1A`,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pickedIcon: { fontSize: 16 },
  pickedName: { color: colors.textPrimary, ...typography.small, fontWeight: '600', flex: 1 },
  uploadBtn: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: 13,
    alignItems: 'center',
    marginTop: spacing.sm,
    ...Platform.select({
      ios: {
        shadowColor: colors.accent,
        shadowOpacity: 0.28,
        shadowRadius: 10,
        shadowOffset: { width: 0, height: 4 },
      },
      android: { elevation: 3 },
    }),
  },
  uploadBtnDisabled: { opacity: 0.5, ...Platform.select({ ios: { shadowOpacity: 0.08 }, android: { elevation: 0 } }) },
  uploadBtnText: { color: colors.white, fontWeight: '700', letterSpacing: 0.3 },
  muted: { ...typography.small, color: colors.textFaint },
  jobBox: {
    marginTop: spacing.md,
    backgroundColor: colors.surface2,
    borderRadius: radius.md,
    padding: spacing.sm,
  },
  jobPct: { ...typography.small, color: colors.textPrimary, fontWeight: '700' },
  progressTrack: {
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.surface3,
    marginTop: spacing.sm,
    overflow: 'hidden',
  },
  progressFill: { height: '100%', backgroundColor: colors.accent, borderRadius: 3 },
  successText: { ...typography.small, color: colors.green, marginTop: spacing.sm, fontWeight: '600' },
  docRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOpacity: 0.04,
        shadowRadius: 6,
        shadowOffset: { width: 0, height: 2 },
      },
      android: { elevation: 1 },
    }),
  },
  docIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: colors.surface2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  docIcon: { fontSize: 16 },
  docName: { color: colors.textPrimary, fontWeight: '700' },
  docChevron: { color: colors.textFaint, fontSize: 18, marginLeft: 2 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' },
  drawer: {
    backgroundColor: colors.bgElevated,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    padding: spacing.xl,
    maxHeight: '85%',
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOpacity: 0.2,
        shadowRadius: 20,
        shadowOffset: { width: 0, height: -4 },
      },
      android: { elevation: 8 },
    }),
  },
  drawerHandle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.border,
    alignSelf: 'center',
    marginBottom: spacing.sm,
  },
  drawerClose: { position: 'absolute', top: spacing.md, right: spacing.md, zIndex: 1 },
  detailGroup: {
    marginBottom: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  detailLabel: {
    ...typography.small,
    color: colors.textFaint,
    fontWeight: '700',
    marginBottom: 6,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    fontSize: 11,
  },
  faint: { color: colors.textFaint, ...typography.small },
});