import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { clearSession as clearStoredSession, loadSession, onUnauthorized, saveSession } from '../lib/auth';
import type { User } from '../lib/types';
import { GoogleSignin } from '@react-native-google-signin/google-signin';

interface AuthContextValue {
  user: User | null;
  initializing: boolean;
  isAuthenticated: boolean;
  login: (token: string, user: User) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    let mounted = true;
loadSession().then((session) => {
  if (!mounted) return;

  setUser(session?.user ?? null);
  setInitializing(false);
});
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    return onUnauthorized(() => {
      setUser(null);
    });
  }, []);

  const login = useCallback(async (token: string, u: User) => {
    await saveSession(token, u);
    setUser(u);
  }, []);

const logout = useCallback(async () => {
  try {
    if (await GoogleSignin.hasPreviousSignIn()) {
      await GoogleSignin.revokeAccess();
      await GoogleSignin.signOut();
    }
  } catch (err) {
    console.warn('Google sign out failed:', err);
  }

  await clearStoredSession();
  setUser(null);
}, []);

  const value = useMemo(
    () => ({ user, initializing, isAuthenticated: !!user, login, logout }),
    [user, initializing, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
