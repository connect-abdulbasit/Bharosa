"use client";
// Session in localStorage. UX only: the backend enforces RBAC server-side.
import { useMemo, useSyncExternalStore } from "react";
import { Role } from "./enums";
import { API_MODE, api } from "./api";
import { clearNotices } from "./notices";
import type { Session } from "./types";

const KEY = "bharosa.session";
const EVENT = "bharosa:session";

// Demo users (fake). Same as .env.example. Used directly in fixtures mode.
export const DEMO_USERS: { username: string; password: string; role: Role; name: string; userId: string }[] = [
  { username: "citizen", password: "citizen-demo-123", role: Role.citizen, name: "Fatima Bibi (demo)", userId: "u-citizen-1" },
  { username: "helper", password: "helper-demo-123", role: Role.helper, name: "Nasreen Akhtar (demo helper)", userId: "u-helper-1" },
  { username: "officer", password: "officer-demo-123", role: Role.officer, name: "Officer Imran (demo)", userId: "u-officer-1" },
  { username: "admin", password: "admin-demo-123", role: Role.admin, name: "Admin (demo)", userId: "u-admin-1" },
  { username: "auditor", password: "auditor-demo-123", role: Role.auditor, name: "Auditor (demo)", userId: "u-auditor-1" },
];

export const HOME_FOR_ROLE: Record<Role, string> = {
  citizen: "/citizen",
  helper: "/helper",
  officer: "/officer",
  admin: "/admin",
  auditor: "/auditor",
};

function raw(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function subscribe(cb: () => void) {
  window.addEventListener("storage", cb);
  window.addEventListener(EVENT, cb);
  return () => {
    window.removeEventListener("storage", cb);
    window.removeEventListener(EVENT, cb);
  };
}

export function getSession(): Session | null {
  const r = raw();
  if (!r) return null;
  try {
    return JSON.parse(r) as Session;
  } catch {
    return null;
  }
}

/** undefined = not yet known (server render / first paint), null = signed out. */
export function useSession(): Session | null | undefined {
  const snapshot = useSyncExternalStore(subscribe, raw, () => undefined);
  return useMemo(() => {
    if (snapshot === undefined) return undefined;
    if (!snapshot) return null;
    try {
      return JSON.parse(snapshot) as Session;
    } catch {
      return null;
    }
  }, [snapshot]);
}

function save(s: Session | null) {
  try {
    if (s) window.localStorage.setItem(KEY, JSON.stringify(s));
    else window.localStorage.removeItem(KEY);
  } catch {
    /* storage blocked: session lasts only until reload */
  }
  window.dispatchEvent(new Event(EVENT));
}

export async function login(username: string, password: string): Promise<Session> {
  const user = DEMO_USERS.find((u) => u.username === username);
  if (API_MODE === "fixtures") {
    if (!user || user.password !== password) throw new Error("Wrong username or password");
    const s: Session = { token: "fixture-token", role: user.role, userId: user.userId, name: user.name, username };
    save(s);
    return s;
  }
  const t = await api<{ access_token: string; role: Role }>("POST", "/auth/login", { body: { username, password } });
  const me = await api<{ user_id: string; display_name: string; role: Role }>("GET", "/me", { token: t.access_token });
  const s: Session = { token: t.access_token, role: me.role, userId: me.user_id, name: me.display_name, username };
  save(s);
  return s;
}

export function logout() {
  // Shared phones: do not leave one person's updates for the next person.
  const s = getSession();
  if (s) clearNotices(s.userId);
  save(null);
}
