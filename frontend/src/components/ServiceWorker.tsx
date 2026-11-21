"use client";
import { useEffect } from "react";

/**
 * Production builds: register /sw.js (offline shell).
 * Development: remove any worker + caches left over from an earlier production run on this origin, otherwise it
 * keeps serving stale CSS/JS on localhost:3000 and the dev server's changes never show up.
 */
export function ServiceWorker() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

    if (process.env.NODE_ENV !== "production") {
      void (async () => {
        const regs = await navigator.serviceWorker.getRegistrations();
        const keys = typeof caches === "undefined" ? [] : (await caches.keys()).filter((k) => k.startsWith("bharosa-"));
        if (regs.length === 0 && keys.length === 0) return;
        await Promise.all(regs.map((r) => r.unregister()));
        await Promise.all(keys.map((k) => caches.delete(k)));
        try {
          if (!window.sessionStorage.getItem("bharosa.sw-cleaned")) {
            window.sessionStorage.setItem("bharosa.sw-cleaned", "1");
            window.location.reload(); // one reload so the page is no longer served by the old worker
          }
        } catch {
          /* ignore */
        }
      })();
      return;
    }

    const register = () => void navigator.serviceWorker.register("/sw.js").catch(() => undefined);
    if (document.readyState === "complete") register();
    else window.addEventListener("load", register, { once: true });
  }, []);
  return null;
}
