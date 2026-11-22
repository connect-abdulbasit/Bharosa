"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { api } from "@/lib/api";
import { useSession } from "@/lib/auth";
import { isLite } from "@/lib/lite";
import { NOTICE_EVENT, detectChanges, listNotices, markAllRead, unreadCount, type Notice } from "@/lib/notices";
import { speak } from "@/lib/speech";
import type { CaseSummary } from "@/lib/types";
import { Icon } from "./Icon";
import { formatTime } from "./StatusTimeline";

function subscribe(cb: () => void) {
  window.addEventListener(NOTICE_EVENT, cb);
  return () => window.removeEventListener(NOTICE_EVENT, cb);
}

/** Bell with an unread badge. Checks for claim changes while the app is open; optional phone alerts if the person allows them. */
export function NotificationBell() {
  const session = useSession();
  const userId = session?.userId ?? "";
  const token = session?.token;
  const helper = session?.role === "helper";
  const [open, setOpen] = useState(false);
  const [perm, setPerm] = useState<NotificationPermission | "unsupported">("unsupported");
  const box = useRef<HTMLDivElement>(null);

  const unread = useSyncExternalStore(subscribe, () => (userId ? unreadCount(userId) : 0), () => 0);
  const raw = useSyncExternalStore(subscribe, () => (userId ? JSON.stringify(listNotices(userId)) : "[]"), () => "[]");
  const items = useMemo<Notice[]>(() => JSON.parse(raw) as Notice[], [raw]);

  useEffect(() => {
    queueMicrotask(() => setPerm(typeof Notification === "undefined" ? "unsupported" : Notification.permission));
  }, []);

  const check = useCallback(async () => {
    if (!userId || !token || document.hidden) return;
    try {
      const r = await api<{ items: CaseSummary[] }>("GET", "/cases", { token });
      detectChanges(userId, r.items, helper);
    } catch {
      /* offline or signed out: try again next time */
    }
  }, [userId, token, helper]);

  // Phone alert for changes found while the app is open but not in front (installed PWA, other tab).
  const lastAlerted = useRef<string | null>(null);
  useEffect(() => {
    const top = items[0];
    if (!top || top.read || lastAlerted.current === top.id) return;
    lastAlerted.current = top.id;
    if (typeof Notification !== "undefined" && Notification.permission === "granted" && document.visibilityState !== "visible") {
      new Notification("Bharosa · بھروسہ", { body: `${top.en}\n${top.ur}`, icon: "/icon.svg", tag: top.id });
    }
  }, [items]);

  useEffect(() => {
    if (!userId) return;
    queueMicrotask(() => void check());
    const t = setInterval(() => void check(), isLite() ? 90_000 : 30_000);
    const wake = () => void check();
    window.addEventListener("focus", wake);
    window.addEventListener("online", wake);
    document.addEventListener("visibilitychange", wake);
    return () => {
      clearInterval(t);
      window.removeEventListener("focus", wake);
      window.removeEventListener("online", wake);
      document.removeEventListener("visibilitychange", wake);
    };
  }, [userId, check]);

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  if (!userId) return null;

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        aria-label={unread ? `${unread} new updates` : "Updates"}
        aria-expanded={open}
        onClick={() => {
          setOpen((v) => !v);
          if (!open && unread) setTimeout(() => markAllRead(userId), 1500);
        }}
        className="relative flex min-h-[44px] min-w-[44px] items-center justify-center rounded-full border border-line bg-surface text-ink-soft transition hover:border-teal-600 hover:text-brand active:scale-95"
      >
        <Icon name="bell" size={20} />
        {unread > 0 && (
          <span className="absolute -end-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-bad-700 px-1 text-[11px] font-extrabold text-white">{unread}</span>
        )}
      </button>

      {open && (
        <div role="dialog" aria-label="Updates" className="card fixed inset-x-4 top-20 z-50 p-3 shadow-[var(--shadow-md)] sm:absolute sm:inset-x-auto sm:end-0 sm:top-full sm:mt-2 sm:w-96">
          <p className="px-2 pb-2 font-extrabold text-heading">
            Updates · <span dir="rtl" lang="ur">اطلاعات</span>
          </p>
          {items.length === 0 ? (
            <p className="px-2 py-4 text-center text-sm text-ink-soft">
              Nothing new. We will tell you here when your claim changes.
              <span dir="rtl" lang="ur" className="block">کوئی نئی اطلاع نہیں۔ دعویٰ بدلنے پر یہاں بتائیں گے۔</span>
            </p>
          ) : (
            <ul className="max-h-80 space-y-2 overflow-y-auto">
              {items.map((n) => (
                <li key={n.id} className={`rounded-2xl p-3 text-sm ${n.read ? "bg-cream-2" : "bg-teal-50 ring-1 ring-teal-600"}`}>
                  <Link href={helper ? "/helper" : "/citizen/status"} onClick={() => setOpen(false)} className="block">
                    <span className="block font-bold">{n.en}</span>
                    <span dir="rtl" lang="ur" className="block">{n.ur}</span>
                  </Link>
                  <span className="mt-1 flex items-center justify-between text-xs text-ink-soft">
                    {formatTime(new Date(n.at).toISOString())}
                    <button type="button" className="min-h-[32px] font-bold text-brand underline" onClick={() => speak(n.ur, n.en)}>
                      Listen · سنیں
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          )}
          {perm === "default" && (
            <button
              type="button"
              className="mt-3 min-h-[44px] w-full rounded-2xl border border-line bg-surface text-sm font-bold hover:border-teal-600"
              onClick={() => void Notification.requestPermission().then(setPerm)}
            >
              Allow alerts on this phone <span aria-hidden>·</span> <span dir="rtl" lang="ur">اس فون پر الرٹس کی اجازت</span>
            </button>
          )}
          {perm === "denied" && <p className="mt-2 px-2 text-xs text-ink-soft">Phone alerts are blocked in this browser&apos;s settings.</p>}
        </div>
      )}
    </div>
  );
}
