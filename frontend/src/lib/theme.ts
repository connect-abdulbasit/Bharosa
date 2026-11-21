"use client";
// Light/dark theme. The inline script in layout.tsx sets <html data-theme> before first paint
// (saved choice, else the system setting); this module reads and changes it afterwards.
import { useSyncExternalStore } from "react";

export type Theme = "light" | "dark";
export const THEME_KEY = "bharosa.theme";
const EVENT = "bharosa:theme";

function current(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  return () => window.removeEventListener(EVENT, cb);
}

export function useTheme(): [Theme, () => void] {
  const theme = useSyncExternalStore(subscribe, current, () => "light" as Theme);
  const toggle = () => {
    const next: Theme = current() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      window.localStorage.setItem(THEME_KEY, next);
    } catch {
      /* storage blocked: the choice lasts until reload */
    }
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", next === "dark" ? "#0b1513" : "#0f766e");
    window.dispatchEvent(new Event(EVENT));
  };
  return [theme, toggle];
}
