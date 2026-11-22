"use client";
import { useCallback, useEffect, useState } from "react";
import { PageShell } from "@/components/PageShell";
import { ReadAloud } from "@/components/ReadAloud";
import { StatusTimeline, type TimelineStep } from "@/components/StatusTimeline";
import { Badge, Button, Card, EmptyState, LinkButton, Notice, SectionTitle, Skeleton } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { useLoader } from "@/lib/hooks";
import { statusLook } from "@/lib/status";
import type { CaseDetail, CaseSummary } from "@/lib/types";

const ORDER = ["submitted", "checking", "needs_more_proof", "with_officer", "decided"] as const;
const STEPS: Record<(typeof ORDER)[number], { icon: TimelineStep["icon"]; en: string; ur: string }> = {
  submitted: { icon: "send", en: "Submitted", ur: "جمع ہو گیا" },
  checking: { icon: "search", en: "Checking", ur: "جانچ ہو رہی ہے" },
  needs_more_proof: { icon: "file", en: "Needs more proof", ur: "مزید ثبوت چاہیے" },
  with_officer: { icon: "user", en: "With an officer", ur: "افسر کے پاس" },
  decided: { icon: "gavel", en: "Decided", ur: "فیصلہ ہو گیا" },
};
const CURRENT: Record<string, (typeof ORDER)[number]> = {
  draft: "submitted",
  submitted: "checking",
  needs_more_proof: "needs_more_proof",
  with_officer: "with_officer",
  approved: "decided",
  rejected: "decided",
  closed: "decided",
};

export default function StatusPage() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [c, setC] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (id: string) => {
    setLoading(true);
    try {
      setC(await api<CaseDetail>("GET", `/cases/${id}`, { token: getSession()?.token }));
      setError(null);
    } catch (e) {
      setError(errorText(e, "Could not load your claim. Try again later."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    api<{ items: CaseSummary[] }>("GET", "/cases", { token: getSession()?.token })
      .then((r) => {
        setCases(r.items);
        if (r.items[0]) setSel(r.items[0].id);
      })
      .catch((e) => {
        setCases([]);
        setError(errorText(e, "Could not load your claims."));
      });
  }, []);

  const loadSel = useCallback(() => (sel ? load(sel) : undefined), [sel, load]);
  useLoader(loadSel);

  // The agent may still be working: refresh quietly while the claim is only "submitted".
  useEffect(() => {
    if (!sel || c?.status !== "submitted") return;
    const t = setInterval(() => void load(sel), 5000);
    return () => clearInterval(t);
  }, [sel, c?.status, load]);

  let steps: TimelineStep[] = [];
  let spoken = { ur: "", en: "" };
  if (c) {
    const cur = ORDER.indexOf(CURRENT[c.status] ?? "checking");
    steps = ORDER.map((k, i) => ({
      key: k,
      ...STEPS[k],
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
    <PageShell
      title="Where is my claim?"
      urdu="میرا دعویٰ کہاں ہے؟"
      roles={["citizen", "helper"]}
      wide
      back={{ href: "/citizen", label: "My Bharosa · میرا بھروسہ" }}
      actions={sel ? <Button variant="ghost" loading={loading} icon="refresh" en="Refresh" ur="تازہ کریں" onClick={() => void load(sel)} /> : undefined}
    >
      {error && <Notice tone="bad">{error}</Notice>}
      {!cases && !error && (
        <div className="space-y-3">
          <Skeleton className="h-20" />
          <Skeleton className="h-64" />
        </div>
      )}
      {cases && cases.length === 0 && !error && <EmptyState icon="file" en="No claims yet." ur="ابھی کوئی دعویٰ نہیں۔" />}

      {cases && cases.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="My claims">
          {cases.map((k) => (
            <button
              key={k.id}
              role="tab"
              aria-selected={sel === k.id}
              onClick={() => setSel(k.id)}
              className={`min-h-[48px] shrink-0 rounded-full border-2 px-4 font-bold ${sel === k.id ? "border-teal-700 bg-teal-700 text-white" : "border-line bg-surface"}`}
            >
              PKR {k.amount_claimed_pkr.toLocaleString("en-US")}
            </button>
          ))}
        </div>
      )}

      {c && (
        <div className="grid items-start gap-6 lg:grid-cols-2">
          <div className="space-y-6">
          <Card className="rise flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-bold uppercase tracking-wide text-ink-soft">Claim · دعویٰ</p>
              <p className="text-2xl font-extrabold text-heading">PKR {c.amount_claimed_pkr.toLocaleString("en-US")}</p>
              <p className="text-ink-soft">{c.claim_type === "short_paid" ? "Short paid" : "Missing payment"}</p>
            </div>
            <Badge tone={statusLook(c.status).tone}>
              {statusLook(c.status).en} <span aria-hidden>·</span> <span dir="rtl" lang="ur">{statusLook(c.status).ur}</span>
            </Badge>
          </Card>

          <Card className="rise rise-1">
            <SectionTitle icon="clock" en="Progress" ur="پیش رفت" />
            <StatusTimeline steps={steps} />
          </Card>
          </div>

          <Card className="rise rise-2 space-y-3 lg:sticky lg:top-28">
            <SectionTitle icon="sparkle" en="What this means" ur="اس کا مطلب" />
            {c.explanation_en ? <p className="text-lg font-semibold">{c.explanation_en}</p> : <p className="text-ink-soft">We will explain here as soon as there is news.</p>}
            {c.explanation_ur && <p dir="rtl" lang="ur" className="text-xl font-semibold">{c.explanation_ur}</p>}
            <ReadAloud ur={spoken.ur} en={spoken.en} />
            {c.status === "needs_more_proof" && (
              <div className="space-y-2 rounded-2xl bg-warn-soft p-4 text-warn-ink">
                <p className="font-extrabold">
                  To give more proof, send your claim again: say your name and the problem clearly, and add a clear photo of your ID card.
                  <span dir="rtl" lang="ur" className="ur-line">مزید ثبوت دینے کے لیے دعویٰ دوبارہ بھیجیں: اپنا نام اور مسئلہ صاف بتائیں اور شناختی کارڈ کی صاف تصویر دیں۔</span>
                </p>
                <LinkButton href="/citizen/claim" variant="accent" icon="mic" en="Send more proof" ur="مزید ثبوت بھیجیں" full />
              </div>
            )}
          </Card>
        </div>
      )}
    </PageShell>
  );
}
