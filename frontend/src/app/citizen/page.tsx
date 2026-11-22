"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { BigIconButton } from "@/components/BigIconButton";
import { Icon } from "@/components/Icon";
import { PageShell } from "@/components/PageShell";
import { ReadAloud } from "@/components/ReadAloud";
import { Badge, Button, Card, LinkButton, Notice, SectionTitle, Skeleton } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { getSession, useSession } from "@/lib/auth";
import { submitClaim } from "@/lib/claims";
import { statusLook } from "@/lib/status";
import type { CaseSummary, ClaimResponse, InAppMessage } from "@/lib/types";

function PaymentCheck() {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<ClaimResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function ask() {
    setBusy(true);
    setErr(null);
    try {
      setRes(await submitClaim({ intent: "payment_check" }, getSession()?.token));
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="rise rise-3 border-saffron-300 bg-saffron-50">
      <SectionTitle icon="send" en="Did my payment arrive?" ur="کیا میری رقم آ گئی؟" />
      <p className="mb-3 text-sm text-ink-soft">We look at the payment record for this month and tell you plainly. Nothing is claimed.</p>
      {!res && <Button variant="accent" full loading={busy} onClick={() => void ask()} icon="search" en="Check this month" ur="اس مہینے کی رقم دیکھیں" />}
      {err && <div className="mt-3"><Notice tone="bad">{err}</Notice></div>}
      {res && (
        <div className="space-y-3" aria-live="polite">
          <p className="text-xl font-extrabold text-heading">{res.explanation_en}</p>
          <p dir="rtl" lang="ur" className="text-xl font-bold">{res.explanation_ur}</p>
          <ReadAloud ur={res.explanation_ur} en={res.explanation_en} />
          <Button variant="ghost" icon="refresh" en="Ask again" ur="دوبارہ پوچھیں" onClick={() => setRes(null)} />
        </div>
      )}
    </Card>
  );
}

/** In-app messages from the notifications service (Urdu + English), created when a claim changes status. Empty is fine: the card says so. */
function MyMessages() {
  const [items, setItems] = useState<InAppMessage[] | null>(null);
  useEffect(() => {
    api<{ items: InAppMessage[] }>("GET", "/me/notifications", { token: getSession()?.token })
      .then((r) => setItems(r.items ?? []))
      .catch(() => setItems([]));
  }, []);
  return (
    <section aria-labelledby="msgs" className="rise rise-2" data-testid="my-messages">
      <SectionTitle icon="bell" en="My messages" ur="میرے پیغامات" />
      {items === null && <Skeleton className="h-20" />}
      {items && items.length === 0 && (
        <Card className="text-center text-ink-soft">
          <p className="font-bold">No messages yet.<span dir="rtl" lang="ur" className="ur-line">ابھی کوئی پیغام نہیں۔</span></p>
        </Card>
      )}
      {items && items.slice(0, 3).map((m) => (
        <Card key={m.id} className="mb-3 space-y-2">
          <p className="text-lg font-bold text-heading">{m.text_en}</p>
          <p dir="rtl" lang="ur" className="text-lg font-bold">{m.text_ur}</p>
          <ReadAloud ur={m.text_ur ?? undefined} en={m.text_en ?? undefined} />
        </Card>
      ))}
    </section>
  );
}

/** The one thing to do next, in plain words, from the state of the latest claim. */
function NextStepCard({ latest }: { latest: CaseSummary | null | undefined }) {
  if (latest === undefined) return <Skeleton className="h-36" />;
  const st = latest?.status;
  const view =
    latest === null
      ? { tone: "bg-saffron-50 border-saffron-300", en: "Did not get your payment? Start here.", ur: "ادائیگی نہیں ملی؟ یہاں سے شروع کریں۔", btn: { href: "/citizen/claim", en: "Get help with my payment", ur: "اپنی ادائیگی کے لیے مدد لیں", icon: "mic" as const } }
      : st === "needs_more_proof"
        ? { tone: "bg-saffron-50 border-saffron-300", en: "We need a little more from you.", ur: "ہمیں آپ سے تھوڑا اور چاہیے۔", btn: { href: "/citizen/claim", en: "Send more proof", ur: "مزید ثبوت بھیجیں", icon: "mic" as const } }
        : st === "approved" || st === "closed" || st === "rejected"
          ? { tone: "bg-teal-50 border-teal-100", en: "Your claim has a result.", ur: "آپ کے دعوے کا نتیجہ آ گیا ہے۔", btn: { href: "/citizen/status", en: "See what happened", ur: "دیکھیں کیا ہوا", icon: "clock" as const } }
          : { tone: "bg-teal-50 border-teal-100", en: "A person is checking your claim. You do not need to do anything.", ur: "ایک افسر آپ کا دعویٰ دیکھ رہا ہے۔ آپ کو کچھ کرنے کی ضرورت نہیں۔", btn: { href: "/citizen/status", en: "See my claim", ur: "میرا دعویٰ دیکھیں", icon: "clock" as const } };
  return (
    <section aria-label="What to do next" className={`rise rise-1 space-y-3 rounded-[26px] border-2 p-5 ${view.tone}`}>
      <p className="text-sm font-bold uppercase tracking-wide text-ink-soft">Next step · <span dir="rtl" lang="ur">اگلا قدم</span></p>
      <p className="text-2xl font-extrabold leading-snug text-heading">{view.en}</p>
      <p dir="rtl" lang="ur" className="text-left text-2xl font-bold">{view.ur}</p>
      <LinkButton href={view.btn.href} size="lg" full variant="accent" icon={view.btn.icon} en={view.btn.en} ur={view.btn.ur} />
    </section>
  );
}

export default function CitizenHome() {
  const session = useSession();
  const [latest, setLatest] = useState<CaseSummary | null | undefined>(undefined);

  useEffect(() => {
    api<{ items: CaseSummary[] }>("GET", "/cases", { token: getSession()?.token })
      .then((r) => setLatest(r.items[0] ?? null))
      .catch(() => setLatest(null));
  }, []);

  const first = session?.name.split(" ")[0] ?? "";
  const look = latest ? statusLook(latest.status) : null;

  return (
    <PageShell title={first ? `Salaam, ${first}` : "My Bharosa"} urdu="میرا بھروسہ" roles={["citizen", "helper"]} wide>
      <div className="grid items-start gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">

          <NextStepCard latest={latest} />

          <section className="hero-gradient rise hidden sm:block relative overflow-hidden rounded-[28px] p-7 text-white sm:p-9">
            <p className="text-sm font-bold uppercase tracking-wide text-saffron-300">Your helper · آپ کا مددگار</p>
            <p className="mt-1 text-3xl font-extrabold leading-snug">What do you need today?</p>
            <p dir="rtl" lang="ur" className="text-left text-3xl font-bold">آج آپ کو کیا چاہیے؟</p>
          </section>

          <p className="text-sm font-bold uppercase tracking-wide text-ink-soft">Or choose · <span dir="rtl" lang="ur">یا چنیں</span></p>
          <div className="rise rise-1 grid gap-4 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            <BigIconButton href="/citizen/check" icon="shield" tone="primary" en="Check a message" ur="پیغام چیک کریں" hint="Is this SMS a scam?" />
            <BigIconButton href="/citizen/claim" icon="mic" tone="accent" en="Claim help" ur="مدد کا دعویٰ کریں" hint="Speak, show your ID card" />
            <BigIconButton href="/citizen/status" icon="clock" en="Where is my claim?" ur="میرا دعویٰ کہاں ہے؟" />
            <BigIconButton href="/citizen/data" icon="lock" en="Control my data" ur="میرا ڈیٹا میرے قابو میں" />
          </div>
        </div>

        <div className="space-y-6">
          <section aria-labelledby="latest" className="rise rise-2">
            <SectionTitle icon="file" en="My latest claim" ur="میرا تازہ دعویٰ" />
            {latest === undefined && <Skeleton className="h-24" />}
            {latest === null && (
              <Card className="text-center text-ink-soft">
                <p className="font-bold">No claim yet.<span dir="rtl" lang="ur" className="ur-line">ابھی کوئی دعویٰ نہیں۔</span></p>
              </Card>
            )}
            {latest && look && (
              <Link href="/citizen/status" className="card card-lift flex items-center gap-4 p-5">
                <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-teal-50 text-brand">
                  <Icon name="file" size={28} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-lg font-extrabold text-heading">PKR {latest.amount_claimed_pkr.toLocaleString("en-US")}</span>
                  <span className="block text-sm text-ink-soft">{latest.claim_type === "short_paid" ? "Short paid" : "Missing payment"}</span>
                  <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5"><Badge tone={look.tone}>{look.en}</Badge><span dir="rtl" lang="ur" className="text-sm font-bold text-ink-soft">{look.ur}</span></span>
                </span>
                <Icon name="arrow" size={22} className="text-ink-soft" />
              </Link>
            )}
          </section>

          <MyMessages />
          <PaymentCheck />
        </div>
      </div>
    </PageShell>
  );
}
