"use client";
import { useEffect, useState } from "react";
import { PageShell } from "@/components/PageShell";
import { Card, Notice, SectionTitle, Skeleton, Stat, pretty } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { getSession } from "@/lib/auth";
import type { ScamMap } from "@/lib/types";

type Live = {
  decisions: { total: number; ai_total: number; agent_total: number; officer_total: number; by_action: Record<string, number>; officer_by_action: Record<string, number>; by_rule_version: Record<string, number> };
  officer_vs_ai: { compared: number; overrides: number; override_rate: number | null; pairs: Record<string, number> };
  confidence: { ai_average: number | null; by_action: Record<string, number> };
  pipeline: { runs: number; average_seconds: number | null; max_seconds: number | null };
  messages: { total: number; by_label: Record<string, number>; average_confidence: number | null };
  model_eval?: Record<string, unknown> | null;
};

const COLORS: Record<string, string> = { auto_handle: "bg-ok-700", ask_more: "bg-saffron-500", send_to_human: "bg-bad-700", scam: "bg-bad-700", genuine: "bg-ok-700", unsure: "bg-saffron-500", approve: "bg-ok-700", reject: "bg-bad-700", ask_more_: "bg-saffron-500" };

/** Horizontal bars with the number printed at the end of each bar (no legend needed). */
function Bars({ data, colors = COLORS, max }: { data: Record<string, number> | { label: string; value: number }[]; colors?: Record<string, string>; max?: number }) {
  const rows = Array.isArray(data) ? data : Object.entries(data).map(([label, value]) => ({ label, value }));
  const top = max ?? Math.max(1, ...rows.map((r) => r.value));
  if (rows.length === 0) return <p className="text-sm text-ink-soft">No data yet.</p>;
  return (
    <ul className="space-y-2.5">
      {rows.map((r) => (
        <li key={r.label} className="grid grid-cols-[minmax(0,13rem)_1fr_auto] items-center gap-3 text-sm">
          <span className="font-bold leading-snug" title={pretty(r.label)}>{pretty(r.label)}</span>
          <span className="h-4 overflow-hidden rounded-full bg-cream-2">
            <span className={`block h-full rounded-full ${colors[r.label] ?? "bg-teal-700"}`} style={{ width: `${Math.max(2, (r.value / top) * 100)}%` }} />
          </span>
          <span className="w-8 text-right font-extrabold tabular-nums">{r.value}</span>
        </li>
      ))}
    </ul>
  );
}

const pct = (n: number | null | undefined) => (typeof n === "number" ? `${Math.round(n * 100)}%` : "–");

export default function EvalPage() {
  const [live, setLive] = useState<Live | null>(null);
  const [map, setMap] = useState<ScamMap | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getSession()?.token;
    api<Live>("GET", "/eval", { token }).then(setLive).catch((e) => setError(errorText(e, "Could not load the numbers.")));
    api<ScamMap>("GET", "/scam-map", { token }).then(setMap).catch(() => undefined);
  }, []);

  const dayMax = Math.max(1, ...(map?.by_day.map((d) => d.count) ?? [1]));

  return (
    <PageShell title="Insights" urdu="اعداد و شمار" roles={["officer", "admin", "auditor"]} wide>
      <Notice tone="info" title="Numbers computed from what the system actually did.">
        <p>These come from stored decisions, jobs and checked messages, not from claims. Small groups are folded together to protect privacy.</p>
      </Notice>
      {error && <Notice tone="bad">{error}</Notice>}
      {!live && !error && <div className="grid gap-4 sm:grid-cols-4"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>}

      {live && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat icon="gavel" label="Decisions" value={live.decisions.total} sub={`${live.decisions.ai_total} AI · ${live.decisions.officer_total} officer`} />
            <Stat icon="user" tone="warn" label="Officer overrides" value={pct(live.officer_vs_ai.override_rate)} sub={`${live.officer_vs_ai.overrides} of ${live.officer_vs_ai.compared} compared`} />
            <Stat icon="sparkle" tone="ok" label="Avg AI confidence" value={pct(live.confidence.ai_average)} />
            <Stat icon="clock" tone="info" label="Avg pipeline" value={live.pipeline.average_seconds != null ? `${live.pipeline.average_seconds}s` : "–"} sub={`${live.pipeline.runs} runs`} />
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card className="space-y-3">
              <SectionTitle icon="chart" en="What the AI decided" ur="اے آئی کے فیصلے" />
              <Bars data={live.decisions.by_action} />
            </Card>
            <Card className="space-y-3">
              <SectionTitle icon="gavel" en="What officers decided" ur="افسروں کے فیصلے" />
              <Bars data={live.decisions.officer_by_action} />
              {Object.keys(live.officer_vs_ai.pairs).length > 0 && (
                <div className="rounded-2xl bg-cream-2 p-3 text-sm">
                  <p className="mb-1 font-extrabold">Where an officer disagreed with the AI</p>
                  <ul className="space-y-1">{Object.entries(live.officer_vs_ai.pairs).map(([k, v]) => <li key={k} className="flex justify-between"><span>{k.replace(/_/g, " ")}</span><strong>{v}</strong></li>)}</ul>
                </div>
              )}
            </Card>
            <Card className="space-y-3">
              <SectionTitle icon="sparkle" en="Confidence by action" ur="اعتماد بلحاظ اقدام" />
              <Bars data={Object.fromEntries(Object.entries(live.confidence.by_action).map(([k, v]) => [k, Math.round(v * 100)]))} max={100} />
              <p className="text-xs text-ink-soft">Percent. Low confidence should lead to a person, never a guess.</p>
            </Card>
            <Card className="space-y-3">
              <SectionTitle icon="shield" en="Messages checked" ur="چیک کیے گئے پیغامات" />
              <Bars data={live.messages.by_label} />
              <p className="text-xs text-ink-soft">{live.messages.total} checked · average confidence {pct(live.messages.average_confidence)}</p>
            </Card>
          </div>
        </>
      )}

      {map && (
        <Card className="space-y-5">
          <SectionTitle icon="map" en="Scam Map" ur="سکیم نقشہ" right={<span className="text-sm font-bold text-ink-soft">{map.total} reports · last {map.window_days} days</span>} />
          <div className="grid gap-6 lg:grid-cols-2">
            <div>
              <p className="mb-2 font-extrabold">By area</p>
              <Bars data={map.by_area.map((a) => ({ label: a.area, value: a.count }))} colors={{}} />
            </div>
            <div>
              <p className="mb-2 font-extrabold">By reason</p>
              <Bars data={map.by_reason.map((a) => ({ label: a.reason, value: a.count }))} colors={{}} />
            </div>
          </div>
          <div>
            <p className="mb-2 font-extrabold">By day</p>
            <div className="flex h-28 items-end gap-1" role="img" aria-label="Reports per day">
              {map.by_day.map((d) => (
                <span key={d.day} title={`${d.day}: ${d.count}`} className="flex-1 rounded-t-md bg-teal-700/80" style={{ height: `${Math.max(4, (d.count / dayMax) * 100)}%` }} />
              ))}
            </div>
          </div>
          <p className="text-xs text-ink-soft">No message text or sender is stored here. Groups of fewer than {map.min_group_size} are shown as “other”.</p>
        </Card>
      )}
    </PageShell>
  );
}
