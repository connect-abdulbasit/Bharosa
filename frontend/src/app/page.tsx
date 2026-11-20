import Link from "next/link";
import { BigIconButton } from "@/components/BigIconButton";
import { PrototypeBanner } from "@/components/PrototypeBanner";

export default function Home() {
  return (
    <>
      <PrototypeBanner />
      <main className="mx-auto w-full max-w-xl flex-1 space-y-6 p-4 pb-16">
        <header className="pt-4">
          <h1 className="text-5xl font-extrabold">Bharosa</h1>
          <p dir="rtl" lang="ur" className="text-4xl">بھروسہ</p>
          <p className="mt-3 text-xl">
            A trusted helper for public services: check messages, claim help, control your data.
          </p>
          <p dir="rtl" lang="ur" className="mt-1 text-xl">
            سرکاری خدمات کے لیے ایک قابل اعتماد مددگار: پیغام چیک کریں، مدد مانگیں، اپنا ڈیٹا اپنے قابو میں رکھیں۔
          </p>
        </header>

        <section aria-labelledby="problem">
          <h2 id="problem" className="text-2xl font-bold">The problem · مسئلہ</h2>
          <p className="mt-2 text-lg">
            People with low literacy and weak signal struggle with forms. Scam messages then make them distrust real services.
          </p>
        </section>

        <section aria-label="What you can do" className="space-y-3">
          <BigIconButton href="/citizen/check" icon="🛡️" en="Check a message" ur="پیغام چیک کریں" />
          <BigIconButton href="/citizen/claim" icon="🗣️" en="Claim help" ur="مدد کا دعویٰ کریں" />
          <BigIconButton href="/citizen/data" icon="🔐" en="Control my data" ur="میرا ڈیٹا میرے قابو میں" />
        </section>

        <p role="note" className="rounded-xl border-2 border-amber-500 bg-amber-50 p-4 text-lg text-black">
          <strong>Prototype only.</strong> Not an official service. Uses the fictional Sahara Relief Programme and simulated data.
          <span dir="rtl" lang="ur" className="mt-1 block">
            صرف نمونہ۔ سرکاری سروس نہیں۔ فرضی &quot;سہارا ریلیف پروگرام&quot; اور فرضی ڈیٹا استعمال ہوتا ہے۔
          </span>
        </p>

        <div className="grid grid-cols-2 gap-3">
          <Link href="/login" className="flex min-h-[64px] items-center justify-center rounded-2xl border-2 border-teal-900 bg-teal-700 text-xl font-bold text-white">
            Login · لاگ ان
          </Link>
          <Link href="/login?demo=1" className="flex min-h-[64px] items-center justify-center rounded-2xl border-2 border-gray-500 text-xl font-bold">
            Try demo · ڈیمو
          </Link>
        </div>
      </main>
    </>
  );
}
