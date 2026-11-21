"use client";
import { Suspense, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Icon } from "@/components/Icon";
import { PageShell } from "@/components/PageShell";
import { ReadAloud } from "@/components/ReadAloud";
import { formatTime } from "@/components/StatusTimeline";
import { Badge, Button, Card, Field, Meter, Notice, SectionTitle, Skeleton, pretty } from "@/components/ui";
import { api, apiImage, errorText } from "@/lib/api";
import { getSession, useSession } from "@/lib/auth";
import { statusLook } from "@/lib/status";
import type { CaseDetail } from "@/lib/types";

/** The ID photo the citizen sent (server-resized copy; same auth as the case). Shown only when the claim has one. */
function IdPhoto({ path }: { path: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    void apiImage(path, getSession()?.token).then((u) => {
      url = u;
      setSrc(u);
    });
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [path]);
  if (!src) return null;
  return (
    <Card className="rise space-y-3">
      <SectionTitle icon="camera" en="ID card photo" ur="شناختی کارڈ کی تصویر" />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt="ID card sent by the citizen (simulated)" className="w-full rounded-2xl border border-line" />
    </Card>
  );
}

const OUTCOME: Record<string, { status: CaseDetail["status"]; msg: string }> = {
  approve: { status: "approved", msg: "Approved. If there is a shortfall, the payment was released once (retries cannot pay twice)." },
  reject: { status: "rejected", msg: "Rejected. The citizen will be told why." },
  ask_more: { status: "needs_more_proof", msg: "Asked the citizen for more proof." },
};

