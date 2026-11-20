import Link from "next/link";
import type { ReactNode } from "react";
import type { Role } from "@/lib/enums";
import { PrototypeBanner } from "./PrototypeBanner";
import { RoleGuard } from "./RoleGuard";
import { SessionBar } from "./SessionBar";

type Props = {
  title: string;
  urdu: string;
  roles?: Role[]; // omit for public pages
  back?: { href: string; label: string };
  note?: string; // placeholder text for screens still to build
  children?: ReactNode;
};

/** Every page: prototype banner, title (English + Urdu), optional role guard. */
export function PageShell({ title, urdu, roles, back, note, children }: Props) {
  const body = (
    <>
      <SessionBar />
      <h1 className="mt-3 text-3xl font-bold">{title}</h1>
      <p dir="rtl" lang="ur" className="mt-1 text-2xl">{urdu}</p>
      <div className="mt-5 space-y-5">
        {note && <p className="rounded border border-dashed p-4 text-sm opacity-80">{note}</p>}
        {children}
      </div>
    </>
  );
  return (
    <>
      <PrototypeBanner />
      <main className="mx-auto w-full max-w-xl flex-1 p-4 pb-16">
        <Link href={back?.href ?? "/"} className="inline-block min-h-[44px] py-2 text-base underline">
          ← {back?.label ?? "Home / ہوم"}
        </Link>
        {roles ? <RoleGuard roles={roles}>{body}</RoleGuard> : body}
      </main>
    </>
  );
}
