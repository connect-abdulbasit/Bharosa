"use client";
import { useState } from "react";
import { speak, stopSpeaking, synthesisSupported, useSupported } from "@/lib/speech";


/** Speaks `ur` with an Urdu voice if the device has one; otherwise speaks `en` with an English voice. */
export function ReadAloud({ ur, en, label }: { ur?: string; en?: string; label?: string }) {
  const supported = useSupported(synthesisSupported);
  const [playing, setPlaying] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  if (!ur && !en) return null;
  if (!supported) {
    return <p className="text-sm opacity-70">Read-aloud is not available on this device. · آواز میں سننے کی سہولت دستیاب نہیں</p>;
  }

  function toggle() {
    if (playing) {
      stopSpeaking();
      setPlaying(false);
      return;
    }
    const used = speak(ur, en, () => setPlaying(false));
    setPlaying(used !== null);
    setNote(used === "en" && ur ? "No Urdu voice on this device: reading English." : null);
  }

  return (
    <div>
      <button
        type="button"
        onClick={toggle}
        aria-pressed={playing}
        className="inline-flex min-h-[56px] items-center gap-3 rounded-full border-2 border-teal-800 bg-teal-50 px-5 text-lg font-semibold text-teal-900"
      >
        <span aria-hidden className="text-2xl">{playing ? "⏹" : "🔊"}</span>
        <span>{playing ? "Stop" : label ?? "Listen"}</span>
        <span dir="rtl" lang="ur">{playing ? "رکیں" : "سنیں"}</span>
      </button>
      {note && <p className="mt-1 text-sm opacity-70">{note}</p>}
    </div>
  );
}
