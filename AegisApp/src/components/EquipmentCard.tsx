import React from 'react';
import { Platform, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { Equipment } from '../lib/types';
import { Badge, HealthRing, StatusBadge } from './ui';
import { colors, radius, spacing, typography } from '../theme/colors';

export default function EquipmentCard({ eq }: { eq: Equipment }) {
  // Untyped on purpose: this card renders both inside the Equipment stack
  // (which owns "EquipmentDetail" directly) and from sibling Drawer screens
  // like Dashboard. The nested-navigator call form — name the Drawer screen,
  // then the child screen + params — resolves correctly from either place,
  // since React Navigation bubbles an unrecognized top-level name up to the
  // parent navigator that owns it.
  const navigation = useNavigation<any>();

  function openDetail() {
    navigation.navigate('EquipmentStack', {
      screen: 'EquipmentDetail',
      params: { id: eq.equipment_id },
    });
  }

  return (
    <TouchableOpacity activeOpacity={0.75} style={styles.card} onPress={openDetail}>
      <HealthRing score={eq.health_score} />
      <View style={styles.meta}>
        <Text style={styles.id}>{eq.equipment_id}</Text>
        <Text style={styles.name} numberOfLines={1}>
          {eq.name}
        </Text>
        <Text style={styles.sub} numberOfLines={1}>
          {eq.type} · {eq.location}
        </Text>
        <View style={styles.footer}>
          <StatusBadge status={eq.status} />
          {eq.open_alerts_count > 0 && (
            <Badge tone={eq.open_alerts_count > 1 ? 'red' : 'amber'}>
              {eq.open_alerts_count} alert{eq.open_alerts_count > 1 ? 's' : ''}
            </Badge>
          )}
        </View>
      </View>
      <Text style={styles.chevron}>›</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    alignItems: 'center',
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOpacity: 0.08,
        shadowRadius: 10,
        shadowOffset: { width: 0, height: 4 },
      },
      android: { elevation: 2 },
    }),
  },
  meta: { flex: 1, minWidth: 0 },
  id: {
    ...typography.small,
    color: colors.accent,
    fontWeight: '700',
    marginBottom: 3,
    letterSpacing: 0.3,
  },
  name: { ...typography.h3, color: colors.textPrimary },
  sub: { ...typography.small, color: colors.textSecondary, marginTop: 2 },
  footer: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm },
  chevron: {
    fontSize: 22,
    color: colors.textFaint,
    fontWeight: '300',
    marginLeft: spacing.xs ?? 4,
  },
});