import Link from "next/link";
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

/** English + Urdu label stack. Urdu is RTL with its own face. */
export function Bi({ en, ur, className = "", urClass = "" }: { en: ReactNode; ur: ReactNode; className?: string; urClass?: string }) {
  return (
    <span className={`flex flex-col ${className}`}>
      <span>{en}</span>
      <span dir="rtl" lang="ur" className={urClass}>{ur}</span>
    </span>
  );
}

/** Inline bilingual: "English · اردو" on one line. */
export function Inline({ en, ur }: { en: ReactNode; ur: ReactNode }) {
  return (
    <>
      {en} <span aria-hidden>·</span> <span dir="rtl" lang="ur">{ur}</span>
    </>
  );
}

const BTN = {
  primary: "bg-teal-700 text-white shadow-[var(--shadow-glow)] hover:bg-teal-800 border-transparent",
  accent: "bg-saffron-500 text-on-accent hover:bg-saffron-300 border-transparent shadow-[0_10px_26px_rgb(245_158_11/0.35)]",
  soft: "bg-teal-50 text-heading border-teal-100 hover:bg-teal-100",
  ghost: "bg-surface text-ink border-line hover:border-teal-600 hover:bg-teal-50",
  danger: "bg-bad-700 text-white hover:brightness-110 border-transparent",
  success: "bg-ok-700 text-white hover:brightness-110 border-transparent",
  onDark: "bg-white/10 text-white border-white/30 hover:bg-white/20",
} as const;
export type BtnVariant = keyof typeof BTN;

type BtnBase = {
  variant?: BtnVariant;
  icon?: IconName;
  en: ReactNode;
  ur?: ReactNode;
  size?: "md" | "lg";
  full?: boolean;
  loading?: boolean;
  className?: string;
};

function btnClass(v: BtnVariant, size: "md" | "lg", full: boolean, extra: string) {
  const h = size === "lg" ? "min-h-[68px] px-6 text-xl" : "min-h-[52px] px-5 text-lg";
  return `inline-flex items-center justify-center gap-3 rounded-2xl border-2 font-bold transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 ${h} ${full ? "w-full" : ""} ${BTN[v]} ${extra}`;
}

function BtnInner({ icon, en, ur, loading, size }: Pick<BtnBase, "icon" | "en" | "ur" | "loading" | "size">) {
  return (
    <>
      {loading ? <Spinner /> : icon ? <Icon name={icon} size={size === "lg" ? 28 : 22} /> : null}
      <span className="flex flex-col items-center text-center leading-tight">
        <span>{en}</span>
        {ur && <span dir="rtl" lang="ur" className="text-[0.95em] font-semibold opacity-95">{ur}</span>}
      </span>
    </>
  );
}

export function Button({ variant = "primary", icon, en, ur, size = "md", full, loading, className = "", disabled, ...rest }: BtnBase & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children" | "className">) {
  return (
    <button type="button" disabled={disabled || loading} className={btnClass(variant, size, !!full, className)} {...rest}>
      <BtnInner icon={icon} en={en} ur={ur} loading={loading} size={size} />
    </button>
  );
}

export function LinkButton({ href, variant = "primary", icon, en, ur, size = "md", full, className = "" }: BtnBase & { href: string }) {
  return (
    <Link href={href} className={btnClass(variant, size, !!full, className)}>
      <BtnInner icon={icon} en={en} ur={ur} size={size} />
    </Link>
  );
}

