"use client";
import { useEffect, useRef, useState } from "react";
import { apiSpeech } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { hasUrduVoice, speak, stopSpeaking, synthesisSupported, useSupported } from "@/lib/speech";
import { Icon } from "./Icon";

/**
 * Speaks `ur` with the device's Urdu voice if it has one; otherwise asks the server for an Urdu voice (POST /tts);
 * if that is unavailable too, speaks `en` with an English voice.
 */
export function ReadAloud({ ur, en, label, autoHint }: { ur?: string; en?: string; label?: string; autoHint?: boolean }) {
  const supported = useSupported(synthesisSupported);
  const [playing, setPlaying] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const run = useRef(0); // ignores a server answer that arrives after the person pressed Stop

  function stopAll() {
    run.current += 1;
    audio.current?.pause();
    audio.current = null;
    stopSpeaking();
    setLoading(false);
    setPlaying(false);
  }

  // Never keep talking after the person leaves the page.
  useEffect(() => () => {
    run.current += 1;
    audio.current?.pause();
    stopSpeaking();
  }, []);

  if (!ur && !en) return null;
  if (!supported) {
    return (
      <p className="text-sm text-ink-soft">
        Read-aloud is not available on this device. · <span dir="rtl" lang="ur">آواز میں سننے کی سہولت دستیاب نہیں</span>
      </p>
    );
  }

  async function toggle() {
    if (playing || loading) {
      stopAll();
      return;
    }
    setNote(null);
    // 1. the device has an Urdu voice, or there is no Urdu text: the browser speaks
    if (!ur || hasUrduVoice()) {
      const used = speak(ur, en, () => setPlaying(false));
      setPlaying(used !== null);
      return;
    }
    // 2. no Urdu voice on this device: ask the server for one
    const mine = ++run.current;
    setLoading(true);
    const url = await apiSpeech(ur, "ur", getSession()?.token);
    if (mine !== run.current) return;
    setLoading(false);
    if (url) {
      const a = new Audio(url);
      audio.current = a;
      a.onended = () => setPlaying(false);
      a.onerror = () => setPlaying(false);
      try {
        await a.play();
        setPlaying(true);
        return;
      } catch {
        audio.current = null; // autoplay blocked or bad audio: fall through to the browser voice
      }
    }
    // 3. server voice unavailable: English with the browser voice, and say so
    const used = speak(ur, en, () => setPlaying(false));
    setPlaying(used !== null);
    setNote(used === "en" ? "Urdu voice is not available right now: reading English." : null);
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => void toggle()}
        aria-pressed={playing}
        aria-busy={loading}
        className={`inline-flex min-h-[60px] items-center gap-3 rounded-full border-2 px-6 text-lg font-extrabold transition active:scale-[0.98] ${
          playing ? "border-saffron-500 bg-saffron-300 text-on-accent" : "border-teal-700 bg-teal-700 text-white shadow-[var(--shadow-glow)] hover:bg-teal-800"
        }`}
      >
        <Icon name={playing ? "stop" : "volume"} size={26} className={playing ? "" : "motion-safe:animate-pulse"} />
        <span>{playing || loading ? "Stop" : label ?? "Listen"}</span>
        <span dir="rtl" lang="ur">{playing || loading ? "رکیں" : "سنیں"}</span>
      </button>
      {autoHint && !playing && <p className="mt-1 text-sm text-ink-soft">Tap to hear this read out loud. · <span dir="rtl" lang="ur">سننے کے لیے دبائیں</span></p>}
      {note && <p className="mt-1 text-sm text-ink-soft">{note}</p>}
    </div>
  );
}
