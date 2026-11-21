"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { clearProgress, loadProgress, saveProgress } from "@/lib/offline";
import { useSupported } from "@/lib/speech";
import { Icon } from "./Icon";
import { Button, Notice } from "./ui";

const PAGE = "voice-note";
const canRecord = () => typeof MediaRecorder !== "undefined" && !!navigator.mediaDevices?.getUserMedia;

/**
 * For browsers WITHOUT speech recognition (Firefox, Safari): record the person's own voice and keep it on this phone
 * so a helper can listen and type it with them. The platform only accepts text, so this is not sent anywhere.
 */
export function VoiceNote({ noteKey }: { noteKey: string }) {
  const [blob, setBlob] = useState<Blob | null>(null);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const stream = useRef<MediaStream | null>(null);

  const supported = useSupported(canRecord);

  // Restore a saved note (reload / dropped signal).
  useEffect(() => {
    if (!noteKey) return;
    void loadProgress<Blob>(PAGE, noteKey).then((row) => {
      if (row?.data) setBlob(row.data);
    });
  }, [noteKey]);

  const url = useMemo(() => (blob ? URL.createObjectURL(blob) : null), [blob]);
  useEffect(() => () => (url ? URL.revokeObjectURL(url) : undefined), [url]);

  useEffect(() => () => stream.current?.getTracks().forEach((t) => t.stop()), []);

  async function start() {
    setError(null);
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = s;
      const r = new MediaRecorder(s);
      chunks.current = [];
      r.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      r.onstop = () => {
        const b = new Blob(chunks.current, { type: r.mimeType || "audio/webm" });
        setBlob(b);
        if (noteKey) void saveProgress(PAGE, noteKey, b);
        s.getTracks().forEach((t) => t.stop());
        setRecording(false);
      };
      rec.current = r;
      r.start();
      setRecording(true);
    } catch {
      setError("The microphone could not start. Please allow it, or type instead.");
    }
  }

  if (!supported) return null;

  return (
    <div className="space-y-3 rounded-2xl bg-teal-50 p-4">
      <p className="text-sm text-ink-soft">
        We cannot turn your voice into words in this browser. Record it so a helper can listen and type it with you.
        <span dir="rtl" lang="ur" className="block">اس براؤزر میں آواز لکھائی نہیں بنتی۔ ریکارڈ کریں تاکہ مددگار سن کر لکھ دے۔</span>
      </p>
      {error && <Notice tone="warn">{error}</Notice>}
      {url && <audio controls src={url} className="w-full" aria-label="Your recording" />}
      <div className="flex flex-wrap gap-3">
        {recording ? (
          <button type="button" onClick={() => rec.current?.stop()} className="pulse-ring flex min-h-[56px] items-center gap-2 rounded-full bg-bad-700 px-6 text-lg font-extrabold text-white">
            <Icon name="stop" size={24} /> Stop · <span dir="rtl" lang="ur">رکیں</span>
          </button>
        ) : (
          <Button icon="mic" en={blob ? "Record again" : "Record my voice"} ur={blob ? "دوبارہ ریکارڈ کریں" : "آواز ریکارڈ کریں"} onClick={() => void start()} />
        )}
        {blob && !recording && (
          <Button
            variant="ghost"
            icon="trash"
            en="Delete"
            ur="مٹائیں"
            onClick={() => {
              setBlob(null);
              if (noteKey) void clearProgress(PAGE, noteKey);
            }}
          />
        )}
      </div>
    </div>
  );
}
