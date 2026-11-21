"use client";
import { useEffect, useState } from "react";
import { speak, stopSpeaking, synthesisSupported, useSupported } from "@/lib/speech";
import { Icon } from "./Icon";

/** Speaks `ur` with an Urdu voice if the device has one; otherwise speaks `en` with an English voice. */
export function ReadAloud({ ur, en, label, autoHint }: { ur?: string; en?: string; label?: string; autoHint?: boolean }) {
  const supported = useSupported(synthesisSupported);
  const [playing, setPlaying] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  // Never keep talking after the person leaves the page.
  useEffect(() => () => stopSpeaking(), []);

  if (!ur && !en) return null;
  if (!supported) {
    return (
      <p className="text-sm text-ink-soft">
        Read-aloud is not available on this device. · <span dir="rtl" lang="ur">آواز میں سننے کی سہولت دستیاب نہیں</span>
      </p>
    );
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
        className={`inline-flex min-h-[60px] items-center gap-3 rounded-full border-2 px-6 text-lg font-extrabold transition active:scale-[0.98] ${
          playing ? "border-saffron-500 bg-saffron-300 text-on-accent" : "border-teal-700 bg-teal-700 text-white shadow-[var(--shadow-glow)] hover:bg-teal-800"
        }`}
      >
        <Icon name={playing ? "stop" : "volume"} size={26} className={playing ? "" : "motion-safe:animate-pulse"} />
        <span>{playing ? "Stop" : label ?? "Listen"}</span>
        <span dir="rtl" lang="ur">{playing ? "رکیں" : "سنیں"}</span>
      </button>
      {autoHint && !playing && <p className="mt-1 text-sm text-ink-soft">Tap to hear this read out loud. · <span dir="rtl" lang="ur">سننے کے لیے دبائیں</span></p>}
      {note && <p className="mt-1 text-sm text-ink-soft">{note}</p>}
    </div>
  );
}
