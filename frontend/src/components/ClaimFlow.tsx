"use client";
import { useEffect, useRef, useState } from "react";
import { MicButton } from "@/components/MicButton";
import { PhotoCapture } from "@/components/PhotoCapture";
import { ReadAloud } from "@/components/ReadAloud";
import { Icon, type IconName } from "@/components/Icon";
import { Button, Card, Meter, Notice, SectionTitle, Spinner } from "@/components/ui";
import { errorText } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { followClaim, submitClaim } from "@/lib/claims";
import { api } from "@/lib/api";
import { clearProgress, loadProgress, saveProgress } from "@/lib/offline";
import type { ClaimProgress, ClaimResponse, DocumentResult } from "@/lib/types";
import { LinkButton } from "@/components/ui";

type Draft = { transcript: string; photo: string | null };

const ACTION_TEXT: Record<string, { icon: IconName; tone: string; en: string; ur: string }> = {
  auto_handle: { icon: "checkCircle", tone: "bg-ok-soft text-ok-ink", en: "Your claim is moving forward. An officer must still approve any payment.", ur: "آپ کا دعویٰ آگے بڑھ رہا ہے۔ ادائیگی کی منظوری افسر دے گا۔" },
  ask_more: { icon: "file", tone: "bg-warn-soft text-warn-ink", en: "We need a little more proof.", ur: "ہمیں تھوڑا اور ثبوت چاہیے۔" },
  send_to_human: { icon: "user", tone: "bg-teal-100 text-heading", en: "A person (officer) will check your claim.", ur: "ایک افسر آپ کا دعویٰ خود دیکھے گا۔" },
};

const STEP_LABEL: Record<string, { en: string; ur: string }> = {
  extract_claim: { en: "Understanding what you said", ur: "آپ کی بات سمجھ رہے ہیں" },
  read_document: { en: "Reading your ID card", ur: "شناختی کارڈ پڑھ رہے ہیں" },
  identity_lookup: { en: "Checking your identity", ur: "شناخت کی جانچ" },
  ledger_lookup: { en: "Checking payment record", ur: "ادائیگی کا ریکارڈ دیکھ رہے ہیں" },
  match_person: { en: "Matching your name", ur: "نام ملا رہے ہیں" },
  decide: { en: "Deciding the safest next step", ur: "محفوظ ترین اگلا قدم طے کر رہے ہیں" },
  explain: { en: "Writing a simple explanation", ur: "آسان وضاحت لکھ رہے ہیں" },
  notify: { en: "Letting you know", ur: "آپ کو اطلاع دے رہے ہیں" },
};
const ORDER = Object.keys(STEP_LABEL);

function AgentProgress({ p }: { p: ClaimProgress | null }) {
  const done = new Set<string>((p?.steps ?? []).filter((s) => s.status === "done" || s.status === "ok" || s.status === "completed").map((s) => s.step));
  const cur = p?.current_step;
  return (
    <Card className="rise space-y-3">
      <SectionTitle icon="sparkle" en="Working on your claim" ur="آپ کے دعوے پر کام ہو رہا ہے" />
      <ol className="space-y-2">
        {ORDER.map((k, i) => {
          const isDone = done.has(k) || (p ? i < Math.max(0, p.steps_done) : false);
          const isCur = !isDone && (cur === k || (!cur && i === 0));
          return (
            <li key={k} className={`flex items-center gap-3 rounded-xl px-3 py-2 ${isCur ? "bg-saffron-50" : ""}`}>
              <span className={`flex h-8 w-8 items-center justify-center rounded-full ${isDone ? "bg-ok-700 text-white" : isCur ? "bg-saffron-300 text-on-accent" : "bg-cream-2 text-ink-soft"}`}>
                {isDone ? <Icon name="check" size={18} /> : isCur ? <Spinner size={18} /> : <span className="text-xs font-bold">{i + 1}</span>}
              </span>
              <span className={`flex flex-1 flex-wrap items-baseline justify-between gap-x-3 ${isDone || isCur ? "" : "text-ink-soft"}`}>
                <span className="font-bold">{STEP_LABEL[k].en}</span>
                <span dir="rtl" lang="ur" className="font-semibold">{STEP_LABEL[k].ur}</span>
              </span>
            </li>
          );
        })}
      </ol>
      <p className="text-sm text-ink-soft">You can keep this page open. If signal drops, we continue and you can check status later.</p>
    </Card>
  );
}

