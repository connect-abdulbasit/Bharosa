"use client";
import { useCallback, useState } from "react";
import { PageShell } from "@/components/PageShell";
import { formatTime } from "@/components/StatusTimeline";
import { Badge, Button, EmptyState, Field, Notice, Skeleton, type Tone } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { useLoader } from "@/lib/hooks";
import type { AuditEntry } from "@/lib/types";

const PAGE = 25;
const ACTOR_TONE: Record<string, Tone> = { user: "brand", ai: "info", agent: "warn", system: "neutral" };

function Diff({ before, after }: { before?: Record<string, unknown> | null; after?: Record<string, unknown> | null }) {
  const keys = Array.from(new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})]));
  if (keys.length === 0) return <p className="text-sm text-ink-soft">No details recorded.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead><tr className="text-xs uppercase text-ink-soft"><th className="py-1 pe-3">Field</th><th className="py-1 pe-3">Before</th><th className="py-1">After</th></tr></thead>
        <tbody>
          {keys.map((k) => {
            const b = before?.[k];
            const a = after?.[k];
            const changed = JSON.stringify(b) !== JSON.stringify(a);
            return (
              <tr key={k} className="border-t border-line align-top">
                <td className="py-1.5 pe-3 font-bold">{k}</td>
                <td className="py-1.5 pe-3 font-mono text-xs text-ink-soft">{b === undefined ? "–" : JSON.stringify(b)}</td>
                <td className={`py-1.5 font-mono text-xs ${changed ? "font-bold text-brand" : "text-ink-soft"}`}>{a === undefined ? "–" : JSON.stringify(a)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function AuditorPage() {
  const [items, setItems] = useState<AuditEntry[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [actorType, setActorType] = useState("");
  const [action, setAction] = useState("");
  const [entityId, setEntityId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const q = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
    if (actorType) q.set("actor_type", actorType);
    if (action.trim()) q.set("action", action.trim());
    if (entityId.trim()) q.set("entity_id", entityId.trim());
    try {
      const r = await api<{ items: AuditEntry[]; total: number }>("GET", `/audit?${q}`, { token: getSession()?.token });
      setItems(r.items);
      setTotal(r.total);
      setError(null);
    } catch (e) {
      setError(errorText(e, "Could not load the audit log."));
    } finally {
      setLoading(false);
    }
  }, [offset, actorType, action, entityId]);

  useLoader(load);

  return (
    <PageShell title="Audit log" urdu="آڈٹ لاگ" roles={["auditor", "admin"]} wide actions={<Button variant="ghost" loading={loading} icon="refresh" en="Refresh" onClick={() => void load()} />}>
      <Notice tone="info" title="Append-only. Every user, AI and agent action is recorded here, and nothing can be edited or deleted." />

      <div className="card grid gap-4 p-5 sm:grid-cols-3">
        <Field label="Who">
          <select className="input" value={actorType} onChange={(e) => { setOffset(0); setActorType(e.target.value); }}>
            <option value="">Everyone</option>
            <option value="user">Users</option>
            <option value="ai">AI</option>
            <option value="agent">Agent</option>
            <option value="system">System</option>
          </select>
        </Field>
        <Field label="Action (exact)">
          <input className="input" value={action} onChange={(e) => { setOffset(0); setAction(e.target.value); }} placeholder="case.decide" />
        </Field>
        <Field label="Case / entity id">
          <input className="input" value={entityId} onChange={(e) => { setOffset(0); setEntityId(e.target.value); }} placeholder="case-0001" />
        </Field>
      </div>

      {error && <Notice tone="bad">{error}</Notice>}
      {!items && !error && <div className="space-y-2"><Skeleton className="h-16" /><Skeleton className="h-16" /><Skeleton className="h-16" /></div>}
      {items && items.length === 0 && <EmptyState icon="scroll" en="Nothing matches these filters." />}

      <ul className="space-y-2">
        {items?.map((e) => (
          <li key={e.id} className="card overflow-hidden">
            <button type="button" aria-expanded={open === e.id} onClick={() => setOpen(open === e.id ? null : e.id)} className="flex min-h-[64px] w-full flex-wrap items-center gap-x-4 gap-y-1 p-4 text-left">
              <Badge tone={ACTOR_TONE[e.actor_type] ?? "neutral"}>{e.actor_type}</Badge>
              <span className="font-extrabold text-heading">{e.action}</span>
              <span className="text-sm text-ink-soft">{e.target}</span>
              <span className="ms-auto text-xs text-ink-soft">{formatTime(e.timestamp)}</span>
            </button>
            {open === e.id && (
              <div className="space-y-2 border-t border-line bg-cream-2 p-4">
                <p className="text-xs text-ink-soft">actor {e.actor} · id {e.id}{e.request_id ? ` · request ${e.request_id}` : ""}</p>
                <Diff before={e.before} after={e.after} />
              </div>
            )}
          </li>
        ))}
      </ul>

      {items && total > PAGE && (
        <div className="flex items-center justify-between gap-3">
          <Button variant="ghost" disabled={offset === 0} icon="arrowLeft" en="Newer" onClick={() => setOffset(Math.max(0, offset - PAGE))} />
          <span className="text-sm font-bold text-ink-soft">{offset + 1}–{Math.min(offset + PAGE, total)} of {total}</span>
          <Button variant="ghost" disabled={offset + PAGE >= total} icon="arrow" en="Older" onClick={() => setOffset(offset + PAGE)} />
        </div>
      )}
    </PageShell>
  );
}
