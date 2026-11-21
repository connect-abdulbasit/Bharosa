"use client";
import { useState } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { PageShell } from "@/components/PageShell";
import { ReadAloud } from "@/components/ReadAloud";
import { Badge, Button, Card, Field, Meter, Notice } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { getSession } from "@/lib/auth";
import type { MessageCheck } from "@/lib/types";

const LOOK: Record<string, { icon: IconName; en: string; ur: string; box: string; chip: string; meter: "ok" | "bad" | "warn" }> = {
  scam: { icon: "xCircle", en: "Looks like a SCAM", ur: "یہ جعلی لگتا ہے", box: "bg-bad-soft text-bad-ink border-bad-700", chip: "bg-bad-700 text-white", meter: "bad" },
  genuine: { icon: "checkCircle", en: "Looks genuine", ur: "یہ اصلی لگتا ہے", box: "bg-ok-soft text-ok-ink border-ok-700", chip: "bg-ok-700 text-white", meter: "ok" },
  unsure: { icon: "question", en: "We are not sure", ur: "ہمیں یقین نہیں", box: "bg-warn-soft text-warn-ink border-warn-700", chip: "bg-saffron-500 text-on-accent", meter: "warn" },
};

const EXAMPLES = [
  { sender: "9090", text: "Sahara Relief: your May instalment of PKR 6000 was paid on 12-05. Ref SR-4421. Reply HELP for help." },
  { sender: "0300-5550199", text: "URGENT! Your Sahara relief is blocked. Send your CNIC and PIN to this number now or lose your money." },
];


const TIPS: { icon: IconName; en: string; ur: string }[] = [
  { icon: "lock", en: "It asks for your CNIC, PIN or password.", ur: "یہ آپ کا شناختی نمبر، پن یا پاس ورڈ مانگتا ہے۔" },
  { icon: "clock", en: "It rushes you: \"act now or lose your money\".", ur: "جلدی کرواتا ہے: \"ابھی کریں ورنہ رقم ختم\"۔" },
  { icon: "phone", en: "It comes from a normal mobile number, not 9090.", ur: "عام موبائل نمبر سے آتا ہے، 9090 سے نہیں۔" },
  { icon: "send", en: "It asks you to send money to receive money.", ur: "رقم لینے کے لیے رقم بھیجنے کو کہتا ہے۔" },
];

