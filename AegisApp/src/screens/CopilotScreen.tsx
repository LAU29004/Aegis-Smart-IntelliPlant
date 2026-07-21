import React, { useRef, useState } from 'react';
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Markdown from '../components/Markdown';
import { api, ApiError } from '../lib/api';
import type { AskResponse } from '../lib/types';
import { ConfidenceBadge, ErrorBanner } from '../components/ui';
import { colors, radius, spacing, typography } from '../theme/colors';

interface ChatMsg {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  meta?: AskResponse;
}

const STARTERS = [
  'What failed on Pump P-101 last month and how was it fixed?',
  'Boiler B-02 safe shutdown procedure',
  'Show all bearing failures on P-101',
  'Which certifications expire in the next 60 days?',
];

export default function CopilotScreen() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [equipmentFilter, setEquipmentFilter] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [inputFocused, setInputFocused] = useState(false);
  const listRef = useRef<FlatList<ChatMsg>>(null);

  async function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    setInput('');
    setError(null);
    const userMsg: ChatMsg = { id: `u-${Date.now()}`, role: 'user', content: q };
    const next = [...messages, userMsg];
    setMessages(next);
    setBusy(true);
    requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
    try {
      const res = await api.post<AskResponse>('/query/ask', {
        query: q,
        conversation_history: next.slice(-10).map((m) => ({ role: m.role, content: m.content })),
        filters: equipmentFilter ? { equipment_id: equipmentFilter } : {},
      });
      setMessages((cur) => [
        ...cur,
        { id: res.query_id, role: 'assistant', content: res.answer, meta: res },
      ]);
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError('Query failed'));
      setMessages((cur) => cur.slice(0, -1));
      setInput(q);
    } finally {
      setBusy(false);
      requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
    }
  }

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={90}
      >
        <View style={styles.filterBar}>
          <TouchableOpacity style={styles.filterToggleBtn} onPress={() => setShowFilters((s) => !s)} activeOpacity={0.7}>
            <Text style={styles.filterToggle}>
              Filters {equipmentFilter ? `· ${equipmentFilter}` : ''}
            </Text>
            <Text style={styles.filterChevron}>{showFilters ? '▲' : '▼'}</Text>
          </TouchableOpacity>
          {showFilters && (
            <TextInput
              style={styles.filterInput}
              placeholder="Equipment ID (e.g. P-101)"
              placeholderTextColor={colors.textFaint}
              value={equipmentFilter}
              onChangeText={setEquipmentFilter}
            />
          )}
        </View>

        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(m) => m.id}
          contentContainerStyle={styles.list}
          ListEmptyComponent={
            <View style={styles.hero}>
              <View style={styles.heroIconWrap}>
                <Text style={styles.heroIcon}>✦</Text>
              </View>
              <Text style={styles.heroTitle}>Ask IntelliPlant anything</Text>
              <Text style={styles.heroSub}>
                Every manual, log, SOP, inspection and incident report — one question away.
              </Text>
              {STARTERS.map((s) => (
                <TouchableOpacity key={s} style={styles.starterCard} onPress={() => send(s)} activeOpacity={0.7}>
                  <Text style={styles.starterText}>{s}</Text>
                  <Text style={styles.starterArrow}>›</Text>
                </TouchableOpacity>
              ))}
            </View>
          }
          renderItem={({ item, index }) => (
            <View style={[styles.msgRow, item.role === 'user' && styles.msgRowUser]}>
              <View
                style={[
                  styles.bubble,
                  item.role === 'user' ? styles.bubbleUser : styles.bubbleAssistant,
                ]}
              >
                {item.role === 'assistant' ? (
                  <>
                    <Markdown text={item.content} />
                    {item.meta && (
                      <>
                        <View style={styles.metaRow}>
                          <ConfidenceBadge
                            confidence={item.meta.confidence}
                            level={item.meta.confidence_level}
                          />
                          {item.meta.sources.map((s) => (
                            <View key={s.chunk_id} style={styles.sourceChip}>
                              <Text style={styles.sourceChipText} numberOfLines={1}>
                                📄 {s.document} · p.{s.page}
                              </Text>
                            </View>
                          ))}
                        </View>
                        {item.meta.confidence < 60 && (
                          <View style={styles.lowConfidenceBanner}>
                            <Text style={styles.lowConfidence}>
                              ⚠ Low confidence — verify with the source document.
                            </Text>
                          </View>
                        )}
                        {index === messages.length - 1 && item.meta.follow_up_suggestions.length > 0 && (
                          <View style={styles.followups}>
                            {item.meta.follow_up_suggestions.map((f) => (
                              <TouchableOpacity key={f} style={styles.pill} onPress={() => send(f)} activeOpacity={0.7}>
                                <Text style={styles.pillText}>{f}</Text>
                              </TouchableOpacity>
                            ))}
                          </View>
                        )}
                      </>
                    )}
                  </>
                ) : (
                  <Text style={styles.userText}>{item.content}</Text>
                )}
              </View>
            </View>
          )}
          ListFooterComponent={
            busy ? (
              <View style={styles.msgRow}>
                <View style={[styles.bubble, styles.bubbleAssistant, styles.typingBubble]}>
                  <View style={styles.typingDot} />
                  <View style={[styles.typingDot, styles.typingDotMid]} />
                  <View style={styles.typingDot} />
                </View>
              </View>
            ) : null
          }
        />

        {error && (
          <View style={{ paddingHorizontal: spacing.lg }}>
            <ErrorBanner error={error} />
          </View>
        )}

        <View style={styles.inputBar}>
          <View style={[styles.inputWrap, inputFocused && styles.inputWrapFocused]}>
            <TextInput
              style={styles.input}
              placeholder="Ask about equipment, procedures, failures, compliance…"
              placeholderTextColor={colors.textFaint}
              value={input}
              onChangeText={setInput}
              onSubmitEditing={() => send()}
              onFocus={() => setInputFocused(true)}
              onBlur={() => setInputFocused(false)}
              editable={!busy}
              multiline
            />
          </View>
          <TouchableOpacity
            style={[styles.sendBtn, (busy || !input.trim()) && styles.sendBtnDisabled]}
            onPress={() => send()}
            disabled={busy || !input.trim()}
            activeOpacity={0.8}
          >
            <Text style={styles.sendText}>➤</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  filterBar: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  filterToggleBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start' },
  filterToggle: { color: colors.textSecondary, ...typography.small, fontWeight: '600' },
  filterChevron: { color: colors.textFaint, fontSize: 10 },
  filterInput: {
    marginTop: spacing.sm,
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    color: colors.textPrimary,
  },
  list: { padding: spacing.lg, flexGrow: 1 },
  hero: { alignItems: 'center', paddingVertical: spacing.xl, gap: spacing.sm },
  heroIconWrap: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: `${colors.accent}1A`,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.xs ?? 4,
  },
  heroIcon: { fontSize: 26, color: colors.accent },
  heroTitle: { ...typography.h2, color: colors.textPrimary, fontWeight: '700' },
  heroSub: { ...typography.body, color: colors.textSecondary, textAlign: 'center', marginBottom: spacing.md },
  starterCard: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOpacity: 0.05,
        shadowRadius: 6,
        shadowOffset: { width: 0, height: 2 },
      },
      android: { elevation: 1 },
    }),
  },
  starterText: { color: colors.textPrimary, ...typography.small, flex: 1 },
  starterArrow: { color: colors.textFaint, fontSize: 18, marginLeft: spacing.sm },

  msgRow: { marginBottom: spacing.md, alignItems: 'flex-start' },
  msgRowUser: { alignItems: 'flex-end' },
  bubble: { maxWidth: '88%', borderRadius: radius.lg, padding: spacing.md },
  bubbleAssistant: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderBottomLeftRadius: 6,
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
  bubbleUser: {
    backgroundColor: colors.accent,
    borderBottomRightRadius: 6,
    ...Platform.select({
      ios: {
        shadowColor: colors.accent,
        shadowOpacity: 0.2,
        shadowRadius: 8,
        shadowOffset: { width: 0, height: 3 },
      },
      android: { elevation: 2 },
    }),
  },
  userText: { color: colors.white, ...typography.body },

  metaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: spacing.sm },
  sourceChip: {
    backgroundColor: colors.surface3,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    maxWidth: 220,
  },
  sourceChipText: { ...typography.small, color: colors.textSecondary },
  lowConfidenceBanner: {
    marginTop: 8,
    backgroundColor: `${colors.amber}14`,
    borderRadius: radius.sm,
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderLeftWidth: 3,
    borderLeftColor: colors.amber,
  },
  lowConfidence: { ...typography.small, color: colors.amber },
  followups: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: spacing.sm },
  pill: {
    borderWidth: 1,
    borderColor: colors.accent,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
  },
  pillText: { color: colors.accent, ...typography.small, fontWeight: '600' },

  typingBubble: { flexDirection: 'row', gap: 4, paddingVertical: 14, alignItems: 'center' },
  typingDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.textFaint,
    opacity: 0.5,
  },
  typingDotMid: { opacity: 0.9 },

  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: spacing.sm,
    padding: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  inputWrap: {
    flex: 1,
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
  },
  inputWrapFocused: {
    borderColor: colors.accent,
    ...Platform.select({
      ios: {
        shadowColor: colors.accent,
        shadowOpacity: 0.15,
        shadowRadius: 6,
        shadowOffset: { width: 0, height: 0 },
      },
      android: { elevation: 1 },
    }),
  },
  input: {
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    color: colors.textPrimary,
    maxHeight: 100,
  },
  sendBtn: {
    backgroundColor: colors.accent,
    width: 44,
    height: 44,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    ...Platform.select({
      ios: {
        shadowColor: colors.accent,
        shadowOpacity: 0.3,
        shadowRadius: 8,
        shadowOffset: { width: 0, height: 3 },
      },
      android: { elevation: 2 },
    }),
  },
  sendBtnDisabled: { opacity: 0.5, ...Platform.select({ ios: { shadowOpacity: 0.1 }, android: { elevation: 0 } }) },
  sendText: { color: colors.white, fontSize: 18 },
});