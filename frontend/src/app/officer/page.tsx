"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/Icon";
import { PageShell } from "@/components/PageShell";
import { Badge, EmptyState, Meter, Notice, Skeleton, Stat, pretty } from "@/components/ui";
import { formatTime } from "@/components/StatusTimeline";
import { api, errorText } from "@/lib/api";
import { getSession } from "@/lib/auth";
import type { QueueItem } from "@/lib/types";

const ACTION_TONE = { auto_handle: "ok", ask_more: "warn", send_to_human: "bad" } as const;

export default function OfficerQueue() {
  const [items, setItems] = useState<QueueItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "high">("all");

  useEffect(() => {
    api<{ items: QueueItem[] }>("GET", "/queue", { token: getSession()?.token })
      .then((r) => setItems(r.items))
      .catch((e) => setError(errorText(e, "Could not load the queue.")));
  }, []);

  const high = useMemo(() => items?.filter((q) => q.risk_score >= 0.5).length ?? 0, [items]);
  const low = useMemo(() => items?.filter((q) => q.confidence < 0.6).length ?? 0, [items]);
  const shown = items?.filter((q) => (filter === "high" ? q.risk_score >= 0.5 : true)) ?? [];

  return (
    <PageShell title="Review queue" urdu="جائزہ قطار" roles={["officer", "admin"]} wide>
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat icon="list" label="Waiting" value={items?.length ?? "–"} sub="cases need a person" />
        <Stat icon="alert" tone="bad" label="High risk" value={items ? high : "–"} sub="risk 50% or more" />
        <Stat icon="question" tone="warn" label="AI unsure" value={items ? low : "–"} sub="confidence under 60%" />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-ink-soft">Sorted by risk (high first), then confidence (low first).<span dir="rtl" lang="ur" className="ur-line">خطرے کے لحاظ سے ترتیب۔</span></p>
        <div className="flex gap-2" role="radiogroup" aria-label="Filter">
          {(["all", "high"] as const).map((f) => (
            <button key={f} role="radio" aria-checked={filter === f} onClick={() => setFilter(f)} className={`min-h-[44px] rounded-full px-4 text-sm font-bold ${filter === f ? "bg-teal-700 text-white" : "border border-line bg-surface"}`}>
              {f === "all" ? "All" : "High risk"}
            </button>
          ))}
        </div>
      </div>

      {error && <Notice tone="bad">{error}</Notice>}
      {!items && !error && <div className="space-y-3"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>}
      {items && shown.length === 0 && <EmptyState icon="checkCircle" en="The queue is empty." ur="قطار خالی ہے۔" />}

      <ul className="grid gap-4 lg:grid-cols-2">
        {shown.map((q, i) => (
          <li key={q.case_id} className={`rise rise-${Math.min(i + 1, 4)}`}>
            <Link href={`/officer/case/${q.case_id}`} className="card card-lift block h-full space-y-3 p-5">
              <span className="flex items-start justify-between gap-3">
                <span>
                  <span className="block text-xl font-extrabold text-heading">{q.citizen_name}</span>
                  <span className="block text-xs text-ink-soft">{q.case_id} · waiting since {formatTime(q.waiting_since)}</span>
                </span>
                <Badge tone={q.risk_score >= 0.5 ? "bad" : q.risk_score >= 0.3 ? "warn" : "neutral"} icon="alert">risk {Math.round(q.risk_score * 100)}%</Badge>
              </span>
              <span className="grid grid-cols-2 gap-4">
                <span>
                  <span className="mb-1 flex justify-between text-xs font-bold text-ink-soft"><span>AI confidence</span><span>{Math.round(q.confidence * 100)}%</span></span>
                  <Meter value={q.confidence} tone={q.confidence >= 0.9 ? "ok" : q.confidence >= 0.6 ? "warn" : "bad"} label="Confidence" />
                </span>
                <span className="text-right">
                  <span className="block text-xs font-bold text-ink-soft">AI suggests</span>
                  <Badge tone={(ACTION_TONE as Record<string, "ok" | "warn" | "bad">)[q.recommended_action] ?? "neutral"}>{pretty(q.recommended_action)}</Badge>
                </span>
              </span>
              <span className="block text-sm text-ink-soft">{q.ai_reason ?? q.reasons.join("; ")}</span>
              <span className="flex items-center gap-1 text-sm font-extrabold text-brand">Review case <Icon name="arrow" size={16} /></span>
            </Link>
          </li>
        ))}
      </ul>
    </PageShell>
  );
}
