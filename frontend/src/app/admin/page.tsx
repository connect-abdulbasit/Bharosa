"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { PageShell } from "@/components/PageShell";
import { formatTime } from "@/components/StatusTimeline";
import { api } from "@/lib/api";
import { getSession } from "@/lib/auth";
import type { UserRow } from "@/lib/types";

export default function AdminHome() {
  const [users, setUsers] = useState<UserRow[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api<{ items: UserRow[] }>("GET", "/users", { token: getSession()?.token })
      .then((r) => setUsers(r.items))
      .catch(() => setError(true));
  }, []);

  return (
    <PageShell title="Admin" urdu="ایڈمن" roles={["admin"]}>
      <nav className="grid grid-cols-1 gap-2">
        <Link className="flex min-h-[56px] items-center rounded-xl border-2 px-4 text-lg font-bold" href="/admin/rules">📏 Rule editor · اصول</Link>
        <Link className="flex min-h-[56px] items-center rounded-xl border-2 px-4 text-lg font-bold" href="/admin/twin">🧪 Digital Twin · ڈیجیٹل ٹوِن</Link>
        <Link className="flex min-h-[56px] items-center rounded-xl border-2 px-4 text-lg font-bold" href="/admin/chaos">🌪️ Chaos Panel · افراتفری پینل</Link>
      </nav>
      <section aria-labelledby="u">
        <h2 id="u" className="text-xl font-bold">Users and roles · صارفین اور کردار</h2>
        {error && <p role="alert" className="font-semibold text-red-700">Could not load users.</p>}
        {!users && !error && <p>Loading…</p>}
        <ul className="mt-2 space-y-2">
          {users?.map((u) => (
            <li key={u.user_id} className="flex items-center justify-between rounded-xl border-2 p-3">
              <span>
                <span className="block font-bold">{u.display_name}</span>
                <span className="text-sm opacity-80">{u.username} · last login {formatTime(u.last_login)}</span>
              </span>
              <span className="rounded-full bg-teal-100 px-3 py-1 text-sm font-bold capitalize text-teal-900">{u.role}</span>
            </li>
          ))}
        </ul>
      </section>
    </PageShell>
  );
}