export function ClaimResult({ r, statusHref, onResume, resuming }: { r: ClaimResponse; statusHref: string; onResume?: () => void; resuming?: boolean }) {
  // A mock-service failure or withdrawn consent pauses the claim at a failed step (saved, with an officer note). Offer "try again" (resume).
  const paused = (r.pipeline_steps ?? []).some((s) => s.status === "failed");
  const act = ACTION_TEXT[r.decision?.action] ?? ACTION_TEXT.send_to_human;
  const conf = r.decision?.confidence ?? 0;
  return (
    <div className="rise space-y-4" aria-live="polite">
      <div className={`flex items-start gap-4 rounded-[26px] p-5 ${act.tone}`}>
        <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-surface/60">
          <Icon name={act.icon} size={32} />
        </span>
        <div>
          <p className="text-2xl font-extrabold leading-snug">{act.en}</p>
          <p dir="rtl" lang="ur" className="text-2xl font-extrabold">{act.ur}</p>
        </div>
      </div>
      <Card className="space-y-3">
        <p className="text-lg font-semibold">{r.explanation_en}</p>
        <p dir="rtl" lang="ur" className="text-xl font-semibold">{r.explanation_ur}</p>
        <div>
          <div className="mb-1 flex justify-between text-sm font-bold">
            <span>How sure we are · <span dir="rtl" lang="ur">ہمیں کتنا یقین ہے</span></span>
            <span>{Math.round(conf * 100)}%</span>
          </div>
          <Meter value={conf} tone={conf >= 0.9 ? "ok" : conf >= 0.6 ? "warn" : "bad"} label="Confidence" />
          {conf < 0.6 && <p className="mt-1 text-sm font-semibold text-warn-ink">We are not sure, so a person will check. · <span dir="rtl" lang="ur">یقین نہیں، اس لیے انسان دیکھے گا۔</span></p>}
        </div>
        {r.decision?.reasons?.length > 0 && <ul className="list-disc space-y-1 ps-6 text-ink-soft">{r.decision.reasons.map((x) => <li key={x}>{x}</li>)}</ul>}
        <ReadAloud ur={`${act.ur} ${r.explanation_ur}`} en={`${act.en} ${r.explanation_en}`} />
      </Card>
      {paused && onResume && (
        <Button variant="accent" size="lg" full loading={resuming} icon="refresh" en="Try again" ur="دوبارہ کوشش کریں" onClick={onResume} />
      )}
      <LinkButton href={statusHref} full size="lg" icon="clock" en="Where is my claim?" ur="میرا دعویٰ کہاں ہے؟" />
    </div>
  );
}

/**
 * Whole claim journey: speak, photo, send, watch the agent work, read the result.
 * `personId` keys the saved progress (shared phones: one saved draft per person). Helpers pass `onBehalfOf`.
 */