export function Spinner({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className="spin" role="status" aria-label="Loading">
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity={0.25} strokeWidth="3" />
      <path d="M21 12a9 9 0 00-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function Card({ children, className = "", lift, ...rest }: { children: ReactNode; className?: string; lift?: boolean } & Omit<HTMLAttributes<HTMLElement>, "children" | "className">) {
  return <section className={`card p-5 ${lift ? "card-lift" : ""} ${className}`} {...rest}>{children}</section>;
}

export function SectionTitle({ en, ur, icon, right }: { en: ReactNode; ur: ReactNode; icon?: IconName; right?: ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
      <h2 className="flex min-w-0 items-center gap-3 text-xl font-extrabold text-heading">
        {icon && (
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-brand">
            <Icon name={icon} size={22} />
          </span>
        )}
        <Bi en={en} ur={ur} className="gap-0 leading-tight" urClass="text-left text-lg font-bold" />
      </h2>
      {right}
    </div>
  );
}

const TONE = {
  ok: "bg-ok-soft text-ok-ink",
  bad: "bg-bad-soft text-bad-ink",
  warn: "bg-warn-soft text-warn-ink",
  info: "bg-info-soft text-info-ink",
  neutral: "bg-cream-2 text-ink-soft",
  brand: "bg-teal-100 text-heading",
} as const;
export type Tone = keyof typeof TONE;

export function Badge({ tone = "neutral", children, icon }: { tone?: Tone; children: ReactNode; icon?: IconName }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1 text-sm font-bold ${TONE[tone]}`}>
      {icon && <Icon name={icon} size={15} />}
      {children}
    </span>
  );
}

/** Calm inline message: error, info, success, warning. */
export function Notice({ tone = "info", title, children, role }: { tone?: Tone; title?: ReactNode; children?: ReactNode; role?: "alert" | "status" }) {
  const icon: IconName = tone === "bad" ? "alert" : tone === "ok" ? "checkCircle" : tone === "warn" ? "alert" : "sparkle";
  return (
    <div role={role ?? (tone === "bad" ? "alert" : "status")} className={`flex gap-3 rounded-2xl p-4 ${TONE[tone]}`}>
      <Icon name={icon} size={24} className="mt-0.5 shrink-0" />
      <div className="space-y-1">
        {title && <p className="font-extrabold">{title}</p>}
        {children && <div className="text-[0.97em] font-medium">{children}</div>}
      </div>
    </div>
  );
}

export function Field({ label, ur, hint, children }: { label: ReactNode; ur?: ReactNode; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 flex flex-col gap-0.5 font-bold text-heading sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
        <span>{label}</span>
        {ur && <span dir="rtl" lang="ur" className="self-end font-bold sm:self-auto">{ur}</span>}
      </span>
      {children}
      {hint && <span className="mt-1 block text-sm text-ink-soft">{hint}</span>}
    </label>
  );
}

export function Stat({ label, value, sub, tone = "brand", icon }: { label: ReactNode; value: ReactNode; sub?: ReactNode; tone?: Tone; icon?: IconName }) {
  return (
    <div className="card flex items-start gap-4 p-5">
      {icon && (
        <span className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ${TONE[tone]}`}>
          <Icon name={icon} size={26} />
        </span>
      )}
      <div className="min-w-0">
        <p className="text-sm font-bold uppercase tracking-wide text-ink-soft">{label}</p>
        <p className="text-3xl font-extrabold text-heading">{value}</p>
        {sub && <p className="text-sm text-ink-soft">{sub}</p>}
      </div>
    </div>
  );
}

export function Meter({ value, tone = "brand", label }: { value: number; tone?: "brand" | "ok" | "warn" | "bad"; label?: string }) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  const bar = { brand: "bg-teal-700", ok: "bg-ok-700", warn: "bg-saffron-500", bad: "bg-bad-700" }[tone];
  return (
    <div role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label={label} className="h-3 w-full overflow-hidden rounded-full bg-cream-2">
      <div className={`h-full rounded-full transition-[width] duration-700 ${bar}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Skeleton({ className = "h-24" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

export function EmptyState({ icon = "sparkle", en, ur }: { icon?: IconName; en: ReactNode; ur?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center gap-2 p-8 text-center text-ink-soft">
      <span className="flex h-14 w-14 items-center justify-center rounded-full bg-teal-50 text-brand">
        <Icon name={icon} size={28} />
      </span>
      <p className="text-lg font-bold">{en}</p>
      {ur && <p dir="rtl" lang="ur" className="text-lg font-semibold">{ur}</p>}
    </div>
  );
}

export function percent(n: number | null | undefined): string {
  return typeof n === "number" ? `${Math.round(n * 100)}%` : "–";
}

export function pretty(s: string | null | undefined): string {
  return (s ?? "").replace(/_/g, " ");
}