export default function CheckPage() {
  const [text, setText] = useState("");
  const [sender, setSender] = useState("");
  const [area, setArea] = useState("");
  const [result, setResult] = useState<MessageCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function check() {
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, string> = { text: text.trim(), sender: sender.trim() };
      if (area.trim()) body.area = area.trim();
      setResult(await api<MessageCheck>("POST", "/messages/check", { body, token: getSession()?.token }));
    } catch (e) {
      setResult(null);
      setError(errorText(e, "We could not check right now. Please try again, or ask a helper."));
    } finally {
      setBusy(false);
    }
  }

  const look = result ? LOOK[result.label] ?? LOOK.unsure : null;
  const lowConfidence = result ? result.confidence < 0.6 : false;

  return (
    <PageShell title="Check a message" urdu="پیغام چیک کریں" roles={["citizen", "helper"]} wide back={{ href: "/citizen", label: "My Bharosa · میرا بھروسہ" }}>
      <div className="grid items-start gap-6 lg:grid-cols-2">
      <Card className="rise space-y-4">
        <Field label="Who sent it? (number or name)" ur="بھیجنے والا">
          <input className="input" value={sender} onChange={(e) => setSender(e.target.value)} placeholder="9090" inputMode="text" autoComplete="off" />
        </Field>
        <Field label="What does the message say?" ur="پیغام میں کیا لکھا ہے؟">
          <textarea className="input" value={text} onChange={(e) => setText(e.target.value)} rows={5} dir="auto" placeholder="Paste or type the message here" />
        </Field>
        <Field label="Your area (optional, helps warn others)" ur="آپ کا علاقہ (اختیاری)">
          <input className="input" value={area} onChange={(e) => setArea(e.target.value)} autoComplete="off" />
        </Field>
        <Button full size="lg" loading={busy} disabled={!text.trim() || !sender.trim()} onClick={() => void check()} icon="shield" en="Check it" ur="چیک کریں" />
        {error && <Notice tone="bad">{error}</Notice>}
      </Card>

      {!result && (
        <div className="rise rise-1 space-y-6">
          <Card className="space-y-4">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-saffron-50 text-saffron-600"><Icon name="alert" size={24} /></span>
              <h2 className="text-xl font-extrabold leading-tight text-heading">
                How to spot a scam
                <span dir="rtl" lang="ur" className="block text-left text-lg text-saffron-600">جعلی پیغام کی پہچان</span>
              </h2>
            </div>
            <ul className="space-y-3">
              {TIPS.map((t) => (
                <li key={t.en} className="flex gap-3 rounded-2xl bg-cream-2 p-3">
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-50 text-brand"><Icon name={t.icon} size={18} /></span>
                  <span>
                    <span className="block font-bold">{t.en}</span>
                    <span dir="rtl" lang="ur" className="block text-ink-soft">{t.ur}</span>
                  </span>
                </li>
              ))}
            </ul>
            <p className="text-sm text-ink-soft">The only official short code is <strong>9090</strong>. · <span dir="rtl" lang="ur">واحد سرکاری کوڈ <strong>9090</strong> ہے۔</span></p>
          </Card>

          <Card className="space-y-3">
            <h2 className="flex flex-wrap items-baseline gap-x-3 text-xl font-extrabold text-heading"><span>Try an example</span><span dir="rtl" lang="ur" className="text-saffron-600">مثال آزمائیں</span></h2>
            <div className="grid gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex.sender}
                  type="button"
                  onClick={() => {
                    setSender(ex.sender);
                    setText(ex.text);
                    setResult(null);
                  }}
                  className="rounded-2xl border border-line bg-surface p-3 text-left text-sm transition hover:border-teal-600 hover:bg-teal-50"
                >
                  <span className="font-extrabold">{ex.sender}</span>
                  <span className="block text-ink-soft">{ex.text}</span>
                </button>
              ))}
            </div>
          </Card>
        </div>
      )}

      {result && look && (
        <section aria-live="polite" className={`rise space-y-4 rounded-[26px] border-2 p-5 ${look.box}`}>
          <div className="flex items-center gap-4">
            <span className={`flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl ${look.chip}`}>
              <Icon name={look.icon} size={40} />
            </span>
            <div className="leading-tight">
              <p className="text-3xl font-extrabold">{look.en}</p>
              <p dir="rtl" lang="ur" className="text-3xl font-extrabold">{look.ur}</p>
            </div>
          </div>

          <div className="rounded-2xl bg-surface/70 p-4 text-ink">
            <div className="mb-1 flex items-center justify-between text-sm font-bold">
              <span>How sure are we? · <span dir="rtl" lang="ur">ہمیں کتنا یقین ہے؟</span></span>
              <span>{Math.round(result.confidence * 100)}%</span>
            </div>
            <Meter value={result.confidence} tone={look.meter} label="Confidence" />
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge tone={result.official_sender ? "ok" : "warn"} icon={result.official_sender ? "checkCircle" : "alert"}>
                {result.official_sender ? "Official sender" : "Not an official sender"}
              </Badge>
            </div>
          </div>

          {lowConfidence && (
            <Notice tone="warn" title="We are not certain. Please do not act on it.">
              <p>Ask a helper or an officer first.</p>
              <p dir="rtl" lang="ur">یقین نہیں، اس پر عمل نہ کریں، مددگار سے پوچھیں۔</p>
            </Notice>
          )}

          <div className="space-y-1 rounded-2xl bg-surface/70 p-4 text-ink">
            <p className="text-lg font-bold">{result.explanation_en}</p>
            <p dir="rtl" lang="ur" className="text-xl font-bold">{result.explanation_ur}</p>
          </div>

          {result.reasons.length > 0 && (
            <div className="rounded-2xl bg-surface/70 p-4 text-ink">
              <p className="mb-1 font-extrabold">Why we think so · <span dir="rtl" lang="ur">ہماری رائے کی وجہ</span></p>
              <ul className="list-disc space-y-1 ps-6">{result.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
            </div>
          )}

          <ReadAloud ur={`${look.ur}۔ ${result.explanation_ur}`} en={`${look.en}. ${result.explanation_en}`} />
        </section>
      )}
      </div>
    </PageShell>
  );
}