export function ClaimFlow({ personId, onBehalfOf, statusHref }: { personId: string; onBehalfOf?: string; statusHref: string }) {
  const PAGE = onBehalfOf ? "helper-claim" : "citizen-claim";
  const [draft, setDraft] = useState<Draft>({ transcript: "", photo: null });
  const [doc, setDoc] = useState<DocumentResult | null>(null);
  const [restored, setRestored] = useState<number | null>(null);
  const [saveFailed, setSaveFailed] = useState(false);
  const [progress, setProgress] = useState<ClaimProgress | null>(null);
  const [result, setResult] = useState<ClaimResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const ready = useRef(false);

  useEffect(() => {
    if (!personId) return;
    ready.current = false;
    void loadProgress<Draft>(PAGE, personId).then((row) => {
      if (row) {
        setDraft(row.data);
        setRestored(row.savedAt);
      }
      ready.current = true;
    });
  }, [personId, PAGE]);

  function update(next: Draft) {
    setDraft(next);
    if (personId && ready.current) void saveProgress(PAGE, personId, next).then((ok) => setSaveFailed(!ok));
  }

  async function submit() {
    setBusy(true);
    setError(null);
    setProgress(null);
    try {
      const r = await submitClaim(
        { transcript: draft.transcript, document_id: doc?.document_id ?? null, on_behalf_of: onBehalfOf ?? null },
        getSession()?.token,
        setProgress,
      );
      setResult(r);
      await clearProgress(PAGE, personId);
    } catch (e) {
      setError(errorText(e, "Could not send. Your answers are saved: try again when signal is better."));
    } finally {
      setBusy(false);
    }
  }

  async function resume() {
    if (!result) return;
    setBusy(true);
    setError(null);
    try {
      const token = getSession()?.token;
      await api("POST", `/claims/${result.claim_id}/resume`, { token });
      setProgress(null);
      setResult(await followClaim(result.claim_id, token, setProgress));
    } catch (e) {
      setError(errorText(e, "Could not try again. Your claim is safe with an officer."));
    } finally {
      setBusy(false);
    }
  }

  if (busy && result) return <AgentProgress p={progress} />;
  if (result) return <><ClaimResult r={result} statusHref={statusHref} onResume={() => void resume()} />{error && <Notice tone="bad">{error}</Notice>}</>;
  if (busy) return <AgentProgress p={progress} />;

  const step = !draft.transcript ? 1 : !draft.photo ? 2 : 3;
  return (
    <div className="space-y-5">
      <ol className="rise flex items-center gap-2" aria-label="Steps">
        {[1, 2, 3].map((n) => (
          <li key={n} className={`flex h-2 flex-1 rounded-full ${n <= step ? "bg-teal-700" : "bg-line"}`} aria-current={n === step ? "step" : undefined} />
        ))}
      </ol>

      {restored && <Notice tone="info" title="We restored what you saved earlier. · آپ کا محفوظ کیا ہوا کام واپس آ گیا۔" />}
      {saveFailed && <Notice tone="warn">Saving on this phone is not available. Please do not close this page.</Notice>}

      <Card className="rise space-y-4">
        <SectionTitle icon="mic" en="1. Tell us the problem" ur="۱۔ اپنا مسئلہ بتائیں" />
        {draft.transcript ? (
          <div className="space-y-3">
            <p dir="auto" className="rounded-2xl bg-ok-soft p-4 text-xl font-semibold text-ink">“{draft.transcript}”</p>
            <Button variant="ghost" icon="refresh" en="Say it again" ur="دوبارہ بولیں" onClick={() => update({ ...draft, transcript: "" })} />
          </div>
        ) : (
          <MicButton noteKey={personId} onConfirm={(t) => update({ ...draft, transcript: t })} />
        )}
      </Card>

      <Card className="rise rise-1 space-y-4">
        <SectionTitle icon="camera" en="2. ID card photo" ur="۲۔ شناختی کارڈ کی تصویر" />
        <PhotoCapture value={draft.photo} onChange={(photo) => update({ ...draft, photo })} onResult={setDoc} citizenId={onBehalfOf} />
      </Card>

      <Card className="rise rise-2 space-y-3">
        <SectionTitle icon="send" en="3. Send" ur="۳۔ بھیجیں" />
        {error && <Notice tone="bad" title="Not sent · نہیں بھیجا جا سکا">{error}</Notice>}
        <Button size="lg" full variant="accent" disabled={!draft.transcript || (doc?.retake_needed ?? false)} onClick={() => void submit()} icon="send" en="Send my claim" ur="دعویٰ بھیجیں" />
        {doc?.retake_needed && <p className="text-sm font-semibold text-warn-ink">Please retake the photo first. · <span dir="rtl" lang="ur">پہلے تصویر دوبارہ لیں۔</span></p>}
        {!draft.photo && draft.transcript && <p className="text-sm text-ink-soft">No photo yet: we may ask for one later. · <span dir="rtl" lang="ur">ابھی تصویر نہیں، بعد میں مانگ سکتے ہیں۔</span></p>}
      </Card>
    </div>
  );
}
