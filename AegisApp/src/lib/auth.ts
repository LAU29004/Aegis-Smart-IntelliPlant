import * as Keychain from 'react-native-keychain';
import type { User } from './types';

// We store the JWT as the Keychain "password" and the serialized User object
// as the "username" field of the same generic-password entry. Keychain/Keystore
// encrypts at rest (iOS Secure Enclave / Android Keystore-backed), which is why
// this replaces localStorage from the web app — tokens must never sit in plain
// AsyncStorage on a mobile device.
const SERVICE = 'com.intelliplant.session';

export interface Session {
  token: string;
  user: User;
}

let cachedSession: Session | null | undefined;

export async function saveSession(token: string, user: User): Promise<void> {
  await Keychain.setGenericPassword(JSON.stringify(user), token, {
    service: SERVICE,
    accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
  cachedSession = { token, user };
}

export async function loadSession(): Promise<Session | null> {
  if (cachedSession !== undefined) return cachedSession;
  try {
    const creds = await Keychain.getGenericPassword({ service: SERVICE });
    if (!creds) {
      cachedSession = null;
      return null;
    }
    const user = JSON.parse(creds.username) as User;
    cachedSession = { token: creds.password, user };
    return cachedSession;
  } catch {
    cachedSession = null;
    return null;
  }
}

export async function clearSession(): Promise<void> {
  await Keychain.resetGenericPassword({ service: SERVICE });
  cachedSession = null;
}

export function getCachedToken(): string | null {
  return cachedSession?.token ?? null;
}

export function getCachedUser(): User | null {
  return cachedSession?.user ?? null;
}

// ---- Tiny event bus so the API layer can force a logout without importing
// navigation/context directly (avoids circular deps). ----
type Listener = () => void;
const unauthorizedListeners = new Set<Listener>();

export function onUnauthorized(listener: Listener): () => void {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

export function emitUnauthorized(): void {
  unauthorizedListeners.forEach((l) => l());
}
