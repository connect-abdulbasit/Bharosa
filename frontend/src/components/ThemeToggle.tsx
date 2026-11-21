"use client";
import { useTheme } from "@/lib/theme";
import { Icon } from "./Icon";

/** Sun/moon switch. `onDark` styles it for the dark teal landing hero. */
export function ThemeToggle({ onDark = false }: { onDark?: boolean }) {
  const [theme, toggle] = useTheme();
  const dark = theme === "dark";
  return (
    <button
      type="button"
      onClick={toggle}
      role="switch"
      aria-checked={dark}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Light mode · روشن" : "Dark mode · تاریک"}
      className={`flex min-h-[44px] min-w-[44px] items-center justify-center rounded-full border transition active:scale-95 ${
        onDark ? "border-white/30 bg-white/10 text-white hover:bg-white/20" : "border-line bg-surface text-ink-soft hover:border-teal-600 hover:text-brand"
      }`}
    >
      <Icon name={dark ? "sun" : "moon"} size={20} />
    </button>
  );
}
