"use client";
import { useState } from "react";
import { PageShell } from "@/components/PageShell";
import { ReadAloud } from "@/components/ReadAloud";
import { api } from "@/lib/api";
import { getSession } from "@/lib/auth";
import type { MessageCheck } from "@/lib/types";

const LOOK: Record<string, { icon: string; en: string; ur: string; cls: string }> = {
  scam: { icon: "🚫", en: "Looks like a SCAM", ur: "یہ جعلی لگتا ہے", cls: "border-red-900 bg-red-100" },
  genuine: { icon: "✅", en: "Looks genuine", ur: "یہ اصلی لگتا ہے", cls: "border-green-900 bg-green-100" },
  unsure: { icon: "❓", en: "We are not sure", ur: "ہمیں یقین نہیں", cls: "border-amber-700 bg-amber-100" },
};

export default function CheckPage() {
  const [text, setText] = useState("");
  const [sender, setSender] = useState("");
  const [result, setResult] = useState<MessageCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function check() {
    setBusy(true);
    setError(null);
    try {
      setResult(await api<MessageCheck>("POST", "/messages/check", { body: { text, sender }, token: getSession()?.token }));
    } catch {
      setResult(null);
      setError("We could not check right now. Please try again, or ask a helper. · ابھی چیک نہیں ہو سکا، دوبارہ کوشش کریں۔");
    } finally {
      setBusy(false);
    }
  }

  const look = result ? LOOK[result.label] ?? LOOK.unsure : null;
  const lowConfidence = result ? result.confidence < 0.6 : false;

  return (
    <PageShell title="Check a message" urdu="پیغام چیک کریں" roles={["citizen", "helper"]} back={{ href: "/citizen", label: "My Bharosa / میرا بھروسہ" }}>
      <label className="block text-lg font-semibold">
        Sender (number or name) · بھیجنے والا
        <input value={sender} onChange={(e) => setSender(e.target.value)} className="mt-1 min-h-[56px] w-full rounded-xl border-2 p-3 text-xl text-black" placeholder="9090" />
      </label>
      <label className="block text-lg font-semibold">
        Message text · پیغام
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} dir="auto" className="mt-1 w-full rounded-xl border-2 p-3 text-xl text-black" />
      </label>
      <button onClick={() => void check()} disabled={busy || !text.trim() || !sender.trim()} className="min-h-[64px] w-full rounded-2xl border-2 border-teal-900 bg-teal-700 text-xl font-bold text-white disabled:opacity-50">
        {busy ? "Checking…" : "Check · چیک کریں"}
      </button>
      {error && <p role="alert" className="font-semibold text-red-700">{error}</p>}

      {result && look && (
        <section aria-live="polite" className={`space-y-3 rounded-2xl border-2 p-4 text-black ${look.cls}`}>
          <p className="text-3xl font-extrabold"><span aria-hidden>{look.icon}</span> {look.en}</p>
          <p dir="rtl" lang="ur" className="text-3xl">{look.ur}</p>
          <p className="text-lg">Confidence · اعتماد: <strong>{Math.round(result.confidence * 100)}%</strong></p>
          {lowConfidence && (
            <p className="font-semibold">We are not certain. Please do not act on it; ask a helper or an officer. · یقین نہیں، اس پر عمل نہ کریں، مددگار سے پوچھیں۔</p>
          )}
          <p className="text-lg">{result.explanation_en}</p>
          <p dir="rtl" lang="ur" className="text-xl">{result.explanation_ur}</p>
          <ul className="list-disc space-y-1 pl-6">
            {result.reasons.map((r) => <li key={r}>{r}</li>)}
          </ul>
          <ReadAloud ur={result.explanation_ur} en={result.explanation_en} />
        </section>
      )}
    </PageShell>
  );
}
