"use client";
import { useLite } from "@/lib/lite";
import { Icon } from "./Icon";

/** Data-saver switch for weak signal. */
export function LiteToggle() {
  const [lite, toggle] = useLite();
  return (
    <button
      type="button"
      onClick={toggle}
      role="switch"
      aria-checked={lite}
      aria-label={lite ? "Turn data saver off" : "Turn data saver on"}
      title={lite ? "Data saver ON · ڈیٹا بچت چالو" : "Data saver off · ڈیٹا بچت بند"}
      className={`flex min-h-[44px] min-w-[44px] items-center justify-center rounded-full border transition active:scale-95 ${
        lite ? "border-saffron-500 bg-saffron-300 text-on-accent" : "border-line bg-surface text-ink-soft hover:border-teal-600 hover:text-brand"
      }`}
    >
      <Icon name="signal" size={20} />
    </button>
  );
}
