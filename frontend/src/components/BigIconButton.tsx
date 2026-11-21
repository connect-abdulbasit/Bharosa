"use client";
import Link from "next/link";
import { Icon, type IconName } from "./Icon";

type Props = {
  icon: IconName;
  en: string;
  ur: string;
  hint?: string;
  href?: string;
  onClick?: () => void;
  disabled?: boolean;
  tone?: "primary" | "neutral" | "danger" | "success" | "accent";
  type?: "button" | "submit";
};

const TONES = {
  primary: { box: "bg-teal-700 text-white border-transparent shadow-[var(--shadow-glow)]", chip: "bg-white/15 text-white" },
  neutral: { box: "bg-surface text-ink border-line", chip: "bg-teal-50 text-brand" },
  danger: { box: "bg-bad-700 text-white border-transparent", chip: "bg-white/15 text-white" },
  success: { box: "bg-ok-700 text-white border-transparent", chip: "bg-white/15 text-white" },
  accent: { box: "bg-saffron-50 text-ink border-saffron-300", chip: "bg-saffron-300 text-on-accent" },
};

/** Large touch target (min 84px): icon chip + English + Urdu. The main way citizens move around. */
export function BigIconButton({ icon, en, ur, hint, href, onClick, disabled, tone = "neutral", type = "button" }: Props) {
  const t = TONES[tone];
  const cls = `card-lift flex min-h-[84px] w-full items-center gap-4 rounded-[22px] border-2 px-4 py-3 text-left disabled:cursor-not-allowed disabled:opacity-50 ${t.box}`;
  const body = (
    <>
      <span className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl ${t.chip}`}>
        <Icon name={icon} size={30} />
      </span>
      <span className="flex min-w-0 flex-1 flex-col leading-tight">
        <span className="text-xl font-extrabold">{en}</span>
        <span dir="rtl" lang="ur" className="self-start text-xl font-bold">{ur}</span>
        {hint && <span className="mt-0.5 text-sm font-medium opacity-80">{hint}</span>}
      </span>
      <Icon name="arrow" size={22} className="shrink-0 opacity-60" />
    </>
  );
  if (href && !disabled) {
    return <Link href={href} className={cls}>{body}</Link>;
  }
  return <button type={type} onClick={onClick} disabled={disabled} className={cls}>{body}</button>;
}
