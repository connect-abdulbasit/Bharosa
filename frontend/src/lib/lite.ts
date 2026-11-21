"use client";
// Low-bandwidth ("data saver") mode. On automatically for the browser's Data Saver or a 2G connection,
// and switchable by hand. Effects: no animations/blur/shadows/gradients (CSS on html[data-lite]),
// slower polling, polling paused while the tab is hidden. The inline script in layout.tsx sets the
// attribute before first paint.
import { useSyncExternalStore } from "react";

export const LITE_KEY = "bharosa.lite";
const EVENT = "bharosa:lite";

type Conn = { saveData?: boolean; effectiveType?: string };
export function autoLite(): boolean {
  const c = (navigator as unknown as { connection?: Conn }).connection;
  return !!c && (c.saveData === true || c.effectiveType === "slow-2g" || c.effectiveType === "2g");
}

export function isLite(): boolean {
  return typeof document !== "undefined" && document.documentElement.dataset.lite === "true";
}

function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  return () => window.removeEventListener(EVENT, cb);
}

export function useLite(): [boolean, () => void] {
  const lite = useSyncExternalStore(subscribe, isLite, () => false);
  const toggle = () => {
    const next = !isLite();
    document.documentElement.dataset.lite = String(next);
    try {
      window.localStorage.setItem(LITE_KEY, String(next));
    } catch {
      /* storage blocked: lasts until reload */
    }
    window.dispatchEvent(new Event(EVENT));
  };
  return [lite, toggle];
}
