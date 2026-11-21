import Link from "next/link";

/** Bharosa mark: a shield holding a small open hand/heart. Pure SVG so it is crisp at any size. */
export function LogoMark({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" className="h-9 w-9 shrink-0 sm:h-10 sm:w-10">
      <defs>
        <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#148f84" />
          <stop offset="1" stopColor="#0a4541" />
        </linearGradient>
      </defs>
      <path d="M24 3l17 6.5v12.2C41 33 34 41.5 24 45 14 41.5 7 33 7 21.7V9.5L24 3z" fill="url(#lg)" />
      <path d="M24 33s-8-4.8-8-10.4A4.4 4.4 0 0124 20.1a4.4 4.4 0 018 2.5C32 28.2 24 33 24 33z" fill="#f59e0b" />
    </svg>
  );
}

export function Logo({ href = "/", light = false }: { href?: string; light?: boolean }) {
  return (
    <Link href={href} className="flex shrink-0 items-center gap-2 sm:gap-3" aria-label="Bharosa home">
      <LogoMark />
      <span className="flex flex-col leading-none">
        <span className={`text-xl font-extrabold tracking-tight sm:text-2xl ${light ? "text-white" : "text-heading"}`}>Bharosa</span>
        <span dir="rtl" lang="ur" className={`text-left text-base font-bold ${light ? "text-saffron-300" : "text-saffron-600"}`}>بھروسہ</span>
      </span>
    </Link>
  );
}
