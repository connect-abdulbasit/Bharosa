"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "@/lib/auth";
import type { Role } from "@/lib/enums";
import { Icon, type IconName } from "./Icon";

type Item = { href: string; icon: IconName; en: string; ur: string; exact?: boolean };

const CITIZEN: Item[] = [
  { href: "/citizen", icon: "home", en: "Home", ur: "ہوم", exact: true },
  { href: "/citizen/check", icon: "shield", en: "Check", ur: "چیک" },
  { href: "/citizen/claim", icon: "mic", en: "Claim", ur: "دعویٰ" },
  { href: "/citizen/status", icon: "clock", en: "Status", ur: "حالت" },
  { href: "/citizen/data", icon: "lock", en: "My data", ur: "ڈیٹا" },
];
const HELPER: Item[] = [{ href: "/helper", icon: "users", en: "Families", ur: "خاندان" }, ...CITIZEN.slice(1)];
const OFFICER: Item[] = [
  { href: "/officer", icon: "list", en: "Queue", ur: "قطار" },
  { href: "/eval", icon: "chart", en: "Insights", ur: "اعداد" },
];
const ADMIN: Item[] = [
  { href: "/admin", icon: "home", en: "Overview", ur: "جائزہ", exact: true },
  { href: "/officer", icon: "list", en: "Queue", ur: "قطار" },
  { href: "/admin/rules", icon: "sliders", en: "Rules", ur: "قواعد" },
  { href: "/admin/twin", icon: "flask", en: "Twin", ur: "ٹوئن" },
  { href: "/admin/chaos", icon: "bolt", en: "Chaos", ur: "خرابی" },
  { href: "/auditor", icon: "scroll", en: "Audit", ur: "آڈٹ" },
  { href: "/eval", icon: "chart", en: "Insights", ur: "اعداد" },
];
const AUDITOR: Item[] = [
  { href: "/auditor", icon: "scroll", en: "Audit log", ur: "آڈٹ لاگ" },
  { href: "/eval", icon: "chart", en: "Insights", ur: "اعداد" },
];

export function navFor(role: Role | undefined): Item[] {
  switch (role) {
    case "citizen": return CITIZEN;
    case "helper": return HELPER;
    case "officer": return OFFICER;
    case "admin": return ADMIN;
    case "auditor": return AUDITOR;
    default: return [];
  }
}

/**
 * One navigation, three shapes:
 *  - side:   desktop sidebar (lg and up), every role
 *  - bottom: phone tab bar for citizen/helper (hidden at lg and up)
 *  - top:    phone/tablet pill row for staff (hidden at lg and up)
 */
export function NavBar({ variant }: { variant: "bottom" | "top" | "side" }) {
  const session = useSession();
  const path = usePathname();
  const items = navFor(session?.role);
  if (!items.length) return null;

  const active = (i: Item) => (i.exact ? path === i.href : path === i.href || path.startsWith(i.href + "/"));

  if (variant === "side") {
    return (
      <nav aria-label="Main" className="no-print sticky top-28 hidden w-60 shrink-0 self-start lg:block">
        <ul className="card space-y-1 p-2">
          {items.map((i) => (
            <li key={i.href}>
              <Link
                href={i.href}
                aria-current={active(i) ? "page" : undefined}
                className={`flex min-h-[52px] items-center gap-3 rounded-2xl px-3 font-bold transition ${
                  active(i) ? "bg-teal-700 text-white shadow-[var(--shadow-sm)]" : "text-ink-soft hover:bg-teal-50 hover:text-heading"
                }`}
              >
                <Icon name={i.icon} size={22} />
                <span className="flex flex-1 items-baseline justify-between gap-2">
                  <span>{i.en}</span>
                  <span dir="rtl" lang="ur" className="text-sm opacity-80">{i.ur}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    );
  }

  if (variant === "top") {
    return (
      <nav aria-label="Main" className="no-print border-b border-line bg-surface/70 backdrop-blur lg:hidden">
        <ul className="mx-auto flex max-w-[88rem] gap-2 overflow-x-auto px-4 py-2">
          {items.map((i) => (
            <li key={i.href} className="shrink-0">
              <Link
                href={i.href}
                aria-current={active(i) ? "page" : undefined}
                className={`flex min-h-[44px] items-center gap-2 whitespace-nowrap rounded-full px-4 text-sm font-bold transition ${
                  active(i) ? "bg-teal-700 text-white shadow-[var(--shadow-glow)]" : "text-ink-soft hover:bg-teal-50 hover:text-heading"
                }`}
              >
                <Icon name={i.icon} size={18} />
                {i.en}
                <span dir="rtl" lang="ur" className="opacity-80">{i.ur}</span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    );
  }

  return (
    <nav aria-label="Main" className="no-print fixed inset-x-0 bottom-0 z-40 px-3 pb-[max(0.6rem,env(safe-area-inset-bottom))] lg:hidden">
      <ul className="mx-auto flex max-w-xl justify-between gap-1 rounded-[26px] border border-line bg-surface/95 p-1.5 shadow-[var(--shadow-md)] backdrop-blur">
        {items.map((i) => (
          <li key={i.href} className="flex-1">
            <Link
              href={i.href}
              aria-current={active(i) ? "page" : undefined}
              className={`flex min-h-[60px] flex-col items-center justify-center gap-0 rounded-[20px] px-1 text-[12px] font-bold leading-tight transition ${
                active(i) ? "bg-teal-700 text-white" : "text-ink-soft hover:bg-teal-50"
              }`}
            >
              <Icon name={i.icon} size={22} />
              <span>{i.en}</span>
              <span dir="rtl" lang="ur" className="text-[12px] leading-none">{i.ur}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
