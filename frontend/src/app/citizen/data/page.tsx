"use client";
import { useCallback, useEffect, useState } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { PageShell } from "@/components/PageShell";
import { formatTime } from "@/components/StatusTimeline";
import { Badge, Button, Card, EmptyState, Field, Notice, SectionTitle, Skeleton } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { getSession } from "@/lib/auth";
import type { ConsentRecord } from "@/lib/types";

const SCOPE: Record<string, { icon: IconName; en: string; ur: string }> = {
  identity: { icon: "user", en: "My identity", ur: "میری شناخت" },
  payments: { icon: "send", en: "My payments", ur: "میری ادائیگیاں" },
  complaints: { icon: "file", en: "Complaints for me", ur: "میری شکایات" },
  notifications: { icon: "phone", en: "Messages to me", ur: "مجھے پیغامات" },
};

function ConsentCard({ c, onChange }: { c: ConsentRecord; onChange: (r: ConsentRecord) => void }) {
  const look = SCOPE[c.scope] ?? { icon: "lock" as IconName, en: c.scope, ur: c.scope };
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function run(path: string, body?: unknown) {
    setBusy(true);
    setErr(null);
    try {
      onChange(await api<ConsentRecord>("POST", path, { body, token: getSession()?.token }));
      setConfirming(false);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className={`rise space-y-3 ${c.granted ? "" : "bg-cream-2"}`}>
      <div className="flex items-start gap-4">
        <span className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl ${c.granted ? "bg-teal-50 text-brand" : "bg-surface text-ink-soft"}`}>
          <Icon name={look.icon} size={30} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xl font-extrabold leading-tight text-heading">{look.en}</p>
          <p dir="rtl" lang="ur" className="text-xl font-bold text-saffron-600">{look.ur}</p>
        </div>
        <Badge tone={c.granted ? "ok" : "neutral"} icon={c.granted ? "checkCircle" : "lock"}>
          {c.granted ? "Shared" : "Not shared"}
        </Badge>
      </div>

      <p className="text-ink-soft">{c.purpose}</p>
      {c.shared_with.length > 0 && (
        <p className="text-sm">
          <span className="font-bold">Who can see it · </span>
          <span dir="rtl" lang="ur" className="font-bold">کون دیکھ سکتا ہے: </span>
          {c.shared_with.join(", ")}
        </p>
      )}
      {c.granted && c.granted_at && <p className="text-xs text-ink-soft">Shared since {formatTime(c.granted_at)}</p>}
      {!c.granted && c.withdrawn_at && <p className="text-xs text-ink-soft">Taken back {formatTime(c.withdrawn_at)}</p>}

      {err && <Notice tone="bad">{err}</Notice>}

      {c.granted ? (
        confirming ? (
          <div className="space-y-2 rounded-2xl bg-bad-soft p-4">
            <p className="font-extrabold text-bad-ink">Take this back? We will not look at it again, and some steps may need a person instead.</p>
            <p dir="rtl" lang="ur" className="font-bold text-bad-ink">کیا واپس لینا ہے؟ ہم دوبارہ نہیں دیکھیں گے، کچھ مراحل انسان کریں گے۔</p>
            <div className="grid grid-cols-2 gap-3">
              <Button variant="danger" loading={busy} icon="lock" en="Yes, take back" ur="ہاں، واپس" onClick={() => void run(`/consent/${c.id}/withdraw`, { reason: "Withdrawn by user" })} />
              <Button variant="ghost" disabled={busy} en="Keep sharing" ur="جاری رکھیں" onClick={() => setConfirming(false)} />
            </div>
          </div>
        ) : (
          <Button variant="ghost" full icon="lock" en="Take it back" ur="واپس لیں" onClick={() => setConfirming(true)} />
        )
      ) : (
        <Button full loading={busy} icon="checkCircle" en="Share again" ur="دوبارہ دیں" onClick={() => void run("/consent", { scope: c.scope })} />
      )}
    </Card>
  );
}

function CorrectData({ consentId }: { consentId: string | undefined }) {
  const [field, setField] = useState<"name" | "phone">("name");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);

  async function save() {
    if (!consentId) return;
    setBusy(true);
    setMsg(null);
    try {
      await api("POST", `/consent/${consentId}/correct`, { body: { field, new_value: value.trim() }, token: getSession()?.token });
      setMsg({ tone: "ok", text: "Saved. The change is written to the audit log. · محفوظ ہو گیا۔" });
      setValue("");
    } catch (e) {
      setMsg({ tone: "bad", text: errorText(e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="space-y-4">
      <SectionTitle icon="pencil" en="Something wrong? Correct it" ur="کچھ غلط ہے؟ درست کریں" />
      <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="What to correct">
        {(["name", "phone"] as const).map((f) => (
          <button
            key={f}
            role="radio"
            aria-checked={field === f}
            onClick={() => setField(f)}
            className={`min-h-[52px] rounded-2xl border-2 font-extrabold ${field === f ? "border-teal-700 bg-teal-700 text-white" : "border-line bg-surface"}`}
          >
            {f === "name" ? <>My name · <span dir="rtl" lang="ur">نام</span></> : <>My phone · <span dir="rtl" lang="ur">فون</span></>}
          </button>
        ))}
      </div>
      <Field label="The correct value" ur="درست معلومات">
        <input className="input" value={value} onChange={(e) => setValue(e.target.value)} dir="auto" />
      </Field>
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <Button full loading={busy} disabled={!value.trim() || !consentId} onClick={() => void save()} icon="check" en="Save correction" ur="درستی محفوظ کریں" />
    </Card>
  );
}

export default function DataPage() {
  const [items, setItems] = useState<ConsentRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<{ items: ConsentRecord[] }>("GET", "/consent", { token: getSession()?.token })
      .then((r) => setItems(r.items))
      .catch((e) => setError(errorText(e, "Could not load your data choices.")));
  }, []);
  useEffect(load, [load]);

  const replace = (r: ConsentRecord) => setItems((prev) => prev?.map((x) => (x.id === r.id ? r : x)) ?? prev);

  return (
    <PageShell title="Control my data" urdu="میرا ڈیٹا میرے قابو میں" roles={["citizen", "helper"]} wide back={{ href: "/citizen", label: "My Bharosa · میرا بھروسہ" }}>
      <Notice tone="info" title="You decide.">
        <p>Nothing is looked up about you unless you allow it. You can take it back at any time.</p>
        <p dir="rtl" lang="ur">آپ کی اجازت کے بغیر آپ کے بارے میں کچھ نہیں دیکھا جاتا۔ جب چاہیں اجازت واپس لے سکتے ہیں۔</p>
      </Notice>
      {error && <Notice tone="bad">{error}</Notice>}
      {!items && !error && <div className="grid gap-5 md:grid-cols-2"><Skeleton className="h-44" /><Skeleton className="h-44" /></div>}
      {items && items.length === 0 && <EmptyState icon="lock" en="No data choices yet." ur="ابھی کوئی انتخاب نہیں۔" />}
      <div className="grid items-start gap-5 md:grid-cols-2">
        {items?.map((c) => <ConsentCard key={c.id} c={c} onChange={replace} />)}
      </div>
      {items && items.length > 0 && <div className="max-w-2xl"><CorrectData consentId={items[0]?.id} /></div>}
    </PageShell>
  );
}
