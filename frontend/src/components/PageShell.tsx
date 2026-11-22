"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import type { Role } from "@/lib/enums";
import { useSession } from "@/lib/auth";
import { Icon } from "./Icon";
import { LiteToggle } from "./LiteToggle";
import { Logo } from "./Logo";
import { NavBar } from "./NavBar";
import { NotificationBell } from "./NotificationBell";
import { OnlineBadge } from "./OnlineBadge";
import { RoleGuard } from "./RoleGuard";
import { SessionBar } from "./SessionBar";
import { ThemeToggle } from "./ThemeToggle";

type Props = {
  title: string;
  urdu: string;
  roles?: Role[]; // omit for public pages
  back?: { href: string; label: string };
  note?: string;
  wide?: boolean; // dashboards / two-column pages use the full content width; default is a focused reading column
  actions?: ReactNode; // right side of the title row
  children?: ReactNode;
};

const CITIZENISH: Role[] = ["citizen", "helper"];
const FRAME = "mx-auto w-full max-w-[88rem] px-4 lg:px-8";

/**
 * App shell. Desktop: header + sidebar + content. Phone: header + content + bottom tab bar (citizen/helper)
 * or a pill row (staff). Public pages (login, offline) have no navigation.
 */
export function PageShell({ title, urdu, roles, back, note, wide, actions, children }: Props) {
  const session = useSession();
  const citizenLike = session ? CITIZENISH.includes(session.role) : roles ? roles.every((r) => CITIZENISH.includes(r)) : false;
  const homeHref = session
    ? citizenLike
      ? session.role === "helper" ? "/helper" : "/citizen"
      : session.role === "officer" ? "/officer" : session.role === "auditor" ? "/auditor" : "/admin"
    : "/";

  const body = (
    <>
      <div className="rise mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-line pb-5">
        <div className="min-w-0">
          {back && (
            <Link href={back.href} className="mb-3 inline-flex min-h-[40px] items-center gap-2 rounded-full bg-surface px-4 text-sm font-bold text-brand shadow-[var(--shadow-sm)] hover:bg-teal-50">
              <Icon name="arrowLeft" size={16} />
              {back.label}
            </Link>
          )}
          <h1 className="text-3xl font-extrabold leading-tight tracking-tight text-heading sm:text-4xl">{title}</h1>
          <p dir="rtl" lang="ur" className="text-left text-2xl font-bold text-saffron-600">{urdu}</p>
        </div>
        {actions && <div className="shrink-0">{actions}</div>}
      </div>
      <div className="space-y-6">
        {note && <p className="rounded-2xl border border-dashed border-line bg-surface p-4 text-sm text-ink-soft">{note}</p>}
        {children}
      </div>
    </>
  );

  const content = roles ? <RoleGuard roles={roles}>{body}</RoleGuard> : body;

  return (
    <>
      <OnlineBadge />
      <header className="no-print sticky top-0 z-30 border-b border-line bg-cream/90 backdrop-blur">
        <div className={`${FRAME} flex items-center justify-between gap-3 py-2.5`}>
          <Logo href={homeHref} />
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
            {citizenLike && <NotificationBell />}
            <LiteToggle />
            <ThemeToggle />
            <SessionBar />
          </div>
        </div>
      </header>
      {!citizenLike && session && <NavBar variant="top" />}

      <div className={`${FRAME} flex flex-1 items-start gap-8 pt-6 ${citizenLike ? "pb-32 lg:pb-16" : "pb-16"}`}>
        {session && <NavBar variant="side" />}
        <main id="main" className="min-w-0 flex-1">
          <div className={wide || !session ? (session ? "" : "mx-auto max-w-5xl") : "mx-auto max-w-3xl"}>{content}</div>
        </main>
      </div>
      {citizenLike && session && <NavBar variant="bottom" />}
    </>
  );
}
