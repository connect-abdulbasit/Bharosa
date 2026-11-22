"use client";
// Small helpers for the browser Speech APIs. Everything degrades gracefully when unsupported.
import { useSyncExternalStore } from "react";

type RecResult = { 0: { transcript: string }; isFinal: boolean; length: number };
export interface RecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: { resultIndex: number; results: ArrayLike<RecResult> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}

export function getRecognitionCtor(): (new () => RecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as Record<string, unknown>;
  return (w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null) as (new () => RecognitionLike) | null;
}

export function recognitionSupported(): boolean {
  return getRecognitionCtor() !== null;
}

export function synthesisSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined";
}

const noop = () => () => {};
/** SSR-safe boolean from a browser capability check. */
export function useSupported(check: () => boolean): boolean {
  return useSyncExternalStore(noop, check, () => false);
}

function pickVoice(prefix: string): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices();
  return voices.find((v) => v.lang.toLowerCase().startsWith(prefix)) ?? null;
}

/** True when this device has its own Urdu voice (rare on laptops). Voices can load late, so ask again at click time. */
export function hasUrduVoice(): boolean {
  return synthesisSupported() && pickVoice("ur") !== null;
}

/**
 * Speak Urdu if an Urdu voice exists; otherwise speak the English text with an English voice.
 * Returns which language was used, or null when speech is unavailable.
 */
export function speak(urText: string | undefined, enText: string | undefined, onEnd?: () => void): "ur" | "en" | null {
  if (!synthesisSupported()) return null;
  window.speechSynthesis.cancel();
  const urVoice = urText ? pickVoice("ur") : null;
  const useUr = Boolean(urText && urVoice);
  const text = useUr ? urText : enText ?? urText;
  if (!text) return null;
  const u = new SpeechSynthesisUtterance(text);
  if (useUr && urVoice) {
    u.voice = urVoice;
    u.lang = urVoice.lang;
  } else {
    const en = pickVoice("en");
    if (en) u.voice = en;
    u.lang = en?.lang ?? "en-US";
  }
  u.rate = 0.9; // slower for clarity
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  window.speechSynthesis.speak(u);
  return useUr ? "ur" : "en";
}

export function stopSpeaking() {
  if (synthesisSupported()) window.speechSynthesis.cancel();
}
