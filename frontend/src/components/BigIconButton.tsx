"use client";
import Link from "next/link";
import type { ReactNode } from "react";

type Props = {
  icon: ReactNode;
  en: string;
  ur: string;
  href?: string;
  onClick?: () => void;
  disabled?: boolean;
  tone?: "primary" | "neutral" | "danger" | "success";
  type?: "button" | "submit";
};

const TONES = {
  primary: "bg-teal-700 text-white border-teal-900",
  neutral: "bg-white text-black border-gray-400",
  danger: "bg-red-700 text-white border-red-900",
  success: "bg-green-700 text-white border-green-900",
};

/** Large touch target (min 72px) with an icon plus English and Urdu labels. */
export function BigIconButton({ icon, en, ur, href, onClick, disabled, tone = "neutral", type = "button" }: Props) {
  const cls = `flex min-h-[72px] w-full items-center gap-4 rounded-2xl border-2 px-4 py-3 text-left shadow-sm active:scale-[0.99] disabled:opacity-50 ${TONES[tone]}`;
  const body = (
    <>
      <span aria-hidden className="text-4xl">{icon}</span>
      <span className="flex flex-col">
        <span className="text-xl font-bold">{en}</span>
        <span dir="rtl" lang="ur" className="text-xl">{ur}</span>
      </span>
    </>
  );
  if (href && !disabled) {
    return (
      <Link href={href} className={cls}>
        {body}
      </Link>
    );
  }
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={cls}>
      {body}
    </button>
  );
}
