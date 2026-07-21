import React, { useRef, useState } from 'react';
import {
  ActivityIndicator,
  Animated,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/Feather';
import { api, ApiError } from '../lib/api';
import type { LoginResponse } from '../lib/types';
import { useAuth } from '../context/AuthContext';
import { ErrorBanner } from '../components/ui';
import { colors, radius, spacing, typography } from '../theme/colors';
import { GoogleSignin } from '@react-native-google-signin/google-signin';
import NotificationService from "../services/notificationService";
import DeviceInfo from "react-native-device-info";
export default function LoginScreen() {
  const { login } = useAuth();
  const [email, setEmail] = useState('engineer@intelliplant.io');
  const [password, setPassword] = useState('demo123');
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [focusedField, setFocusedField] = useState<'email' | 'password' | null>(null);

  const fade = useRef(new Animated.Value(0)).current;
  const slide = useRef(new Animated.Value(16)).current;
  const buttonScale = useRef(new Animated.Value(1)).current;
  const googleScale = useRef(new Animated.Value(1)).current;

  React.useEffect(() => {
    Animated.parallel([
      Animated.timing(fade, { toValue: 1, duration: 420, useNativeDriver: true }),
      Animated.timing(slide, { toValue: 0, duration: 420, useNativeDriver: true }),
    ]).start();
  }, []);

  function pressIn(scale: Animated.Value) {
    Animated.spring(scale, { toValue: 0.97, useNativeDriver: true, speed: 40 }).start();
  }
  function pressOut(scale: Animated.Value) {
    Animated.spring(scale, { toValue: 1, useNativeDriver: true, speed: 40 }).start();
  }

async function loginWithGoogle() {
  try {
    console.log("1. Starting Google Sign-In");

    await GoogleSignin.hasPlayServices();
    console.log("2. Play Services OK");

    const userInfo = await GoogleSignin.signIn();
    console.log("3. User Info:", userInfo);

    const idToken = userInfo.data?.idToken;
    console.log("4. ID Token:", idToken);

    if (!idToken) {
      throw new Error("No Google ID token received");
    }

    console.log("5. Calling backend...");

    const res = await api.post<LoginResponse>(
      "/auth/google",
      {
        id_token: idToken,
      }
    );

    console.log("6. Backend response:", res);

    await login(res.access_token, res.user);

// Request notification permission
const granted = await NotificationService.requestPermission();

if (granted) {
  const token = await NotificationService.getToken();

  await api.post("/notifications/register", {
    token,
    device_id: DeviceInfo.getUniqueIdSync(),
    platform: "android",
    app_version: DeviceInfo.getVersion(),
  });
}
  } catch (err) {
    console.log("GOOGLE SIGN-IN ERROR:", err);
  }
}

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<LoginResponse>('/auth/login', { email, password });
      await login(res.access_token, res.user);

const granted = await NotificationService.requestPermission();

if (granted) {
  const token = await NotificationService.getToken();

  await api.post("/notifications/register", {
    token,
    device_id: DeviceInfo.getUniqueIdSync(),
    platform: "android",
    app_version: DeviceInfo.getVersion(),
  });
}} catch (err) {
      setError(err instanceof ApiError ? err : new ApiError('Network error'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.wrap}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.flex}
      >
        <ScrollView
          contentContainerStyle={styles.center}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Ambient glow accents */}
          <View pointerEvents="none" style={styles.glowTop} />
          <View pointerEvents="none" style={styles.glowBottom} />
          <View pointerEvents="none" style={styles.glowAccent} />

          <Animated.View
            style={[
              styles.card,
              { opacity: fade, transform: [{ translateY: slide }] },
            ]}
          >
            <View style={styles.logoBadge}>
              <Icon name="zap" size={26} color={colors.accent} />
            </View>
            <Text style={styles.logoText}>IntelliPlant</Text>
            <Text style={styles.tagline}>Industrial Knowledge Intelligence Platform</Text>

            {error && (
              <View style={styles.errorWrap}>
                <ErrorBanner error={error} />
              </View>
            )}

            <View style={styles.field}>
              <Text style={styles.label}>Email</Text>
              <View
                style={[
                  styles.inputWrap,
                  focusedField === 'email' && styles.inputWrapFocused,
                ]}
              >
                <Icon
                  name="mail"
                  size={16}
                  color={focusedField === 'email' ? colors.accent : colors.textFaint}
                  style={styles.inputIcon}
                />
                <TextInput
                  style={styles.input}
                  value={email}
                  onChangeText={setEmail}
                  onFocus={() => setFocusedField('email')}
                  onBlur={() => setFocusedField(null)}
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="email-address"
                  placeholder="you@company.com"
                  placeholderTextColor={colors.textFaint}
                />
              </View>
            </View>

            <View style={styles.field}>
              <Text style={styles.label}>Password</Text>
              <View
                style={[
                  styles.inputWrap,
                  focusedField === 'password' && styles.inputWrapFocused,
                ]}
              >
                <Icon
                  name="lock"
                  size={16}
                  color={focusedField === 'password' ? colors.accent : colors.textFaint}
                  style={styles.inputIcon}
                />
                <TextInput
                  style={[styles.input, styles.inputFlex]}
                  value={password}
                  onChangeText={setPassword}
                  onFocus={() => setFocusedField('password')}
                  onBlur={() => setFocusedField(null)}
                  secureTextEntry={!showPassword}
                  placeholder="••••••••"
                  placeholderTextColor={colors.textFaint}
                />
                <Pressable
                  onPress={() => setShowPassword((v) => !v)}
                  hitSlop={10}
                  style={styles.eyeButton}
                >
                  <Icon
                    name={showPassword ? 'eye-off' : 'eye'}
                    size={18}
                    color={colors.textSecondary}
                  />
                </Pressable>
              </View>
            </View>

            <Animated.View style={{ width: '100%', transform: [{ scale: buttonScale }] }}>
              <TouchableOpacity
                style={[styles.button, busy && styles.buttonBusy]}
                onPress={submit}
                onPressIn={() => pressIn(buttonScale)}
                onPressOut={() => pressOut(buttonScale)}
                disabled={busy || googleBusy}
                activeOpacity={0.9}
              >
                {busy ? (
                  <View style={styles.buttonRow}>
                    <ActivityIndicator color={colors.white} size="small" />
                    <Text style={styles.buttonText}>Signing in…</Text>
                  </View>
                ) : (
                  <View style={styles.buttonRow}>
                    <Text style={styles.buttonText}>Sign in</Text>
                    <Icon name="arrow-right" size={16} color={colors.white} />
                  </View>
                )}
              </TouchableOpacity>
            </Animated.View>

            <View style={styles.orRow}>
              <View style={styles.orLine} />
              <Text style={styles.orText}>OR CONTINUE WITH</Text>
              <View style={styles.orLine} />
            </View>

<TouchableOpacity
  style={[styles.googleButton, googleBusy && { opacity: 0.7 }]}
  disabled={busy || googleBusy}
  onPress={loginWithGoogle}
>
  {googleBusy ? (
    <ActivityIndicator color={colors.accent} />
  ) : (
    <>
      <Icon name="chrome" size={18} color="#EA4335" />
      <Text style={styles.googleText}>Continue with Google</Text>
    </>
  )}
</TouchableOpacity>

            <View style={styles.divider} />

            <View style={styles.hint}>
              <Text style={styles.hintLabel}>DEMO ACCOUNTS</Text>
              <Text style={styles.hintText}>engineer@intelliplant.io · demo123</Text>
              <Text style={styles.hintTextFaint}>manager · safety · tech · admin — same domain</Text>
            </View>
          </Animated.View>

          <Text style={styles.footer}>IntelliPlant · Multi-Agent Industrial Intelligence</Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg },
  flex: { flex: 1 },
  center: {
    flexGrow: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    paddingVertical: spacing.xl * 1.5,
  },
  glowTop: {
    position: 'absolute',
    top: -120,
    right: -80,
    width: 260,
    height: 260,
    borderRadius: 260,
    backgroundColor: colors.accent,
    opacity: 0.08,
  },
  glowBottom: {
    position: 'absolute',
    bottom: -140,
    left: -100,
    width: 280,
    height: 280,
    borderRadius: 280,
    backgroundColor: colors.accent,
    opacity: 0.06,
  },
  glowAccent: {
    position: 'absolute',
    top: '35%',
    left: '50%',
    marginLeft: -150,
    width: 300,
    height: 300,
    borderRadius: 300,
    backgroundColor: colors.accent,
    opacity: 0.04,
  },
  card: {
    width: '100%',
    maxWidth: 420,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.xl,
    padding: spacing.xl,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.2,
    shadowRadius: 28,
    elevation: 8,
  },
  logoBadge: {
    width: 56,
    height: 56,
    borderRadius: radius.xl,
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
    shadowColor: colors.accent,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 10,
  },
  logoText: { ...typography.h1, color: colors.textPrimary },
  tagline: {
    ...typography.small,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 4,
    marginBottom: spacing.xl,
  },
  errorWrap: { width: '100%', marginBottom: spacing.md },
  field: { width: '100%', marginBottom: spacing.md },
  label: { ...typography.small, color: colors.textSecondary, marginBottom: 6, fontWeight: '600' },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
  },
  inputWrapFocused: {
    borderColor: colors.accent,
    shadowColor: colors.accent,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 2,
  },
  inputIcon: { marginRight: 8 },
  input: {
    flex: 1,
    paddingVertical: 12,
    color: colors.textPrimary,
    fontSize: 15,
  },
  inputFlex: { flex: 1 },
  eyeButton: { paddingLeft: spacing.sm, paddingVertical: 6 },
  button: {
    width: '100%',
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.sm,
    shadowColor: colors.accent,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35,
    shadowRadius: 12,
    elevation: 4,
  },
  buttonBusy: { opacity: 0.75 },
  buttonRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  buttonText: { color: colors.white, fontWeight: '700', fontSize: 15 },
  orRow: {
    flexDirection: 'row',
    alignItems: 'center',
    width: '100%',
    marginTop: spacing.lg,
    marginBottom: spacing.md,
    gap: 10,
  },
  orLine: { flex: 1, height: 1, backgroundColor: colors.border },
  orText: {
    ...typography.small,
    color: colors.textFaint,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1,
  },
  googleButtonText: { color: colors.textPrimary, fontWeight: '600', fontSize: 15 },
  divider: {
    width: '100%',
    height: 1,
    backgroundColor: colors.border,
    marginTop: spacing.lg,
    marginBottom: spacing.md,
  },
  hint: { width: '100%', alignItems: 'center', gap: 3 },
  hintLabel: {
    ...typography.small,
    color: colors.textFaint,
    letterSpacing: 1,
    fontSize: 10,
    fontWeight: '700',
    marginBottom: 2,
  },
  hintText: { ...typography.small, color: colors.textSecondary, textAlign: 'center' },
  hintTextFaint: { ...typography.small, color: colors.textFaint, textAlign: 'center', fontSize: 12 },
  footer: {
    ...typography.small,
    color: colors.textFaint,
    marginTop: spacing.xl,
    textAlign: 'center',
  },
  googleButton: {
  width: '100%',
  flexDirection: 'row',
  justifyContent: 'center',
  alignItems: 'center',
  borderWidth: 1,
  borderColor: colors.border,
  borderRadius: radius.md,
  paddingVertical: 14,
  marginTop: spacing.md,
  backgroundColor: colors.surface,
},

googleText: {
  marginLeft: 10,
  color: colors.textPrimary,
  fontWeight: '600',
  fontSize: 15,
},
});