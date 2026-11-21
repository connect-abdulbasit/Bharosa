"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { PageShell } from "@/components/PageShell";
import { ThresholdBar } from "@/components/ThresholdBar";
import { Badge, Button, Card, Field, Meter, Notice, SectionTitle, Skeleton, pretty } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { getSession } from "@/lib/auth";
import type { RuleSimulation, RuleSummary, RuleVersion } from "@/lib/types";

const PRESETS = [
  { label: "Stricter: auto ≥ 95%", auto: 0.95, ask: 0.6 },
  { label: "Looser ask floor: ask ≥ 50%", auto: 0.9, ask: 0.5 },
  { label: "Much stricter: auto ≥ 98%, ask ≥ 70%", auto: 0.98, ask: 0.7 },
];

export default function TwinPage() {
  const [rule, setRule] = useState<RuleSummary | null>(null);
  const [cur, setCur] = useState<RuleVersion | null>(null);
  const [auto, setAuto] = useState(0.95);
  const [ask, setAsk] = useState(0.6);
  const [res, setRes] = useState<RuleSimulation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getSession()?.token;
    api<{ items: RuleSummary[] }>("GET", "/rules", { token })
      .then(async (l) => {
        const r = l.items[0];
        if (!r) return;
        setRule(r);
        const v = await api<{ versions: RuleVersion[] }>("GET", `/rules/${r.id}/versions`, { token });
        const c = v.versions.find((x) => x.version === r.current_version) ?? v.versions[0] ?? null;
        setCur(c);
        if (c) {
          setAuto(Math.min(1, +(c.auto_handle_min + 0.05).toFixed(2)));
          setAsk(c.ask_more_min);
        }
      })
      .catch((e) => setError(errorText(e, "Could not load the current rule.")));
  }, []);

  async function run() {
    if (!rule) return;
    setBusy(true);
    setError(null);
    try {
      setRes(await api<RuleSimulation>("POST", `/rules/${rule.id}/simulate`, { body: { auto_handle_min: auto, ask_more_min: ask }, token: getSession()?.token }));
    } catch (e) {
      setRes(null);
      setError(errorText(e, "The simulation could not run."));
    } finally {
      setBusy(false);
    }
  }

  const valid = ask > 0 && ask < auto && auto <= 1;
  const pct = res && res.simulated_cases > 0 ? res.would_change / res.simulated_cases : 0;

  return (
    <PageShell title="Digital Twin" urdu="ڈیجیٹل ٹوِن" roles={["admin"]} back={{ href: "/admin", label: "Admin · ایڈمن" }} wide>
      <Notice tone="info" title="Test a rule change on past cases before you publish it.">
        <p>Nothing is saved. We re-run only the decide step on the stored inputs of real past decisions.</p>
        <p dir="rtl" lang="ur">اصول بدلنے سے پہلے پرانے کیسوں پر آزمائیں۔ کچھ محفوظ نہیں ہوتا۔</p>
      </Notice>

      <div className="grid items-start gap-5 lg:grid-cols-5">
        <Card className="rise space-y-4 lg:col-span-2">
          <SectionTitle icon="flask" en="Proposed change" ur="مجوزہ تبدیلی" />
          {!cur ? <Skeleton className="h-40" /> : (
            <>
              <div>
                <p className="mb-1 text-sm font-bold text-ink-soft">Now (v{cur.version})</p>
                <ThresholdBar askMore={cur.ask_more_min} autoHandle={cur.auto_handle_min} />
              </div>
              <div>
                <p className="mb-1 text-sm font-bold text-saffron-600">Proposed</p>
                <ThresholdBar askMore={ask} autoHandle={auto} />
              </div>
              <div className="flex flex-wrap gap-2">
                {PRESETS.map((p) => (
                  <button key={p.label} type="button" onClick={() => { setAuto(p.auto); setAsk(p.ask); }} className="min-h-[44px] rounded-full border border-line bg-surface px-3 text-sm font-bold hover:border-teal-600">{p.label}</button>
                ))}
              </div>
              <Field label={`Auto-handle from ${Math.round(auto * 100)}%`}>
                <input type="range" min={0.5} max={1} step={0.01} value={auto} onChange={(e) => setAuto(Number(e.target.value))} className="h-10 w-full text-teal-600" />
              </Field>
              <Field label={`Ask for more from ${Math.round(ask * 100)}%`}>
                <input type="range" min={0.1} max={0.95} step={0.01} value={ask} onChange={(e) => setAsk(Number(e.target.value))} className="h-10 w-full text-saffron-500" />
              </Field>
              {!valid && <Notice tone="bad">Ask threshold must be below the auto-handle threshold.</Notice>}
              <Button full loading={busy} disabled={!valid} icon="flask" en="Run on past cases" ur="پرانے کیسوں پر چلائیں" onClick={() => void run()} />
            </>
          )}
          {error && <Notice tone="bad">{error}</Notice>}
        </Card>

        <div className="space-y-5 lg:col-span-3">
          {!res && !busy && (
            <Card className="flex flex-col items-center gap-3 p-10 text-center text-ink-soft">
              <span className="flex h-16 w-16 items-center justify-center rounded-full bg-teal-50 text-brand"><Icon name="flask" size={32} /></span>
              <p className="text-lg font-bold">Pick a change and run it to see what would happen.</p>
            </Card>
          )}
          {busy && <Skeleton className="h-64" />}
          {res && (
            <>
              <Card className="rise space-y-4" aria-live="polite">
                <p className="text-sm font-bold uppercase tracking-wide text-ink-soft">Result</p>
                <p className="text-4xl font-extrabold text-heading">
                  {res.would_change} <span className="text-2xl font-bold text-ink-soft">of {res.simulated_cases} past decisions would change</span>
                </p>
                <Meter value={pct} tone={pct > 0.3 ? "bad" : pct > 0.1 ? "warn" : "ok"} label="Share of decisions that change" />
                {res.skipped_no_inputs > 0 && (
                  <p className="text-sm text-ink-soft">{res.skipped_no_inputs} of {res.total_cases} decisions were skipped because their original inputs were not stored (sample data).</p>
                )}
              </Card>

              {Object.keys(res.by_transition).length > 0 && (
                <Card className="rise space-y-3">
                  <SectionTitle icon="chart" en="What changes into what" ur="کیا کس میں بدلتا ہے" />
                  <ul className="space-y-2">
                    {Object.entries(res.by_transition).map(([k, v]) => (
                      <li key={k} className="flex items-center justify-between gap-3 rounded-2xl bg-cream-2 p-3">
                        <span className="font-bold">{k.split("->").map((s) => pretty(s.trim())).join("  →  ")}</span>
                        <Badge tone="brand">{v}</Badge>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {res.examples.length > 0 && (
                <Card className="rise space-y-3">
                  <SectionTitle icon="list" en="Examples" ur="مثالیں" />
                  <ul className="space-y-2">
                    {res.examples.map((e) => (
                      <li key={e.case_id} className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-cream-2 p-3">
                        <Link href={`/officer/case/${e.case_id}`} className="font-bold text-brand underline">{e.case_id}</Link>
                        <span>{pretty(e.old_action)} → <strong>{pretty(e.new_action)}</strong></span>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              <Link href="/admin/rules" className="inline-flex min-h-[52px] items-center gap-2 rounded-2xl bg-teal-700 px-5 font-extrabold text-white">
                Happy with it? Publish in Rules <Icon name="arrow" size={20} />
              </Link>
            </>
          )}
        </div>
      </div>
    </PageShell>
  );
}
