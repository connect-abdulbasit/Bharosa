"use client";
import { useEffect, useRef, useState } from "react";
import { apiUpload, errorText } from "@/lib/api";
import { getSession } from "@/lib/auth";
import type { DocumentResult } from "@/lib/types";
import { Icon } from "./Icon";
import { Button, Notice, Spinner } from "./ui";

type Props = {
  value: string | null; // data URL, kept in IndexedDB so a reload does not lose it
  onChange: (dataUrl: string | null) => void;
  onResult?: (doc: DocumentResult | null) => void; // the checked upload (document_id, blur, retake_needed)
  citizenId?: string | null; // helpers: the person the photo belongs to
};

/** ID card photo: opens the camera on phones, a file picker elsewhere. Preview, quality check from the server, retake. */
export function PhotoCapture({ value, onChange, onResult, citizenId }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const attempted = useRef<string | null>(null);
  const [doc, setDoc] = useState<DocumentResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function upload(blob: Blob, key: string) {
    attempted.current = key;
    setChecking(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", blob, "id-card.jpg");
      if (citizenId) form.append("citizen_id", citizenId);
      const r = await apiUpload<DocumentResult>("/documents", form, getSession()?.token);
      setDoc(r);
      onResult?.(r);
    } catch (e) {
      setDoc(null);
      onResult?.(null);
      setError(errorText(e, "We could not check the photo. You can still send your claim."));
    } finally {
      setChecking(false);
    }
  }

  // A photo restored from saved progress still needs its server check.
  useEffect(() => {
    if (!value || doc || checking || attempted.current === value) return;
    void fetch(value).then((r) => r.blob()).then((b) => upload(b, value)).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  function onFile(file: File | undefined) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const url = typeof reader.result === "string" ? reader.result : null;
      setDoc(null);
      onResult?.(null);
      onChange(url);
      if (url) void upload(file, url);
    };
    reader.readAsDataURL(file);
  }

  function retake() {
    onChange(null);
    setDoc(null);
    setError(null);
    attempted.current = null;
    onResult?.(null);
    if (input.current) input.current.value = "";
    input.current?.click();
  }

  return (
    <div className="space-y-3">
      <input
        ref={input}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        aria-label="Take a photo of your ID card"
        onChange={(e) => onFile(e.target.files?.[0])}
      />
      {value ? (
        <>
          <div className="relative overflow-hidden rounded-2xl border-2 border-line bg-cream-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={value} alt="Your ID card photo" className="max-h-64 w-full object-contain" />
            {checking && (
              <div className="absolute inset-0 flex items-center justify-center gap-3 bg-teal-950/60 text-lg font-bold text-white">
                <Spinner size={26} /> Checking photo… · <span dir="rtl" lang="ur">تصویر چیک ہو رہی ہے…</span>
              </div>
            )}
          </div>
          {doc && !doc.retake_needed && (
            <Notice tone="ok" title={<>Photo looks clear · <span dir="rtl" lang="ur">تصویر صاف ہے</span></>}>
              {doc.explanation_en}
            </Notice>
          )}
          {doc && doc.retake_needed && (
            <Notice tone="warn" title={<>Please retake the photo<span dir="rtl" lang="ur" className="ur-line">براہ کرم تصویر دوبارہ لیں</span></>}>
              <p>{doc.explanation_en}</p>
              <p dir="rtl" lang="ur">{doc.explanation_ur}</p>
            </Notice>
          )}
          {error && <Notice tone="warn">{error}</Notice>}
          <Button variant="ghost" full icon="refresh" en="Retake" ur="دوبارہ لیں" onClick={retake} />
        </>
      ) : (
        <button
          type="button"
          onClick={() => input.current?.click()}
          className="card-lift flex min-h-[110px] w-full items-center justify-center gap-4 rounded-[22px] border-2 border-dashed border-teal-700 bg-teal-50 px-4 text-heading"
        >
          <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-teal-700 text-white">
            <Icon name="camera" size={34} />
          </span>
          <span className="flex flex-col text-left leading-tight">
            <span className="text-xl font-extrabold">Photo of ID card</span>
            <span dir="rtl" lang="ur" className="text-xl font-bold">شناختی کارڈ کی تصویر</span>
          </span>
        </button>
      )}
      <p className="text-sm text-ink-soft">
        Keep the card flat, in light, with all four corners visible.<span dir="rtl" lang="ur" className="ur-line">کارڈ سیدھا رکھیں، روشنی میں، چاروں کونے نظر آئیں۔</span>
      </p>
    </div>
  );
}
