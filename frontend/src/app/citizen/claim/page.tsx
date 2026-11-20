"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { MicButton } from "@/components/MicButton";
import { PageShell } from "@/components/PageShell";
import { PhotoCapture } from "@/components/PhotoCapture";
import { ReadAloud } from "@/components/ReadAloud";
import { api } from "@/lib/api";
import { getSession, useSession } from "@/lib/auth";
import { clearProgress, loadProgress, saveProgress } from "@/lib/offline";
import type { ClaimResponse } from "@/lib/types";

type Draft = { transcript: string; photo: string | null };
const PAGE = "citizen-claim";
const ACTION_TEXT: Record<string, { en: string; ur: string }> = {
  auto_handle: { en: "Your claim is moving forward. An officer must still approve any payment.", ur: "آپ کا دعویٰ آگے بڑھ رہا ہے۔ ادائیگی کی منظوری افسر دے گا۔" },
  ask_more: { en: "We need a little more proof.", ur: "ہمیں تھوڑا اور ثبوت چاہیے۔" },
  send_to_human: { en: "A person (officer) will check your claim.", ur: "ایک افسر آپ کا دعویٰ خود دیکھے گا۔" },
};

export default function ClaimPage() {
  const session = useSession();
  const personId = session?.userId ?? "";
  const [draft, setDraft] = useState<Draft>({ transcript: "", photo: null });
  const [restored, setRestored] = useState<number | null>(null);
  const [saveFailed, setSaveFailed] = useState(false);
  const [result, setResult] = useState<ClaimResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const ready = useRef(false);

  // Restore saved progress for this person (reload / dropped connection).
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
  }, [personId]);

  function update(next: Draft) {
    setDraft(next);
    if (personId && ready.current) void saveProgress(PAGE, personId, next).then((ok) => setSaveFailed(!ok));
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const r = await api<ClaimResponse>("POST", "/claims", { body: { transcript: draft.transcript }, token: getSession()?.token });
      setResult(r);
      await clearProgress(PAGE, personId);
    } catch {
      setError("Could not send. Your answers are saved: try again when signal is better. · بھیج نہیں سکے۔ آپ کے جوابات محفوظ ہیں، سگنل بہتر ہونے پر دوبارہ کوشش کریں۔");
    } finally {
      setBusy(false);
    }
  }

  const act = result ? ACTION_TEXT[result.decision.action] ?? ACTION_TEXT.send_to_human : null;

  return (
    <PageShell title="Claim help" urdu="مدد کا دعویٰ" roles={["citizen", "helper"]} back={{ href: "/citizen", label: "My Bharosa / میرا بھروسہ" }}>
      {result && act ? (
        <section aria-live="polite" className="space-y-3 rounded-2xl border-2 border-teal-900 bg-teal-50 p-4 text-black">
          <p className="text-2xl font-extrabold">{act.en}</p>
          <p dir="rtl" lang="ur" className="text-2xl">{act.ur}</p>
          <p className="text-lg">{result.explanation_en}</p>
          <p dir="rtl" lang="ur" className="text-xl">{result.explanation_ur}</p>
          <p className="text-sm">Confidence · اعتماد: {Math.round(result.decision.confidence * 100)}%</p>
          <ul className="list-disc pl-6">{result.decision.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          <ReadAloud ur={`${act.ur} ${result.explanation_ur}`} en={`${act.en} ${result.explanation_en}`} />
          <Link href="/citizen/status" className="flex min-h-[64px] items-center justify-center rounded-2xl border-2 border-teal-900 bg-teal-700 text-xl font-bold text-white">
            📍 Where is my claim? · میرا دعویٰ کہاں ہے؟
          </Link>
        </section>
      ) : (
        <>
          {restored && (
            <p className="rounded-xl bg-blue-50 p-3 text-black">
              ♻️ We restored what you saved earlier. · آپ کا محفوظ کیا ہوا کام واپس آ گیا۔
            </p>
          )}
          {saveFailed && <p className="text-sm text-amber-800">Saving on this phone is not available; do not close this page.</p>}

          <section aria-labelledby="s1" className="space-y-3">
            <h2 id="s1" className="text-2xl font-bold">1. Tell us the problem · اپنا مسئلہ بتائیں</h2>
            {draft.transcript ? (
              <div className="space-y-2 rounded-xl bg-green-50 p-3 text-black">
                <p dir="auto" className="text-xl">“{draft.transcript}”</p>
                <button type="button" onClick={() => update({ ...draft, transcript: "" })} className="min-h-[48px] rounded-xl border-2 px-4 font-semibold">
                  Say it again · دوبارہ بولیں
                </button>
              </div>
            ) : (
              <MicButton onConfirm={(t) => update({ ...draft, transcript: t })} />
            )}
          </section>

          <section aria-labelledby="s2" className="space-y-3">
            <h2 id="s2" className="text-2xl font-bold">2. ID card photo · شناختی کارڈ کی تصویر</h2>
            <PhotoCapture value={draft.photo} onChange={(photo) => update({ ...draft, photo })} />
          </section>

          <section aria-labelledby="s3" className="space-y-3">
            <h2 id="s3" className="text-2xl font-bold">3. Send · بھیجیں</h2>
            {error && <p role="alert" className="font-semibold text-red-700">{error}</p>}
            <button onClick={() => void submit()} disabled={busy || !draft.transcript} className="min-h-[72px] w-full rounded-2xl border-2 border-teal-900 bg-teal-700 text-2xl font-bold text-white disabled:opacity-50">
              {busy ? "Sending…" : "📨 Send my claim · دعویٰ بھیجیں"}
            </button>
            {!draft.photo && draft.transcript && <p className="text-sm">No photo yet: we may ask for one later. · ابھی تصویر نہیں، بعد میں مانگ سکتے ہیں۔</p>}
          </section>
        </>
      )}
    </PageShell>
  );
}
