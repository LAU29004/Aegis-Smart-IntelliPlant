import React, { useMemo, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/Feather';
import { useApi } from '../lib/api';
import type { Equipment } from '../lib/types';
import EquipmentCard from '../components/EquipmentCard';
import { ErrorBanner, Skeleton } from '../components/ui';
import { colors, radius, spacing, typography } from '../theme/colors';

export default function EquipmentListScreen() {
  const { data, loading, error, reload } = useApi<{ equipment: Equipment[] }>('/equipment');
  const [search, setSearch] = useState('');
  const [focused, setFocused] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const filtered = useMemo(
    () =>
      (data?.equipment ?? []).filter((eq) => {
        const q = search.toLowerCase();
        return (
          eq.equipment_id.toLowerCase().includes(q) ||
          eq.name.toLowerCase().includes(q) ||
          eq.type.toLowerCase().includes(q)
        );
      }),
    [data, search],
  );

  async function onRefresh() {
    setRefreshing(true);
    await reload();
    setRefreshing(false);
  }

  const hasEquipment = !!data && data.equipment.length > 0;
  const showEmpty = !loading && !!data;

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={styles.title}>Equipment</Text>
          {hasEquipment && (
            <View style={styles.countPill}>
              <Text style={styles.countPillText}>{filtered.length}</Text>
            </View>
          )}
        </View>

        <View style={[styles.searchWrap, focused && styles.searchWrapFocused]}>
          <Icon name="search" size={18} color={focused ? colors.accent : colors.textFaint} style={styles.searchIcon} />
          <TextInput
            style={styles.search}
            placeholder="Search by ID, name or type…"
            placeholderTextColor={colors.textFaint}
            value={search}
            onChangeText={setSearch}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            returnKeyType="search"
            clearButtonMode="never"
          />
          {search.length > 0 && (
            <TouchableOpacity
              onPress={() => setSearch('')}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              style={styles.clearBtn}
            >
              <Icon name="close-circle" size={18} color={colors.textFaint} />
            </TouchableOpacity>
          )}
        </View>
      </View>

      {loading && (
        <View style={{ paddingHorizontal: spacing.lg }}>
          <Skeleton height={90} style={{ marginBottom: spacing.md }} />
          <Skeleton height={90} style={{ marginBottom: spacing.md }} />
          <Skeleton height={90} />
        </View>
      )}
      {error && (
        <View style={{ paddingHorizontal: spacing.lg }}>
          <ErrorBanner error={error} onRetry={reload} />
        </View>
      )}

      <FlatList
        data={filtered}
        keyExtractor={(eq) => eq.equipment_id}
        contentContainerStyle={filtered.length === 0 ? styles.listEmpty : styles.list}
        ItemSeparatorComponent={() => <View style={{ height: spacing.md }} />}
        renderItem={({ item }) => <EquipmentCard eq={item} />}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />
        }
        ListEmptyComponent={
          showEmpty ? (
            <View style={styles.emptyState}>
              <View style={styles.emptyIconWrap}>
                <Icon
                  name={hasEquipment ? 'search-outline' : 'construct-outline'}
                  size={28}
                  color={colors.textFaint}
                />
              </View>
              <Text style={styles.emptyTitle}>
                {hasEquipment ? 'No matches found' : 'No equipment yet'}
              </Text>
              <Text style={styles.emptyBody}>
                {hasEquipment
                  ? `Nothing matches "${search}". Try a different ID, name or type.`
                  : 'Equipment you add will show up here.'}
              </Text>
              {hasEquipment && search.length > 0 && (
                <TouchableOpacity style={styles.emptyClearBtn} onPress={() => setSearch('')}>
                  <Icon name="close" size={14} color={colors.accent} />
                  <Text style={styles.emptyClearBtnText}>Clear search</Text>
                </TouchableOpacity>
              )}
            </View>
          ) : null
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },

  header: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.md },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: spacing.md },
  title: { ...typography.h2, color: colors.textPrimary },
  countPill: {
    backgroundColor: colors.surface2,
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 2,
  },
  countPillText: { ...typography.small, color: colors.textSecondary, fontWeight: '700' },

  searchWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
  },
  searchWrapFocused: {
    borderColor: colors.accent,
    shadowColor: colors.accent,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 1,
  },
  searchIcon: { marginRight: 8 },
  search: {
    flex: 1,
    paddingVertical: 11,
    color: colors.textPrimary,
    ...typography.body,
  },
  clearBtn: { marginLeft: 6, padding: 2 },

  list: { padding: spacing.lg, paddingTop: 0 },
  listEmpty: { flexGrow: 1, padding: spacing.lg, paddingTop: 0 },

  emptyState: { alignItems: 'center', justifyContent: 'center', paddingTop: spacing.xl ?? 32, gap: 6 },
  emptyIconWrap: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.surface2,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
  },
  emptyTitle: { ...typography.body, color: colors.textPrimary, fontWeight: '700' },
  emptyBody: {
    ...typography.small,
    color: colors.textFaint,
    textAlign: 'center',
    maxWidth: 260,
    marginTop: 2,
  },
  emptyClearBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: spacing.md,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.accentSoft,
  },
  emptyClearBtnText: { ...typography.small, color: colors.accent, fontWeight: '700' },
});