function CaseInner() {
  const { id } = useParams<{ id: string }>();
  const session = useSession();
  const [c, setC] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [done, setDone] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    const token = getSession()?.token;
    api<CaseDetail>("GET", `/cases/${id}`, { token }).then(setC).catch((e) => setError(errorText(e, "Could not load this case.")));
  }, [id]);

  async function decide(action: keyof typeof OUTCOME) {
    if (!reason.trim()) {
      setDone({ tone: "bad", text: "Please write a short reason. It is saved in the audit log." });
      return;
    }
    setBusy(action);
    setDone(null);
    try {
      const updated = await api<CaseDetail>("POST", `/cases/${id}/decide`, { body: { action, reason: reason.trim() }, token: getSession()?.token });
      setC((prev) => (updated?.id ? updated : prev ? { ...prev, status: OUTCOME[action].status } : prev));
      setDone({ tone: "ok", text: OUTCOME[action].msg });
    } catch (e) {
      setDone({ tone: "bad", text: `${errorText(e, "Could not save the decision.")} Nothing was changed.` });
    } finally {
      setBusy(null);
    }
  }

  const d = c?.decision as (CaseDetail["decision"] & { reasons?: string[] }) | null | undefined;
  const look = c ? statusLook(c.status) : null;
  const isOfficer = session?.role === "officer";
  const closed = c ? ["approved", "rejected", "closed"].includes(c.status) : false;

  return (
    <PageShell title="Case review" urdu="کیس کا جائزہ" roles={["officer", "admin"]} back={{ href: "/officer", label: "Queue · قطار" }} wide>
      {error && <Notice tone="bad">{error}</Notice>}
      {!c && !error && <div className="grid gap-4 lg:grid-cols-3"><Skeleton className="h-56 lg:col-span-2" /><Skeleton className="h-56" /></div>}
      {c && look && (
        <div className="grid items-start gap-5 lg:grid-cols-3">
          <div className="space-y-5 lg:col-span-2">
            <Card className="rise space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-2xl font-extrabold text-heading">{c.citizen_name}</p>
                  <p className="text-sm text-ink-soft">ID {c.cnic_masked} · {c.programme} · {c.id}</p>
                </div>
                <Badge tone={look.tone}>{look.en}</Badge>
              </div>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-2xl bg-cream-2 p-3"><p className="text-xs font-bold text-ink-soft">CLAIM</p><p className="font-extrabold">{c.claim_type === "short_paid" ? "Short paid" : pretty(c.claim_type)}</p></div>
                <div className="rounded-2xl bg-cream-2 p-3"><p className="text-xs font-bold text-ink-soft">AMOUNT</p><p className="font-extrabold">PKR {c.amount_claimed_pkr.toLocaleString("en-US")}</p></div>
                <div className="rounded-2xl bg-cream-2 p-3"><p className="text-xs font-bold text-ink-soft">RISK</p><p className="font-extrabold">{Math.round(c.risk_score * 100)}%</p></div>
              </div>
            </Card>

            {d && (
              <Card className="rise rise-1 space-y-4">
                <SectionTitle icon="sparkle" en="AI assessment" ur="اے آئی کا اندازہ" />
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <div className="mb-1 flex justify-between text-sm font-bold"><span>Confidence</span><span>{Math.round(d.confidence * 100)}%</span></div>
                    <Meter value={d.confidence} tone={d.confidence >= 0.9 ? "ok" : d.confidence >= 0.6 ? "warn" : "bad"} label="Confidence" />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={d.action === "auto_handle" ? "ok" : d.action === "ask_more" ? "warn" : "bad"}>suggests: {pretty(d.action)}</Badge>
                    <Badge tone="neutral">rule v{d.rule_version}</Badge>
                    <Badge tone="neutral">{d.model_version}</Badge>
                  </div>
                </div>
                {d.requires_officer_approval && <Notice tone="warn">Any payment on this case needs your approval.</Notice>}
                {d.reasons && d.reasons.length > 0 && (
                  <div>
                    <p className="mb-1 font-extrabold">Reasons</p>
                    <ul className="list-disc space-y-1 ps-6">{d.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                  </div>
                )}
                <details className="rounded-2xl bg-cream-2 p-3">
                  <summary className="min-h-[44px] cursor-pointer py-2 font-bold">Full trace</summary>
                  <pre className="overflow-x-auto text-xs">{JSON.stringify(d.trace, null, 2)}</pre>
                </details>
              </Card>
            )}

            {c.image_url && <IdPhoto path={c.image_url} />}

            {c.pipeline_steps.length > 0 && (
              <Card className="rise space-y-3">
                <SectionTitle icon="list" en="What the agent did" ur="ایجنٹ نے کیا کیا" />
                <ol className="space-y-2">
                  {c.pipeline_steps.map((s, i) => (
                    <li key={`${s.step}-${i}`} className="flex items-start gap-3 rounded-xl bg-cream-2 p-3">
                      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-teal-700 text-white"><Icon name="check" size={16} /></span>
                      <span><strong>{pretty(s.step)}</strong><span className="block text-sm text-ink-soft">{s.detail}</span></span>
                    </li>
                  ))}
                </ol>
              </Card>
            )}
          </div>

          <aside className="space-y-5 lg:sticky lg:top-32">
            {(c.explanation_en || c.explanation_ur) && (
              <Card className="space-y-2">
                <SectionTitle icon="volume" en="What the citizen sees" ur="شہری کو کیا نظر آتا ہے" />
                <p>{c.explanation_en}</p>
                <p dir="rtl" lang="ur" className="text-lg">{c.explanation_ur}</p>
                <ReadAloud ur={c.explanation_ur ?? undefined} en={c.explanation_en ?? undefined} />
              </Card>
            )}

            <Card className="space-y-3">
              <SectionTitle icon="gavel" en="Your decision" ur="آپ کا فیصلہ" />
              {isOfficer ? (
                <>
                  <Field label="Reason (required, saved in the audit log)" ur="وجہ (ضروری)">
                    <textarea className="input" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. ID matches ledger; payment short by PKR 3000" />
                  </Field>
                  {done && <Notice tone={done.tone}>{done.text}</Notice>}
                  <Button full variant="success" loading={busy === "approve"} disabled={!!busy || closed} icon="checkCircle" en="Approve" ur="منظور کریں" onClick={() => void decide("approve")} />
                  <Button full variant="danger" loading={busy === "reject"} disabled={!!busy || closed} icon="xCircle" en="Reject" ur="مسترد کریں" onClick={() => void decide("reject")} />
                  <Button full variant="ghost" loading={busy === "ask_more"} disabled={!!busy || closed} icon="file" en="Ask for more proof" ur="مزید ثبوت مانگیں" onClick={() => void decide("ask_more")} />
                  {closed && <p className="text-sm text-ink-soft">This case is already decided.</p>}
                </>
              ) : (
                <Notice tone="info">Only officers can decide. You are viewing as {session?.role}.</Notice>
              )}
            </Card>

            <Card className="space-y-2">
              <SectionTitle icon="scroll" en="Notes" ur="نوٹس" />
              {c.notes.length === 0 && <p className="text-sm text-ink-soft">No notes yet.</p>}
              <ul className="space-y-2">
                {c.notes.map((n, i) => (
                  <li key={i} className="rounded-xl bg-cream-2 p-3">
                    <p>{n.text}</p>
                    <p className="text-xs text-ink-soft">{n.author} · {formatTime(n.created_at)}</p>
                  </li>
                ))}
              </ul>
            </Card>
          </aside>
        </div>
      )}
    </PageShell>
  );
}

export default function OfficerCasePage() {
  return (
    <Suspense fallback={<div className="p-6"><Skeleton className="h-40" /></div>}>
      <CaseInner />
    </Suspense>
  );
}
