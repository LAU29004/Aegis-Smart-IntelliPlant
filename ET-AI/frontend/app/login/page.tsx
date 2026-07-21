"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError, storeSession } from "@/lib/api";
import type { LoginResponse } from "@/lib/types";
import { ErrorBanner } from "@/components/ui";
import { GoogleLogin } from "@react-oauth/google";
export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("engineer@intelliplant.io");
  const [password, setPassword] = useState("demo123");
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<LoginResponse>("/auth/login", {
        email,
        password,
      });
      storeSession(res.access_token, res.user);
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError("Login failed"));
      setBusy(false);
    }
  }

  async function loginWithGoogle(idToken: string) {
  try {
    setBusy(true);
    setError(null);

    const res = await api.post<LoginResponse>("/auth/google", {
      id_token: idToken,
    });

    storeSession(res.access_token, res.user);

    router.replace("/");
  } catch (err) {
    setError(
      err instanceof ApiError
        ? err
        : new ApiError("Google Sign-In failed")
    );
  } finally {
    setBusy(false);
  }
}

return (
  <div className="login-wrap">
    <div className="login-card">
      <div className="login-logo">
        <span style={{ color: "var(--accent)" }}>⚡</span> IntelliPlant
      </div>

      <div className="login-tagline">
        Industrial Knowledge Intelligence Platform
      </div>

      <form onSubmit={submit} className="stack">
        {error && <ErrorBanner error={error} />}

        <div className="field">
          <label>Email</label>
          <input
            className="input"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div className="field">
          <label>Password</label>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <button className="btn btn-primary" disabled={busy} type="submit">
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>

      {/* Divider */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          margin: "20px 0",
        }}
      >
        <div
          style={{
            flex: 1,
            height: 1,
            background: "#2b2b2b",
          }}
        />
        <span
          style={{
            padding: "0 12px",
            color: "#888",
            fontSize: 13,
          }}
        >
          OR
        </span>
        <div
          style={{
            flex: 1,
            height: 1,
            background: "#2b2b2b",
          }}
        />
      </div>

      <GoogleLogin
        width="100%"
        theme="filled_black"
        shape="pill"
        text="continue_with"
        onSuccess={(credentialResponse) => {
          if (!credentialResponse.credential) {
            setError(new ApiError("No Google credential received"));
            return;
          }

          loginWithGoogle(credentialResponse.credential);
        }}
        onError={() => {
          setError(new ApiError("Google Sign-In failed"));
        }}
      />

      <div className="demo-hint">
        Demo: <code>engineer@intelliplant.io</code> /{" "}
        <code>demo123</code>
        <br />
        Also: manager@ · safety@ · tech@ · admin@intelliplant.io
      </div>
    </div>
  </div>
);
}
