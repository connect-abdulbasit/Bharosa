"use client";
// In-app notices: when a claim's status changes we tell the person, in English and Urdu.
// There is no push channel in the prototype, so the app notices changes by checking /cases (ETag-cheap) while it is open.
// Stored per user on this phone only; cleared on log out because phones are shared.
import { statusLook } from "./status";
import type { CaseSummary } from "./types";

export type Notice = { id: string; caseId: string; en: string; ur: string; at: number; read: boolean; status: string };
type Store = { seen: Record<string, string>; items: Notice[] };

const key = (userId: string) => `bharosa.notices.${userId}`;
export const NOTICE_EVENT = "bharosa:notices";
const MAX = 30;

function load(userId: string): Store {
  try {
    const raw = window.localStorage.getItem(key(userId));
    if (raw) return JSON.parse(raw) as Store;
  } catch {
    /* ignore */
  }
  return { seen: {}, items: [] };
}

function save(userId: string, s: Store, announce = true) {
  try {
    window.localStorage.setItem(key(userId), JSON.stringify(s));
  } catch {
    /* storage blocked: notices last until reload */
  }
  if (announce) window.dispatchEvent(new Event(NOTICE_EVENT));
}

export const listNotices = (userId: string): Notice[] => load(userId).items;
export const unreadCount = (userId: string): number => load(userId).items.filter((n) => !n.read).length;

export function markAllRead(userId: string) {
  const s = load(userId);
  s.items = s.items.map((n) => ({ ...n, read: true }));
  save(userId, s);
}

export function clearNotices(userId: string) {
  try {
    window.localStorage.removeItem(key(userId));
  } catch {
    /* ignore */
  }
}

/** Compare the latest cases with what we saw last time; returns the NEW notices (also saved). The first look only records a baseline. */
export function detectChanges(userId: string, cases: CaseSummary[], helper: boolean): Notice[] {
  const s = load(userId);
  const first = Object.keys(s.seen).length === 0 && s.items.length === 0;
  const fresh: Notice[] = [];
  for (const c of cases) {
    const prev = s.seen[c.id];
    if (!first && prev !== c.status) {
      const look = statusLook(c.status);
      fresh.push({
        id: `${c.id}:${c.status}:${c.updated_at}`,
        caseId: c.id,
        status: c.status,
        at: Date.now(),
        read: false,
        en: `${helper ? c.citizen_name + ": " : ""}your claim of PKR ${c.amount_claimed_pkr.toLocaleString("en-US")} is now: ${look.en}.`,
        ur: `${helper ? c.citizen_name + ": " : ""}آپ کا PKR ${c.amount_claimed_pkr} کا دعویٰ اب: ${look.ur}۔`,
      });
    }
    s.seen[c.id] = c.status;
  }
  if (fresh.length) s.items = [...fresh, ...s.items].slice(0, MAX);
  save(userId, s, fresh.length > 0); // only wake listeners when something is new
  return fresh;
}
