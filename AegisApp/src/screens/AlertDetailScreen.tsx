import React from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { useRoute, RouteProp } from '@react-navigation/native';

import { EquipmentStackParamList } from '../navigation/types';
import { useApi } from '../lib/api';
import { colors, spacing, radius, typography } from '../theme/colors';

type AlertRouteProp = RouteProp<
  EquipmentStackParamList,
  'AlertDetail'
>;

export default function AlertDetailScreen() {
  const route = useRoute<AlertRouteProp>();

  const { id } = route.params;

  const {
    data,
    loading,
    error,
  } = useApi<any>(`/alerts/${id}`);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator
          size="large"
          color={colors.accent}
        />
      </View>
    );
  }

  if (error || !data) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>
          Unable to load alert.
        </Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={{
        paddingBottom: spacing.xl,
      }}
    >
      <Text style={styles.title}>
        🚨 {data.title}
      </Text>

      <View style={styles.card}>
        <Item
          label="Alert ID"
          value={data.alert_id}
        />

        <Item
          label="Equipment"
          value={data.equipment_id}
        />

        <Item
          label="Severity"
          value={data.severity.toUpperCase()}
        />

        <Item
          label="Status"
          value={data.status}
        />

        <Item
          label="Triggered At"
          value={data.triggered_at}
        />
      </View>

      <View style={styles.card}>
        <Section
          title="Description"
          text={data.description}
        />

        <Section
          title="Recommended Action"
          text={data.recommended_action}
        />

        <Section
          title="AI Explanation"
          text={data.ai_explanation}
        />
      </View>
    </ScrollView>
  );
}

function Item({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <View style={styles.item}>
      <Text style={styles.label}>
        {label}
      </Text>

      <Text style={styles.value}>
        {value}
      </Text>
    </View>
  );
}

function Section({
  title,
  text,
}: {
  title: string;
  text: string;
}) {
  return (
    <View style={{ marginBottom: spacing.lg }}>
      <Text style={styles.sectionTitle}>
        {title}
      </Text>

      <Text style={styles.sectionText}>
        {text}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
    padding: spacing.lg,
  },

  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.bg,
  },

  title: {
    ...typography.h1,
    color: colors.textPrimary,
    marginBottom: spacing.lg,
  },

  card: {
    backgroundColor: colors.bgElevated,
    borderRadius: radius.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },

  item: {
    marginBottom: spacing.md,
  },

  label: {
    color: colors.textFaint,
    fontSize: 12,
    marginBottom: 4,
  },

  value: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: '600',
  },

  sectionTitle: {
    color: colors.accent,
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 8,
  },

  sectionText: {
    color: colors.textSecondary,
    lineHeight: 22,
    fontSize: 15,
  },

  error: {
    color: colors.textPrimary,
    fontSize: 16,
  },
});