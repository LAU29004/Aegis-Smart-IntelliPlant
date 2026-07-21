"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getStoredUser, getToken, logout } from "@/lib/api";
import type { User } from "@/lib/types";

const NAV = [
  { href: "/", label: "Dashboard", icon: "▦" },
  { href: "/copilot", label: "Copilot", icon: "✦" },
  { href: "/documents", label: "Documents", icon: "▤" },
  { href: "/equipment", label: "Equipment", icon: "⚙" },
  { href: "/compliance", label: "Compliance", icon: "☑" },
  { href: "/incidents", label: "Incidents", icon: "⚠" },
  { href: "/analytics", label: "Analytics", icon: "◫" },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    setUser(getStoredUser());
    setReady(true);
  }, [router]);

  if (!ready) return null;

  const initials = (user?.name ?? "?")
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <span className="bolt">⚡</span> IntelliPlant
        </div>
        <nav>
          {NAV.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-link ${active ? "active" : ""}`}
              >
                <span className="nav-icon">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-footer">PLANT-01 · v1.0 prototype</div>
      </aside>
      <div className="main-col">
        <header className="topbar">
          <div className="user-block">
            <div className="avatar">{initials}</div>
            <div>
              <div className="user-name">{user?.name}</div>
              <div className="user-role">{user?.role}</div>
            </div>
          </div>
          <button className="btn btn-sm" onClick={logout}>
            Logout
          </button>
        </header>
        <main className="page">{children}</main>
      </div>
    </div>
  );
}
