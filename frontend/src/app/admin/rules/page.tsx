"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import { PageShell } from "@/components/PageShell";
import { ThresholdBar } from "@/components/ThresholdBar";
import { formatTime } from "@/components/StatusTimeline";
import { Badge, Button, Card, Field, Notice, SectionTitle, Skeleton, pretty } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { useLoader } from "@/lib/hooks";
import type { RuleSummary, RuleVersion } from "@/lib/types";

export default function RulesPage() {
  const [rule, setRule] = useState<RuleSummary | null>(null);
  const [versions, setVersions] = useState<RuleVersion[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [auto, setAuto] = useState(0.9);
  const [ask, setAsk] = useState(0.6);
  const [flags, setFlags] = useState<string[]>([]);
  const [newFlag, setNewFlag] = useState("");
  const [note, setNote] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);

  const load = useCallback(async () => {
    const token = getSession()?.token;
    try {
      const list = await api<{ items: RuleSummary[] }>("GET", "/rules", { token });
      const r = list.items[0];
      if (!r) return setError("No rules found.");
      setRule(r);
      const v = await api<{ versions: RuleVersion[] }>("GET", `/rules/${r.id}/versions`, { token });
      setVersions(v.versions);
      const cur = v.versions.find((x) => x.version === r.current_version) ?? v.versions[0];
      if (cur) {
        setAuto(cur.auto_handle_min);
        setAsk(cur.ask_more_min);
        setFlags(cur.red_flags);
      }
    } catch (e) {
      setError(errorText(e, "Could not load the rules."));
    }
  }, []);
  useLoader(load);

  const current = versions?.find((v) => v.version === rule?.current_version) ?? versions?.[0];
  const valid = ask > 0 && ask < auto && auto <= 1;
  const unchanged = !!current && current.auto_handle_min === auto && current.ask_more_min === ask && JSON.stringify(current.red_flags) === JSON.stringify(flags);

  async function publish() {
    if (!rule) return;
    setBusy(true);
    setMsg(null);
    try {
      await api("POST", `/rules/${rule.id}/versions`, { body: { auto_handle_min: auto, ask_more_min: ask, red_flags: flags, note: note.trim() || undefined }, token: getSession()?.token });
      setMsg({ tone: "ok", text: "Published as a new version. Old versions are untouched and still shown on past decisions." });
      setConfirm(false);
      setNote("");
      await load();
    } catch (e) {
      setMsg({ tone: "bad", text: errorText(e, "Could not publish.") });
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell title="Decision rules" urdu="فیصلے کے قواعد" roles={["admin"]} back={{ href: "/admin", label: "Admin · ایڈمن" }} wide>
      {error && <Notice tone="bad">{error}</Notice>}
      {!rule && !error && <Skeleton className="h-64" />}
      {rule && current && (
        <div className="grid items-start gap-5 lg:grid-cols-5">
          <div className="space-y-5 lg:col-span-3">
            <Card className="rise space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-xl font-extrabold text-heading">{rule.name}</p>
                  <p className="text-sm text-ink-soft">Active since {formatTime(current.created_at)}</p>
                </div>
                <Badge tone="brand">version {rule.current_version}</Badge>
              </div>
              <ThresholdBar askMore={current.ask_more_min} autoHandle={current.auto_handle_min} />
              <div>
                <p className="mb-2 text-sm font-bold text-ink-soft">Red flags: any one of these always sends the case to a person</p>
                <div className="flex flex-wrap gap-2">{current.red_flags.map((f) => <Badge key={f} tone="bad" icon="alert">{pretty(f)}</Badge>)}</div>
              </div>
            </Card>

            <Card className="rise rise-1 space-y-3">
              <SectionTitle icon="scroll" en="Version history" ur="ورژن کی تاریخ" />
              <ul className="space-y-2">
                {versions?.map((v) => (
                  <li key={v.version} className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-cream-2 p-3">
                    <span className="font-extrabold">v{v.version}</span>
                    <span className="text-sm">auto ≥ {Math.round(v.auto_handle_min * 100)}% · ask ≥ {Math.round(v.ask_more_min * 100)}%</span>
                    <span className="text-xs text-ink-soft">{v.note ?? "–"} · {formatTime(v.created_at)}</span>
                    {v.version === rule.current_version && <Badge tone="ok">active</Badge>}
                  </li>
                ))}
              </ul>
              <p className="text-xs text-ink-soft">Versions are immutable. Every decision stores the version it used.</p>
            </Card>
          </div>

          <Card className="rise rise-2 space-y-4 lg:col-span-2">
            <SectionTitle icon="sliders" en="Propose a new version" ur="نیا ورژن تجویز کریں" />
            <ThresholdBar askMore={ask} autoHandle={auto} />
            <Field label={`Auto-handle from ${Math.round(auto * 100)}%`} ur="خودکار">
              <input type="range" min={0.5} max={1} step={0.01} value={auto} onChange={(e) => setAuto(Number(e.target.value))} className="h-10 w-full text-teal-600" />
            </Field>
            <Field label={`Ask for more from ${Math.round(ask * 100)}%`} ur="مزید ثبوت">
              <input type="range" min={0.1} max={0.95} step={0.01} value={ask} onChange={(e) => setAsk(Number(e.target.value))} className="h-10 w-full text-saffron-500" />
            </Field>
            <div>
              <p className="mb-2 font-bold text-heading">Red flags</p>
              <div className="flex flex-wrap gap-2">
                {flags.map((f) => (
                  <button key={f} type="button" onClick={() => setFlags(flags.filter((x) => x !== f))} className="inline-flex min-h-[40px] items-center gap-1 rounded-full bg-bad-soft px-3 text-sm font-bold text-bad-ink" aria-label={`Remove ${f}`}>
                    {pretty(f)} ✕
                  </button>
                ))}
              </div>
              <div className="mt-2 flex gap-2">
                <input className="input" value={newFlag} onChange={(e) => setNewFlag(e.target.value)} placeholder="add a flag name" aria-label="New red flag" />
                <Button variant="ghost" icon="plus" en="Add" disabled={!newFlag.trim()} onClick={() => { setFlags([...flags, newFlag.trim().toLowerCase().replace(/\s+/g, "_")]); setNewFlag(""); }} />
              </div>
              {flags.length === 0 && <p className="mt-1 text-sm font-semibold text-bad-ink">No red flags: nothing will force a human check.</p>}
            </div>
            <Field label="Why this change? (saved with the version)">
              <input className="input" value={note} onChange={(e) => setNote(e.target.value)} />
            </Field>
            {!valid && <Notice tone="bad">The ask-more threshold must be above 0 and below the auto-handle threshold.</Notice>}
            {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
            <Link href="/admin/twin" className="inline-flex min-h-[44px] items-center gap-2 font-bold text-brand underline">Test it on past cases first (Digital Twin)</Link>
            {confirm ? (
              <div className="space-y-2 rounded-2xl bg-saffron-50 p-4">
                <p className="font-extrabold">Publish v{rule.current_version + 1}? It applies to new decisions immediately.</p>
                <div className="grid grid-cols-2 gap-3">
                  <Button loading={busy} icon="check" en="Yes, publish" onClick={() => void publish()} />
                  <Button variant="ghost" disabled={busy} en="Cancel" onClick={() => setConfirm(false)} />
                </div>
              </div>
            ) : (
              <Button full disabled={!valid || unchanged} icon="send" en="Publish new version" ur="نیا ورژن شائع کریں" onClick={() => setConfirm(true)} />
            )}
          </Card>
        </div>
      )}
    </PageShell>
  );
}
