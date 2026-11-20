"use client";
import { useEffect, useState } from "react";
import { PageShell } from "@/components/PageShell";
import { ReadAloud } from "@/components/ReadAloud";
import { StatusTimeline, type TimelineStep } from "@/components/StatusTimeline";
import { api } from "@/lib/api";
import { getSession } from "@/lib/auth";
import type { CaseDetail } from "@/lib/types";

const ORDER = ["submitted", "checking", "needs_more_proof", "with_officer", "decided"] as const;
const STEPS: Record<(typeof ORDER)[number], { icon: string; en: string; ur: string }> = {
  submitted: { icon: "📨", en: "Submitted", ur: "جمع ہو گیا" },
  checking: { icon: "🔎", en: "Checking", ur: "جانچ ہو رہی ہے" },
  needs_more_proof: { icon: "📎", en: "Needs more proof", ur: "مزید ثبوت چاہیے" },
  with_officer: { icon: "👮", en: "With an officer", ur: "افسر کے پاس" },
  decided: { icon: "⚖️", en: "Decided", ur: "فیصلہ ہو گیا" },
};
const CURRENT: Record<string, (typeof ORDER)[number]> = {
  draft: "submitted", submitted: "checking", needs_more_proof: "needs_more_proof",
  with_officer: "with_officer", approved: "decided", rejected: "decided", closed: "decided",
};

export default function StatusPage() {
  const [c, setC] = useState<CaseDetail | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const token = getSession()?.token;
    api<{ items: { id: string }[] }>("GET", "/cases", { token })
      .then((r) => (r.items[0] ? api<CaseDetail>("GET", `/cases/${r.items[0].id}`, { token }) : null))
      .then((d) => (d ? setC(d) : setError(true)))
      .catch(() => setError(true));
  }, []);

  let steps: TimelineStep[] = [];
  let spoken = { ur: "", en: "" };
  if (c) {
    const cur = ORDER.indexOf(CURRENT[c.status] ?? "checking");
    steps = ORDER.map((k, i) => ({
      key: k, ...STEPS[k],
      state: i < cur ? "done" : i === cur ? "current" : "todo",
      time: i === 0 ? c.created_at : i === cur ? c.updated_at : null,
    }));
    const now = STEPS[ORDER[cur]];
    spoken = {
      ur: `آپ کا دعویٰ اس وقت: ${now.ur}۔ ${c.explanation_ur ?? ""}`,
      en: `Your claim is now: ${now.en}. ${c.explanation_en ?? ""}`,
    };
  }

  return (
    <PageShell title="Where is my claim?" urdu="میرا دعویٰ کہاں ہے؟" roles={["citizen", "helper"]} back={{ href: "/citizen", label: "My Bharosa / میرا بھروسہ" }}>
      {error && <p role="alert" className="font-semibold text-red-700">Could not load your claim. Try again later. · دعویٰ لوڈ نہیں ہو سکا۔</p>}
      {!c && !error && <p>Loading… · لوڈ ہو رہا ہے…</p>}
      {c && (
        <>
          <p className="text-lg">
            Claim for <strong>{c.citizen_name}</strong>: PKR {c.amount_claimed_pkr} ({c.claim_type === "short_paid" ? "short paid" : "missing"})
          </p>
          <StatusTimeline steps={steps} />
          <section className="space-y-2 rounded-2xl border-2 bg-gray-50 p-4 text-black">
            <p className="text-lg">{c.explanation_en}</p>
            <p dir="rtl" lang="ur" className="text-xl">{c.explanation_ur}</p>
            <ReadAloud ur={spoken.ur} en={spoken.en} />
          </section>
        </>
      )}
    </PageShell>
  );
}
