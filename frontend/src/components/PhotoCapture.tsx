"use client";
import { useRef } from "react";

type Props = { value: string | null; onChange: (dataUrl: string | null) => void };

/** ID card photo: opens the camera on phones, a file picker elsewhere. Preview + retake. */
export function PhotoCapture({ value, onChange }: Props) {
  const input = useRef<HTMLInputElement>(null);

  function onFile(file: File | undefined) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => onChange(typeof reader.result === "string" ? reader.result : null);
    reader.readAsDataURL(file);
  }

  function retake() {
    onChange(null);
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
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={value} alt="Your ID card photo" className="max-h-64 w-full rounded-xl border-2 object-contain" />
          <button type="button" onClick={retake} className="min-h-[56px] w-full rounded-2xl border-2 border-gray-500 bg-white text-xl font-bold text-black">
            🔄 Retake · دوبارہ لیں
          </button>
        </>
      ) : (
        <button
          type="button"
          onClick={() => input.current?.click()}
          className="flex min-h-[96px] w-full items-center justify-center gap-4 rounded-2xl border-2 border-teal-900 bg-teal-700 text-2xl font-bold text-white"
        >
          <span aria-hidden className="text-5xl">📷</span>
          <span className="flex flex-col">
            <span>Photo of ID card</span>
            <span dir="rtl" lang="ur">شناختی کارڈ کی تصویر</span>
          </span>
        </button>
      )}
      <p className="text-sm opacity-80">
        Keep the card flat, in light, with all four corners visible. · کارڈ سیدھا رکھیں، روشنی میں، چاروں کونے نظر آئیں۔
      </p>
    </div>
  );
}
