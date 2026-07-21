import React, { useEffect, useRef } from 'react';
import {
  ActivityIndicator,
  Animated,
  Easing,
  StyleSheet,
  Text,
  View,
  ViewStyle,
} from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { colors, radius, spacing, Tone, toneColor, toneSoft, typography } from '../theme/colors';
import { ApiError, BACKEND_DOWN_MESSAGE } from '../lib/api';

// ---------- Badges ----------

export function Badge({
  tone,
  children,
  dot = false,
  style,
}: {
  tone: Tone;
  children: React.ReactNode;
  dot?: boolean;
  style?: ViewStyle;
}) {
  const c = toneColor(tone);
  return (
    <View style={[styles.badge, { backgroundColor: toneSoft(tone) }, style]}>
      {dot && <View style={[styles.dot, { backgroundColor: c }]} />}
      <Text style={[styles.badgeText, { color: c }]}>{children}</Text>
    </View>
  );
}

export function statusTone(status: string): Tone {
  switch (status) {
    case 'healthy':
    case 'compliant':
    case 'indexed':
    case 'completed':
    case 'resolved':
      return 'green';
    case 'warning':
    case 'partial':
    case 'expiring':
    case 'medium':
    case 'processing':
    case 'queued':
      return 'amber';
    case 'critical':
    case 'gap':
    case 'high':
    case 'failed':
    case 'failure':
    case 'expired':
      return 'red';
    case 'info':
    case 'low':
    case 'open':
    case 'reported':
      return 'blue';
    default:
      return 'gray';
  }
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={statusTone(status)} dot>
      {status.replace(/_/g, ' ')}
    </Badge>
  );
}

export function confidenceTone(confidence: number): Tone {
  if (confidence >= 80) return 'green';
  if (confidence >= 60) return 'amber';
  return 'red';
}

export function ConfidenceBadge({
  confidence,
  level,
}: {
  confidence: number;
  level?: string;
}) {
  const label = level ?? (confidence >= 80 ? 'High' : confidence >= 60 ? 'Medium' : 'Low');
  return (
    <Badge tone={confidenceTone(confidence)} dot>
      {confidence}% {label.charAt(0).toUpperCase() + label.slice(1).toLowerCase()}
    </Badge>
  );
}

// ---------- Stat card ----------

export function StatCard({
  label,
  value,
  unit,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  unit?: string;
  tone?: Tone;
}) {
  const color = tone ? toneColor(tone) : colors.textPrimary;
  return (
    <View style={styles.statCard}>
      <Text style={styles.statLabel}>{label}</Text>
      <View style={styles.statValueRow}>
        <Text style={[styles.statValue, { color }]}>{value}</Text>
        {unit && <Text style={styles.statUnit}>{unit}</Text>}
      </View>
    </View>
  );
}

// ---------- Loading ----------

export function Spinner() {
  return <ActivityIndicator color={colors.accent} />;
}

export function Skeleton({
  height = 16,
  width = '100%' as number | `${number}%`,
  style,
}: {
  height?: number;
  width?: number | `${number}%`;
  style?: ViewStyle;
}) {
  const pulse = useRef(new Animated.Value(0.35)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 0.75,
          duration: 700,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0.35,
          duration: 700,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  return (
    <Animated.View
      style={[
        { height, width, borderRadius: radius.md, backgroundColor: colors.surface3, opacity: pulse },
        style,
      ]}
    />
  );
}

export function SkeletonCards({ count = 3, height = 90 }: { count?: number; height?: number }) {
  return (
    <View style={styles.grid2}>
      {Array.from({ length: count }).map((_, i) => (
        <View key={i} style={styles.gridHalf}>
          <Skeleton height={height} />
        </View>
      ))}
    </View>
  );
}

// ---------- Errors ----------

export function ErrorBanner({
  error,
  onRetry,
}: {
  error: ApiError | Error | string;
  onRetry?: () => void;
}) {
  const isDown =
    error instanceof ApiError
      ? error.backendDown
      : typeof error === 'string'
        ? error === BACKEND_DOWN_MESSAGE
        : false;
  const message = typeof error === 'string' ? error : error.message;

  return (
    <View style={[styles.errorBanner, !isDown && styles.errorBannerHard]}>
      <Text style={styles.errorIcon}>{isDown ? '⚠' : '✕'}</Text>
      <Text style={styles.errorText}>
        {isDown ? (
          <>Backend not running — start it with `uvicorn app.main:app`</>
        ) : (
          message
        )}
      </Text>
      {onRetry && (
        <Text style={styles.retryBtn} onPress={onRetry}>
          Retry
        </Text>
      )}
    </View>
  );
}

// ---------- Health ring ----------

export function HealthRing({ score, size = 'sm' }: { score: number; size?: 'sm' | 'lg' }) {
  const color = score >= 80 ? colors.green : score >= 60 ? colors.amber : colors.red;
  const px = size === 'lg' ? 84 : 56;
  const stroke = size === 'lg' ? 7 : 5;
  const r = (px - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, score));
  return (
    <View style={{ width: px, height: px, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={px} height={px} style={StyleSheet.absoluteFill}>
        <Circle
          cx={px / 2}
          cy={px / 2}
          r={r}
          fill="none"
          stroke={colors.surface3}
          strokeWidth={stroke}
        />
        <Circle
          cx={px / 2}
          cy={px / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${circ}, ${circ}`}
          strokeDashoffset={circ * (1 - clamped / 100)}
          rotation={-90}
          origin={`${px / 2}, ${px / 2}`}
        />
      </Svg>
      <Text style={{ color, fontWeight: '700', fontSize: size === 'lg' ? 20 : 15 }}>
        {clamped}
      </Text>
    </View>
  );
}

// ---------- Toast ----------

export function Toast({ message, kind = 'success' }: { message: string; kind?: 'success' | 'error' }) {
  const opacity = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(opacity, { toValue: 1, duration: 200, useNativeDriver: true }).start();
  }, [opacity]);
  return (
    <Animated.View
      style={[
        styles.toast,
        { backgroundColor: kind === 'error' ? colors.red : colors.green, opacity },
      ]}
    >
      <Text style={styles.toastText}>{message}</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radius.pill,
    gap: 6,
  },
  badgeText: { ...typography.small, fontWeight: '600', textTransform: 'capitalize' },
  dot: { width: 6, height: 6, borderRadius: 3 },

  statCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    flex: 1,
  },
  statLabel: { ...typography.small, color: colors.textFaint, marginBottom: 6 },
  statValueRow: { flexDirection: 'row', alignItems: 'flex-end', gap: 4 },
  statValue: { fontSize: 26, fontWeight: '700' },
  statUnit: { fontSize: 14, color: colors.textFaint, marginBottom: 3 },

  grid2: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -6 },
  gridHalf: { width: '50%', padding: 6 },

  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.amberSoft,
    borderWidth: 1,
    borderColor: colors.amber,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  errorBannerHard: { backgroundColor: colors.redSoft, borderColor: colors.red },
  errorIcon: { fontSize: 16, color: colors.textPrimary },
  errorText: { ...typography.small, color: colors.textPrimary, flex: 1 },
  retryBtn: { color: colors.accent,...typography.small },

  toast: {
    position: 'absolute',
    bottom: 24,
    left: 20,
    right: 20,
    borderRadius: radius.md,
    padding: spacing.md,
    shadowColor: '#000',
    shadowOpacity: 0.3,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 6,
  },
  toastText: { color: colors.white, fontWeight: '600', textAlign: 'center' },
});
