"use client";
import { useEffect, useRef, useState } from "react";
import { getRecognitionCtor, recognitionSupported, useSupported, type RecognitionLike } from "@/lib/speech";
import { Icon } from "./Icon";
import { Notice } from "./ui";
import { VoiceNote } from "./VoiceNote";

type Props = { onConfirm: (transcript: string) => void; lang?: string; noteKey?: string };

/**
 * Tap to speak (Urdu by default). Shows what we heard and asks Yes/No before accepting.
 * If speech recognition is unsupported, falls back to a typing box with the same confirm step.
 */
export function MicButton({ onConfirm, lang = "ur-PK", noteKey }: Props) {
  const supported = useSupported(recognitionSupported);
  const [listening, setListening] = useState(false);
  const [text, setText] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<RecognitionLike | null>(null);

  useEffect(() => () => rec.current?.stop(), []);

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
      setError(e.error === "not-allowed" ? "Microphone permission was denied. You can type instead." : "We could not hear you. Please try again.");
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
    <div className="space-y-4">
      {supported ? (
        <div className="flex flex-col items-center gap-3 rounded-[28px] bg-teal-50 p-6">
          <button
            type="button"
            onClick={listening ? () => rec.current?.stop() : start}
            aria-pressed={listening}
            aria-label={listening ? "Stop listening" : "Tap and speak"}
            className={`flex h-32 w-32 items-center justify-center rounded-full border-4 border-white text-white transition active:scale-95 ${
              listening ? "pulse-ring bg-bad-700" : "bg-teal-700 shadow-[var(--shadow-glow)] hover:bg-teal-800"
            }`}
          >
            <Icon name={listening ? "stop" : "mic"} size={56} />
          </button>
          <p className="text-center text-xl font-extrabold leading-tight text-heading">
            {listening ? "Listening… tap to stop" : "Tap and speak"}
            <span dir="rtl" lang="ur" className="block">{listening ? "سن رہے ہیں… رکنے کے لیے دبائیں" : "دبائیں اور بولیں"}</span>
          </p>
        </div>
      ) : (
        <div className="space-y-2 rounded-2xl border-2 border-dashed border-line bg-surface p-4">
          <p className="text-sm text-ink-soft">
            Voice is not supported in this browser, please type.<span dir="rtl" lang="ur" className="ur-line">اس براؤزر میں آواز کام نہیں کرتی، براہ کرم لکھیں۔</span>
          </p>
          {noteKey && <VoiceNote noteKey={noteKey} />}
          <textarea
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setAsking(e.target.value.trim().length > 0);
            }}
            rows={3}
            dir="auto"
            aria-label="Describe your problem"
            className="input"
          />
        </div>
      )}
      {error && <Notice tone="warn">{error}</Notice>}
      {text && supported && (
        <p dir="auto" className="rounded-2xl bg-surface p-4 text-xl font-semibold shadow-[var(--shadow-sm)]">
          “{text}”
        </p>
      )}
      {asking && text.trim() && !listening && (
        <div className="space-y-2">
          <p className="text-lg font-extrabold text-heading">
            Is this correct? <span dir="rtl" lang="ur">کیا یہ صحیح ہے؟</span>
          </p>
          <div className="grid grid-cols-2 gap-3">
            <button type="button" onClick={yes} className="flex min-h-[68px] items-center justify-center gap-2 rounded-2xl bg-ok-700 text-xl font-extrabold text-white active:scale-[0.98]">
              <Icon name="check" size={26} /> Yes · <span dir="rtl" lang="ur">ہاں</span>
            </button>
            <button type="button" onClick={no} className="flex min-h-[68px] items-center justify-center gap-2 rounded-2xl border-2 border-line bg-surface text-xl font-extrabold active:scale-[0.98]">
              <Icon name="refresh" size={24} /> No · <span dir="rtl" lang="ur">نہیں</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
