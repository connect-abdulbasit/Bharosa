"use client";
import { Suspense } from "react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { BigIconButton } from "@/components/BigIconButton";
import { MicButton } from "@/components/MicButton";
import { PageShell } from "@/components/PageShell";
import { ReadAloud } from "@/components/ReadAloud";
import { api } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { loadProgress, saveProgress } from "@/lib/offline";
import type { CaseDetail, ConsentRecord, Family } from "@/lib/types";

type Draft = { transcript: string; note: string };
const PAGE = "helper-family";

/** Accept "1" or "fam-001". */
function normaliseId(raw: string): string {
  return /^\d+$/.test(raw) ? `fam-${raw.padStart(3, "0")}` : raw;
}

function HelperFamilyPageInner() {
  const params = useParams<{ familyId: string }>();
  const router = useRouter();
  const familyId = normaliseId(params.familyId);
  const [family, setFamily] = useState<Family | null | undefined>(undefined);
  const [claim, setClaim] = useState<CaseDetail | null>(null);
  const [consent, setConsent] = useState<ConsentRecord[]>([]);
  const [draft, setDraft] = useState<Draft>({ transcript: "", note: "" });
  const [error, setError] = useState(false);
  const ready = useRef(false);

  useEffect(() => {
    const token = getSession()?.token;
    ready.current = false;
    Promise.all([
      api<{ items: Family[] }>("GET", "/helper/families", { token }),
      api<{ items: { id: string }[] }>("GET", "/cases", { token }).then((r) =>
        r.items[0] ? api<CaseDetail>("GET", `/cases/${r.items[0].id}`, { token }) : null,
      ),
      api<{ items: ConsentRecord[] }>("GET", "/consent", { token }),
      loadProgress<Draft>(PAGE, familyId),
    ])
      .then(([fam, c, con, saved]) => {
        setFamily(fam.items.find((f) => f.family_id === familyId) ?? null);
        setClaim(c);  // TODO: filter by family once the backend links cases to families
        setConsent(con.items);
        if (saved) setDraft(saved.data);
        ready.current = true;
      })
      .catch(() => setError(true));
  }, [familyId]);

  function update(next: Draft) {
    setDraft(next);
    if (ready.current) void saveProgress(PAGE, familyId, next);
  }

  function switchPerson() {
    // Clear everything on screen so the next person never sees this one's data.
    setFamily(undefined);
    setClaim(null);
    setConsent([]);
    setDraft({ transcript: "", note: "" });
    router.push("/helper");
  }

  const consentOk = family?.consent_on_file ?? false;

  return (
    <PageShell title="Open case" urdu="کھلا ہوا کیس" roles={["helper"]} back={{ href: "/helper", label: "All families / تمام خاندان" }}>
      {error && <p role="alert" className="font-semibold text-red-700">Could not load this case. · کیس لوڈ نہیں ہوا۔</p>}
      {family === undefined && !error && <p>Loading… · لوڈ ہو رہا ہے…</p>}
      {family === null && (
        <p role="alert" className="rounded-xl border-2 border-amber-600 bg-amber-50 p-4 text-black">
          No such person. Go back and choose again. · ایسا کوئی فرد نہیں۔ واپس جا کر دوبارہ چنیں۔
        </p>
      )}
      {family && (
        <>
          <div role="status" className="rounded-2xl border-4 border-teal-900 bg-teal-100 p-4 text-black">
            <p className="text-sm font-semibold uppercase">You are now helping · آپ مدد کر رہے ہیں</p>
            <p className="text-3xl font-extrabold">{family.head_name}</p>
          </div>

          {!consentOk && (
            <p role="alert" className="rounded-xl border-2 border-red-700 bg-red-50 p-3 font-semibold text-red-900">
              No consent on file. Ask this person for permission before doing anything. · اجازت موجود نہیں۔ کچھ کرنے سے پہلے ان سے اجازت لیں۔
            </p>
          )}

          <section aria-labelledby="st" className="space-y-2 rounded-2xl border-2 p-4">
            <h2 id="st" className="text-xl font-bold">Claim status · دعوے کی حالت</h2>
            {claim && (
              <>
                <p className="text-lg">
                  <strong>{claim.status.replace(/_/g, " ")}</strong> · PKR {claim.amount_claimed_pkr}
                </p>
                <p>{claim.explanation_en}</p>
                <p dir="rtl" lang="ur">{claim.explanation_ur}</p>
                <ReadAloud ur={claim.explanation_ur ?? undefined} en={claim.explanation_en ?? undefined} />
              </>
            )}
          </section>

          <section aria-labelledby="co" className="space-y-2 rounded-2xl border-2 p-4">
            <h2 id="co" className="text-xl font-bold">Consent · رضامندی</h2>
            <ul className="space-y-1">
              {consent.map((c) => (
                <li key={c.id} className="flex items-center justify-between">
                  <span className="capitalize">{c.scope}</span>
                  <span className="font-semibold">{c.granted ? "✅ Yes · ہاں" : "⛔ No · نہیں"}</span>
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="dr" className="space-y-3">
            <h2 id="dr" className="text-xl font-bold">Their words · ان کی بات</h2>
            {draft.transcript ? (
              <div className="space-y-2 rounded-xl bg-green-50 p-3 text-black">
                <p dir="auto" className="text-xl">“{draft.transcript}”</p>
                <button type="button" onClick={() => update({ ...draft, transcript: "" })} className="min-h-[48px] rounded-xl border-2 px-4 font-semibold">
                  Again · دوبارہ
                </button>
              </div>
            ) : (
              <MicButton onConfirm={(t) => update({ ...draft, transcript: t })} />
            )}
            <label className="block text-lg font-semibold">
              Your note · آپ کا نوٹ
              <textarea value={draft.note} onChange={(e) => update({ ...draft, note: e.target.value })} rows={3} className="mt-1 w-full rounded-xl border-2 p-3 text-lg text-black" />
            </label>
            <p className="text-sm opacity-80">Saved on this phone for this person only. · صرف اسی فرد کے لیے اس فون پر محفوظ۔</p>
          </section>

          <BigIconButton icon="🔄" en="Switch person" ur="دوسرا فرد" onClick={switchPerson} tone="danger" />
        </>
      )}
    </PageShell>
  );
}

export default function HelperFamilyPage() {
  return (
    <Suspense fallback={<p className="p-6 text-center">Loading… · لوڈ ہو رہا ہے…</p>}>
      <HelperFamilyPageInner />
    </Suspense>
  );
}
