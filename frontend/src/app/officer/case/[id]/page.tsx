"use client";
import { Suspense } from "react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { BigIconButton } from "@/components/BigIconButton";
import { PageShell } from "@/components/PageShell";
import { formatTime } from "@/components/StatusTimeline";
import { api } from "@/lib/api";
import { getSession, useSession } from "@/lib/auth";
import type { CaseDetail } from "@/lib/types";

const OUTCOME: Record<string, { status: string; msg: string }> = {
  approve: { status: "approved", msg: "Approved. The payment step is released for processing." },
  reject: { status: "rejected", msg: "Rejected. The citizen will be told why." },
  request_more: { status: "needs_more_proof", msg: "Asked the citizen for more proof." },
};

function OfficerCasePageInner() {
  const { id } = useParams<{ id: string }>();
  const session = useSession();
  const [c, setC] = useState<CaseDetail | null>(null);
  const [error, setError] = useState(false);
  const [note, setNote] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<CaseDetail>("GET", `/cases/${id}`, { token: getSession()?.token }).then(setC).catch(() => setError(true));
  }, [id]);

  async function decide(action: keyof typeof OUTCOME) {
    setBusy(true);
    try {
      await api("POST", `/cases/${id}/decide`, { body: { action, note }, token: getSession()?.token });
      setC((prev) => (prev ? { ...prev, status: OUTCOME[action].status as CaseDetail["status"] } : prev));
      setDone(OUTCOME[action].msg);
    } catch {
      setDone("Could not save the decision. Nothing was changed. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const d = c?.decision;
  return (
    <PageShell title="Case review" urdu="کیس کا جائزہ" roles={["officer", "admin"]} back={{ href: "/officer", label: "Queue / قطار" }}>
      {error && <p role="alert" className="font-semibold text-red-700">Could not load this case.</p>}
      {!c && !error && <p>Loading…</p>}
      {c && (
        <>
          <section aria-labelledby="cl" className="space-y-1 rounded-2xl border-2 p-4">
            <h2 id="cl" className="text-xl font-bold">Claim · دعویٰ</h2>
            <p><strong>{c.citizen_name}</strong> · ID {c.cnic_masked}</p>
            <p>{c.programme}</p>
            <p>{c.claim_type === "short_paid" ? "Short paid" : "Missing"} · PKR {c.amount_claimed_pkr}</p>
            <p>Status: <strong>{c.status.replace(/_/g, " ")}</strong></p>
          </section>

          {d && (
            <section aria-labelledby="ai" className="space-y-2 rounded-2xl border-2 p-4">
              <h2 id="ai" className="text-xl font-bold">AI assessment · اے آئی کا اندازہ</h2>
              <p>Confidence: <strong>{Math.round(d.confidence * 100)}%</strong> · Risk: <strong>{Math.round(c.risk_score * 100)}%</strong></p>
              <p>Suggested: <strong>{d.action.replace(/_/g, " ")}</strong>{d.requires_officer_approval && " (payment needs officer approval)"}</p>
              <p>Rule version: <strong>v{d.rule_version}</strong> · model {d.model_version}</p>
              <h3 className="font-bold">Reasons</h3>
              <ul className="list-disc pl-6">{d.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              <details className="rounded-lg bg-gray-100 p-2 text-black">
                <summary className="min-h-[44px] cursor-pointer py-2 font-semibold">Full trace</summary>
                <pre className="overflow-x-auto text-xs">{JSON.stringify(d.trace, null, 2)}</pre>
              </details>
            </section>
          )}

          {c.pipeline_steps.length > 0 && (
            <section aria-labelledby="ps" className="rounded-2xl border-2 p-4">
              <h2 id="ps" className="text-xl font-bold">Pipeline steps</h2>
              <ol className="list-decimal pl-6">
                {c.pipeline_steps.map((s) => <li key={s.step}><strong>{s.step}</strong>: {s.detail}</li>)}
              </ol>
            </section>
          )}

          <section aria-labelledby="nt" className="rounded-2xl border-2 p-4">
            <h2 id="nt" className="text-xl font-bold">Case notes · نوٹس</h2>
            <ul className="mt-2 space-y-2">
              {c.notes.map((n, i) => (
                <li key={i} className="rounded-lg bg-gray-100 p-2 text-black">
                  <p>{n.text}</p>
                  <p className="text-xs opacity-70">{n.author} · {formatTime(n.created_at)}</p>
                </li>
              ))}
            </ul>
          </section>

          {session?.role === "officer" ? (
            <section aria-labelledby="dc" className="space-y-3">
              <h2 id="dc" className="text-xl font-bold">Your decision · آپ کا فیصلہ</h2>
              <label className="block font-semibold">
                Note (optional)
                <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} className="mt-1 w-full rounded-xl border-2 p-3 text-black" />
              </label>
              {done && <p role="status" className="rounded-xl bg-blue-50 p-3 font-semibold text-black">{done}</p>}
              <BigIconButton icon="✅" en="Approve" ur="منظور کریں" tone="success" disabled={busy} onClick={() => void decide("approve")} />
              <BigIconButton icon="⛔" en="Reject" ur="مسترد کریں" tone="danger" disabled={busy} onClick={() => void decide("reject")} />
              <BigIconButton icon="📎" en="Ask for more proof" ur="مزید ثبوت مانگیں" disabled={busy} onClick={() => void decide("request_more")} />
            </section>
          ) : (
            <p className="rounded-xl bg-gray-100 p-3 text-black">Only officers can decide. You are viewing as {session?.role}.</p>
          )}
        </>
      )}
    </PageShell>
  );
}

export default function OfficerCasePage() {
  return (
    <Suspense fallback={<p className="p-6 text-center">Loading… · لوڈ ہو رہا ہے…</p>}>
      <OfficerCasePageInner />
    </Suspense>
  );
}
