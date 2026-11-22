"use client";
import { Suspense, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ClaimFlow } from "@/components/ClaimFlow";
import { Icon } from "@/components/Icon";
import { PageShell } from "@/components/PageShell";
import { ReadAloud } from "@/components/ReadAloud";
import { Badge, Button, Card, Field, Notice, SectionTitle, Skeleton } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { statusLook } from "@/lib/status";
import { familyCitizenId, type CaseDetail, type CaseSummary, type ConsentRecord, type Family } from "@/lib/types";

/** Accept "1" or "fam-001". */
function normaliseId(raw: string): string {
  return /^\d+$/.test(raw) ? `fam-${raw.padStart(3, "0")}` : raw;
}

function GrantRow({ c, citizenId, onDone }: { c: ConsentRecord; citizenId: string; onDone: (r: ConsentRecord) => void }) {
  const [open, setOpen] = useState(false);
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function grant() {
    setBusy(true);
    setErr(null);
    try {
      onDone(await api<ConsentRecord>("POST", "/consent", { body: { scope: c.scope, citizen_id: citizenId, pin }, token: getSession()?.token }));
      setOpen(false);
      setPin("");
    } catch (e) {
      setErr(errorText(e, "Could not save. Check the PIN."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="rounded-2xl bg-cream-2 p-3">
      <div className="flex items-center justify-between gap-3">
        <span className="font-bold capitalize">{c.scope}</span>
        {c.granted ? <Badge tone="ok" icon="checkCircle">Yes · ہاں</Badge> : (
          <button type="button" onClick={() => setOpen((v) => !v)} className="min-h-[44px] rounded-full bg-saffron-300 px-4 text-sm font-extrabold text-on-accent">
            Ask for consent · اجازت لیں
          </button>
        )}
      </div>
      {open && !c.granted && (
        <div className="mt-3 space-y-2">
          <Field label="Their 4-digit PIN" ur="ان کا ۴ ہندسوں کا پن" hint="They must tell you their own PIN. It proves they agree.">
            <input className="input tracking-[0.5em]" inputMode="numeric" maxLength={4} value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} autoComplete="off" />
          </Field>
          {err && <Notice tone="bad">{err}</Notice>}
          <Button loading={busy} disabled={pin.length !== 4} onClick={() => void grant()} icon="lock" en="Save their consent" ur="اجازت محفوظ کریں" />
        </div>
      )}
    </li>
  );
}

function HelperFamilyInner() {
  const params = useParams<{ familyId: string }>();
  const router = useRouter();
  const familyId = normaliseId(params.familyId);
  const [family, setFamily] = useState<Family | null | undefined>(undefined);
  const [latest, setLatest] = useState<CaseDetail | null>(null);
  const [consent, setConsent] = useState<ConsentRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getSession()?.token;
    api<{ items: Family[] }>("GET", "/helper/families", { token })
      .then(async (fam) => {
        const f = fam.items.find((x) => x.family_id === familyId) ?? null;
        setFamily(f);
        if (!f) return;
        const cid = familyCitizenId(f);
        const [cases, con] = await Promise.all([
          api<{ items: CaseSummary[] }>("GET", "/cases", { token }),
          api<{ items: ConsentRecord[] }>("GET", "/consent", { token }),
        ]);
        setConsent(con.items.filter((c) => c.citizen_id === cid));
        const mine = cases.items.find((c) => c.citizen_name === f.head_name);
        if (mine) setLatest(await api<CaseDetail>("GET", `/cases/${mine.id}`, { token }));
      })
      .catch((e) => setError(errorText(e, "Could not load this person.")));
  }, [familyId]);

  function switchPerson() {
    // Clear everything on screen so the next person never sees this one's data.
    setFamily(undefined);
    setLatest(null);
    setConsent([]);
    router.push("/helper");
  }

  const cid = family ? familyCitizenId(family) : "";
  const identityOk = consent.length ? consent.some((c) => c.scope === "identity" && c.granted) : family?.consent_on_file ?? false;
  const look = latest ? statusLook(latest.status) : null;

  return (
    <PageShell title="Open case" urdu="کھلا ہوا کیس" roles={["helper"]} wide back={{ href: "/helper", label: "All families · تمام خاندان" }}>
      {error && <Notice tone="bad">{error}</Notice>}
      {family === undefined && !error && <div className="grid gap-6 lg:grid-cols-5"><Skeleton className="h-56 lg:col-span-2" /><Skeleton className="h-56 lg:col-span-3" /></div>}
      {family === null && <Notice tone="warn" title="No such person. Go back and choose again. · ایسا کوئی فرد نہیں۔" />}

      {family && (
        <div className="grid items-start gap-6 lg:grid-cols-5">
          <div className="space-y-6 lg:col-span-2 lg:sticky lg:top-28">
          <div role="status" className="rise rounded-[26px] border-4 border-saffron-500 bg-saffron-50 p-5">
            <p className="flex items-center gap-2 text-sm font-extrabold uppercase tracking-wide text-saffron-600">
              <Icon name="users" size={18} /> You are now helping · <span dir="rtl" lang="ur" className="normal-case">آپ مدد کر رہے ہیں</span>
            </p>
            <p className="text-3xl font-extrabold text-heading">{family.head_name}</p>
          </div>

          {!identityOk && (
            <Notice tone="bad" title="No consent on file. Ask this person for permission before doing anything.">
              <p dir="rtl" lang="ur">اجازت موجود نہیں۔ کچھ کرنے سے پہلے ان سے اجازت لیں۔</p>
            </Notice>
          )}

          <Card className="rise space-y-3">
            <SectionTitle icon="clock" en="Claim status" ur="دعوے کی حالت" />
            {!latest && <p className="text-ink-soft">No claim yet for this person.<span dir="rtl" lang="ur" className="ur-line">ابھی کوئی دعویٰ نہیں۔</span></p>}
            {latest && look && (
              <>
                <div className="flex flex-wrap items-center gap-3">
                  <Badge tone={look.tone}>{look.en} · <span dir="rtl" lang="ur">{look.ur}</span></Badge>
                  <span className="font-extrabold">PKR {latest.amount_claimed_pkr.toLocaleString("en-US")}</span>
                </div>
                {latest.explanation_en && <p className="text-lg">{latest.explanation_en}</p>}
                {latest.explanation_ur && <p dir="rtl" lang="ur" className="text-xl">{latest.explanation_ur}</p>}
                <ReadAloud ur={latest.explanation_ur ?? undefined} en={latest.explanation_en ?? undefined} />
              </>
            )}
          </Card>

          <Card className="rise rise-1 space-y-3">
            <SectionTitle icon="lock" en="Consent" ur="رضامندی" />
            {consent.length === 0 && <p className="text-ink-soft">Consent details are not available.</p>}
            <ul className="space-y-2">{consent.map((c) => <GrantRow key={c.id} c={c} citizenId={cid} onDone={(r) => setConsent((p) => p.map((x) => (x.id === r.id ? r : x)))} />)}</ul>
          </Card>

          <Button variant="danger" full size="lg" icon="refresh" en="Switch person" ur="دوسرا فرد" onClick={switchPerson} />
          </div>

          <div className="rise rise-2 lg:col-span-3">
            <h2 className="mb-4 flex flex-wrap items-baseline gap-x-3 text-2xl font-extrabold text-heading"><span>New claim for {family.head_name.split(" ")[0]}</span><span dir="rtl" lang="ur" className="text-saffron-600">نیا دعویٰ</span></h2>
            {identityOk ? (
              <ClaimFlow personId={cid} onBehalfOf={cid} statusHref={`/helper/${familyId}`} />
            ) : (
              <Notice tone="warn">Get their consent first, then you can file a claim.<span dir="rtl" lang="ur" className="ur-line">پہلے اجازت لیں، پھر دعویٰ کریں۔</span></Notice>
            )}
          </div>
        </div>
      )}
    </PageShell>
  );
}

export default function HelperFamilyPage() {
  return (
    <Suspense fallback={<div className="p-6"><Skeleton className="h-40" /></div>}>
      <HelperFamilyInner />
    </Suspense>
  );
}
