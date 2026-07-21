import React from 'react';
import { Alert, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { DrawerContentComponentProps } from '@react-navigation/drawer';
import Icon from 'react-native-vector-icons/Feather';
import { colors, radius, spacing, typography } from '../theme/colors';
import { useAuth } from '../context/AuthContext';


const NAV: { route: keyof import('../navigation/types').DrawerParamList; label: string; icon: string }[] = [
  { route: 'Dashboard', label: 'Dashboard', icon: 'grid' },
  { route: 'Copilot', label: 'Copilot', icon: 'message-circle' },
  { route: 'Documents', label: 'Documents', icon: 'file-text' },
  { route: 'EquipmentStack', label: 'Equipment', icon: 'settings' },
  { route: 'Compliance', label: 'Compliance', icon: 'check-square' },
  { route: 'Incidents', label: 'Incidents', icon: 'alert-triangle' },
  { route: 'Analytics', label: 'Analytics', icon: 'bar-chart-2' },
];

export default function Sidebar(props: DrawerContentComponentProps) {
  const { state, navigation } = props;
  const { user, logout } = useAuth();
  const activeRouteName = state.routeNames[state.index];

  const initials = (user?.name ?? '?')
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

        const ROLE_ACCESS = {
  Dashboard: ["Admin", "Plant Manager", "Engineer", "Safety Officer", "Field Technician"],
  Copilot: ["Admin", "Plant Manager", "Engineer", "Safety Officer", "Field Technician"],
  Documents: ["Admin", "Plant Manager", "Engineer", "Safety Officer", "Field Technician"],
  EquipmentStack: ["Admin", "Plant Manager", "Engineer", "Field Technician"],
  Compliance: ["Admin", "Plant Manager", "Safety Officer"],
  Incidents: ["Admin", "Plant Manager", "Engineer", "Safety Officer"],
  Analytics: ["Admin", "Plant Manager", "Safety Officer"],
} as const;

const visibleNav = NAV.filter(item => {
  console.log(item.route, ROLE_ACCESS[item.route]);

  return ROLE_ACCESS[item.route]?.includes(user?.role as any);
});
  function confirmLogout() {
    Alert.alert('Log out', 'You will need to sign in again to continue.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Log out', style: 'destructive', onPress: logout },
    ]);
  }

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <View style={styles.logoRow}>
        <View style={styles.logoBadge}>
          <Icon name="zap" size={18} color={colors.accent} />
        </View>
        <Text style={styles.logoText}>IntelliPlant</Text>
      </View>

      <View style={styles.nav}>
        <Text style={styles.sectionLabel}>WORKSPACE</Text>
        {visibleNav.map((item) => {
          const active = item.route === activeRouteName;
          return (
            <TouchableOpacity
              key={item.route}
              style={[styles.navLink, active && styles.navLinkActive]}
              activeOpacity={0.7}
              onPress={() => navigation.navigate(item.route as never)}
            >
              {active && <View style={styles.activeBar} />}
              <Icon
                name={item.icon}
                size={17}
                color={active ? colors.accent : colors.textFaint}
                style={styles.navIcon}
              />
              <Text style={[styles.navLabel, active && styles.navLabelActive]}>{item.label}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <View style={styles.footer}>
        <View style={styles.userBlock}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initials}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.userName} numberOfLines={1}>
              {user?.name}
            </Text>
            <Text style={styles.userRole} numberOfLines={1}>
              {user?.role}
            </Text>
          </View>
        </View>
        <TouchableOpacity style={styles.logoutBtn} onPress={confirmLogout} activeOpacity={0.75}>
          <Icon name="log-out" size={14} color={colors.textSecondary} />
          <Text style={styles.logoutText}>Logout</Text>
        </TouchableOpacity>
        <Text style={styles.version}>PLANT-01 · v1.0 prototype</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bgElevated },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    marginBottom: spacing.sm,
  },
  logoBadge: {
    width: 30,
    height: 30,
    borderRadius: radius.md,
    backgroundColor: colors.accentSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoText: { ...typography.h2, color: colors.textPrimary },

  nav: { flex: 1, paddingHorizontal: spacing.md, gap: 2 },
  sectionLabel: {
    color: colors.textFaint,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1,
    paddingHorizontal: spacing.md,
    marginBottom: 6,
    marginTop: 2,
  },
  navLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    borderRadius: radius.md,
    position: 'relative',
  },
  navLinkActive: { backgroundColor: colors.accentSoft },
  activeBar: {
    position: 'absolute',
    left: -spacing.md + 2,
    top: 8,
    bottom: 8,
    width: 3,
    borderRadius: 2,
    backgroundColor: colors.accent,
  },
  navIcon: { width: 20, textAlign: 'center' },
  navLabel: { ...typography.body, color: colors.textSecondary, fontWeight: '600' },
  navLabelActive: { color: colors.textPrimary },

  footer: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    padding: spacing.lg,
    gap: spacing.md,
  },
  userBlock: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.accentSoft,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.accent,
  },
  avatarText: { color: colors.accent, fontWeight: '700', fontSize: 13 },
  userName: { color: colors.textPrimary, fontWeight: '700', fontSize: 13 },
  userRole: { color: colors.textFaint, fontSize: 11, textTransform: 'capitalize' },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingVertical: 10,
  },
  logoutText: { color: colors.textPrimary, fontWeight: '700', fontSize: 13 },
  version: { color: colors.textFaint, fontSize: 11, textAlign: 'center' },
});