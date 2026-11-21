"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { PageShell } from "@/components/PageShell";
import { formatTime } from "@/components/StatusTimeline";
import { Badge, Button, Card, Field, Notice, SectionTitle, Skeleton } from "@/components/ui";
import { API_MODE, api, errorText } from "@/lib/api";
import { getSession } from "@/lib/auth";
import type { UserRow } from "@/lib/types";

type ApiKey = { id: string; name: string; prefix: string; scopes: string[]; created_at: string; last_used_at?: string | null; revoked: boolean };

const TILES: { href: string; icon: IconName; en: string; ur: string; line: string }[] = [
  { href: "/officer", icon: "list", en: "Review queue", ur: "جائزہ قطار", line: "Cases waiting for a person" },
  { href: "/admin/rules", icon: "sliders", en: "Decision rules", ur: "قواعد", line: "Versioned thresholds and red flags" },
  { href: "/admin/twin", icon: "flask", en: "Digital Twin", ur: "ڈیجیٹل ٹوِن", line: "Test a change on past cases" },
  { href: "/admin/chaos", icon: "bolt", en: "Chaos Panel", ur: "خرابی کا پینل", line: "Show safe failure live" },
  { href: "/auditor", icon: "scroll", en: "Audit log", ur: "آڈٹ لاگ", line: "Every action, append-only" },
  { href: "/eval", icon: "chart", en: "Insights", ur: "اعداد", line: "Accuracy, overrides, scam map" },
];

const SCOPES = ["cases:read", "messages:check"];

function ApiKeys() {
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>(["messages:check"]);
  const [created, setCreated] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    api<{ items: ApiKey[] }>("GET", "/apikeys", { token: getSession()?.token })
      .then((r) => setKeys(r.items))
      .catch((e) => setErr(errorText(e)));
  }, []);
  useEffect(load, [load]);

  async function create() {
    setBusy(true);
    setErr(null);
    try {
      const r = await api<ApiKey & { key: string }>("POST", "/apikeys", { body: { name: name.trim(), scopes }, token: getSession()?.token });
      setCreated(r.key);
      setName("");
      load();
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: string) {
    try {
      await api("POST", `/apikeys/${id}/revoke`, { token: getSession()?.token });
      load();
    } catch (e) {
      setErr(errorText(e));
    }
  }

  return (
    <Card className="space-y-4">
      <SectionTitle icon="key" en="Partner API keys" ur="پارٹنر API کیز" />
      {err && <Notice tone="bad">{err}</Notice>}
      {created && (
        <Notice tone="ok" title="Copy this key now. It is shown only once.">
          <code className="mt-1 block break-all rounded-xl bg-surface p-3 font-mono text-sm text-ink">{created}</code>
          <button type="button" className="mt-2 min-h-[44px] font-bold underline" onClick={() => setCreated(null)}>I have copied it</button>
        </Notice>
      )}
      {!keys && <Skeleton className="h-24" />}
      <ul className="space-y-2">
        {keys?.map((k) => (
          <li key={k.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-cream-2 p-3">
            <span className="min-w-0">
              <span className="block font-extrabold">{k.name}</span>
              <span className="block font-mono text-xs text-ink-soft">{k.prefix}… · {k.scopes.join(", ")}</span>
              <span className="block text-xs text-ink-soft">last used {k.last_used_at ? formatTime(k.last_used_at) : "never"}</span>
            </span>
            {k.revoked ? <Badge tone="neutral">revoked</Badge> : <Button variant="ghost" icon="x" en="Revoke" onClick={() => void revoke(k.id)} />}
          </li>
        ))}
      </ul>
      <div className="space-y-3 rounded-2xl border border-dashed border-line p-4">
        <Field label="New key name">
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Partner NGO" />
        </Field>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Scopes">
          {SCOPES.map((s) => (
            <button key={s} type="button" aria-pressed={scopes.includes(s)} onClick={() => setScopes(scopes.includes(s) ? scopes.filter((x) => x !== s) : [...scopes, s])} className={`min-h-[44px] rounded-full px-4 text-sm font-bold ${scopes.includes(s) ? "bg-teal-700 text-white" : "border border-line bg-surface"}`}>{s}</button>
          ))}
        </div>
        <Button loading={busy} disabled={!name.trim() || scopes.length === 0} icon="plus" en="Create key" onClick={() => void create()} />
      </div>
    </Card>
  );
}

export default function AdminHome() {
  const [users, setUsers] = useState<UserRow[] | null>(null);

  useEffect(() => {
    // GET /users does not exist on the backend yet (TODO(Basit)). Fixtures mode shows sample users; live mode hides the list.
    if (API_MODE !== "fixtures") return;
    api<{ items: UserRow[] }>("GET", "/users", { token: getSession()?.token }).then((r) => setUsers(r.items)).catch(() => setUsers([]));
  }, []);

  return (
    <PageShell title="Admin" urdu="ایڈمن" roles={["admin"]} wide>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {TILES.map((t, i) => (
          <Link key={t.href} href={t.href} className={`card card-lift rise rise-${Math.min(i + 1, 4)} flex items-center gap-4 p-5`}>
            <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-teal-50 text-brand"><Icon name={t.icon} size={28} /></span>
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block text-lg font-extrabold text-heading">{t.en}</span>
              <span dir="rtl" lang="ur" className="block font-bold text-saffron-600">{t.ur}</span>
              <span className="block text-sm text-ink-soft">{t.line}</span>
            </span>
          </Link>
        ))}
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-2">
        <ApiKeys />
        <Card className="space-y-3">
          <SectionTitle icon="users" en="Users and roles" ur="صارفین اور کردار" />
          {API_MODE === "live" && <Notice tone="info">The backend has no users list endpoint yet, so this panel shows sample data only in fixtures mode.</Notice>}
          {API_MODE === "fixtures" && !users && <Skeleton className="h-24" />}
          <ul className="space-y-2">
            {users?.map((u) => (
              <li key={u.user_id} className="flex items-center justify-between gap-3 rounded-2xl bg-cream-2 p-3">
                <span><span className="block font-extrabold">{u.display_name}</span><span className="text-xs text-ink-soft">{u.username}</span></span>
                <Badge tone={u.active ? "brand" : "neutral"}>{u.role}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </PageShell>
  );
}
