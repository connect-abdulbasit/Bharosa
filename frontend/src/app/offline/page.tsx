import { Icon } from "@/components/Icon";
import { Logo } from "@/components/Logo";
import { RetryButton } from "./RetryButton";

export const metadata = { title: "Offline" };

/** Shown by the service worker when a page is not available without signal. */
export default function OfflinePage() {
  return (
    <>
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center justify-center gap-6 px-6 py-16 text-center">
        <Logo />
        <span className="flex h-24 w-24 items-center justify-center rounded-full bg-teal-50 text-brand">
          <Icon name="wifiOff" size={48} />
        </span>
        <div className="space-y-1">
          <h1 className="text-3xl font-extrabold text-heading">No signal right now</h1>
          <p dir="rtl" lang="ur" className="text-2xl font-bold text-saffron-600">ابھی سگنل نہیں ہے</p>
        </div>
        <p className="text-ink-soft">
          Anything you already typed or recorded is saved on this phone. It will still be here when the signal comes back.
        </p>
        <p dir="rtl" lang="ur" className="text-lg text-ink-soft">جو کچھ آپ نے لکھا یا ریکارڈ کیا وہ اس فون پر محفوظ ہے۔ سگنل آنے پر وہیں ملے گا۔</p>
        <RetryButton />
      </main>
    </>
  );
}
