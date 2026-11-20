"use client";
import { useRef, useState } from "react";
import { getRecognitionCtor, recognitionSupported, useSupported, type RecognitionLike } from "@/lib/speech";

type Props = { onConfirm: (transcript: string) => void; lang?: string };

/**
 * Tap to speak (Urdu by default). Shows what we heard and asks Yes/No before accepting.
 * If speech recognition is unsupported, falls back to a typing box with the same confirm step.
 */
export function MicButton({ onConfirm, lang = "ur-PK" }: Props) {
  const supported = useSupported(recognitionSupported);
  const [listening, setListening] = useState(false);
  const [text, setText] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<RecognitionLike | null>(null);

  function start() {
    const Ctor = getRecognitionCtor();
    if (!Ctor) return;
    setError(null);
    setText("");
    setAsking(false);
    const r = new Ctor();
    r.lang = lang;
    r.interimResults = true;
    r.continuous = false;
    r.onresult = (e) => {
      let t = "";
      for (let i = 0; i < e.results.length; i++) t += e.results[i][0].transcript;
      setText(t);
    };
    r.onerror = (e) => {
      setError(e.error === "not-allowed" ? "Microphone permission was denied." : "We could not hear you. Please try again.");
      setListening(false);
    };
    r.onend = () => {
      setListening(false);
      setAsking(true);
    };
    rec.current = r;
    setListening(true);
    try {
      r.start();
    } catch {
      setListening(false);
      setError("The microphone could not start.");
    }
  }

  function stop() {
    rec.current?.stop();
  }

  function yes() {
    if (!text.trim()) return;
    onConfirm(text.trim());
    setAsking(false);
  }

  function no() {
    setText("");
    setAsking(false);
  }

  return (
    <div className="space-y-3">
      {supported ? (
        <button
          type="button"
          onClick={listening ? stop : start}
          aria-pressed={listening}
          className={`flex min-h-[96px] w-full items-center justify-center gap-4 rounded-2xl border-2 text-2xl font-bold ${
            listening ? "animate-pulse border-red-900 bg-red-700 text-white" : "border-teal-900 bg-teal-700 text-white"
          }`}
        >
          <span aria-hidden className="text-5xl">{listening ? "⏹" : "🎤"}</span>
          <span className="flex flex-col">
            <span>{listening ? "Listening… tap to stop" : "Tap and speak"}</span>
            <span dir="rtl" lang="ur">{listening ? "سن رہے ہیں… رکنے کے لیے دبائیں" : "دبائیں اور بولیں"}</span>
          </span>
        </button>
      ) : (
        <div className="rounded-xl border-2 border-dashed p-3">
          <p className="text-sm">
            Voice is not supported in this browser, please type. · اس براؤزر میں آواز کام نہیں کرتی، براہ کرم لکھیں۔
          </p>
          <textarea
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setAsking(e.target.value.trim().length > 0);
            }}
            rows={3}
            dir="auto"
            aria-label="Describe your problem"
            className="mt-2 w-full rounded-lg border-2 p-3 text-lg text-black"
          />
        </div>
      )}
      {error && <p role="alert" className="font-semibold text-red-700">{error}</p>}
      {text && (
        <p dir="auto" className="rounded-xl bg-gray-100 p-3 text-xl text-black">
          “{text}”
        </p>
      )}
      {asking && text.trim() && !listening && (
        <div className="space-y-2">
          <p className="text-lg font-semibold">
            Is this correct? <span dir="rtl" lang="ur">کیا یہ صحیح ہے؟</span>
          </p>
          <div className="grid grid-cols-2 gap-3">
            <button type="button" onClick={yes} className="min-h-[64px] rounded-2xl border-2 border-green-900 bg-green-700 text-xl font-bold text-white">
              ✅ Yes · ہاں
            </button>
            <button type="button" onClick={no} className="min-h-[64px] rounded-2xl border-2 border-gray-500 bg-white text-xl font-bold text-black">
              ↩ No · نہیں
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
