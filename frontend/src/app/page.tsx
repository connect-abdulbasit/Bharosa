import { Icon, type IconName } from "@/components/Icon";
import { Logo } from "@/components/Logo";
import { PrototypeBanner } from "@/components/PrototypeBanner";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LinkButton } from "@/components/ui";

const PILLARS: { icon: IconName; en: string; ur: string; body: string; bodyUr: string; href: string; tone: string }[] = [
  {
    icon: "shield",
    en: "Check",
    ur: "چیک",
    body: "Got a payment SMS? Find out if it is a scam before you act.",
    bodyUr: "ادائیگی کا پیغام آیا؟ عمل سے پہلے جانیں کہ یہ جعلی تو نہیں۔",
    href: "/citizen/check",
    tone: "bg-teal-50 text-brand",
  },
  {
    icon: "mic",
    en: "Claim",
    ur: "دعویٰ",
    body: "Speak your problem and show your ID card. No forms to read.",
    bodyUr: "اپنا مسئلہ بولیں اور شناختی کارڈ دکھائیں۔ کوئی فارم پڑھنا نہیں۔",
    href: "/citizen/claim",
    tone: "bg-saffron-100 text-saffron-600",
  },
  {
    icon: "lock",
    en: "Control",
    ur: "اختیار",
    body: "See who has your data, and take it back whenever you want.",
    bodyUr: "دیکھیں آپ کا ڈیٹا کس کے پاس ہے، اور جب چاہیں واپس لے لیں۔",
    href: "/citizen/data",
    tone: "bg-info-soft text-info-ink",
  },
];

const STEPS: { n: string; en: string; ur: string }[] = [
  { n: "1", en: "You speak or send a photo", ur: "آپ بولتے ہیں یا تصویر بھیجتے ہیں" },
  { n: "2", en: "We check your ID and payment record, with your consent", ur: "آپ کی اجازت سے ہم شناخت اور ادائیگی کا ریکارڈ دیکھتے ہیں" },
  { n: "3", en: "If we are not sure, a real person decides", ur: "اگر یقین نہ ہو تو فیصلہ ایک انسان کرتا ہے" },
];

const SAFETY: { icon: IconName; en: string }[] = [
  { icon: "user", en: "A person approves every payment" },
  { icon: "scroll", en: "Every action is written to an audit log" },
  { icon: "lock", en: "Nothing is looked up without your consent" },
  { icon: "alert", en: "Not sure? We say so and ask a human" },
];

export default function Home() {
  return (
    <>
      <PrototypeBanner />

      <header className="hero-gradient relative overflow-hidden text-white">
        <div className="mx-auto max-w-5xl px-5 pb-16 pt-5 sm:pb-24">
          <div className="flex items-center justify-between">
            <Logo light />
            <div className="flex items-center gap-2">
              <ThemeToggle onDark />
              <LinkButton href="/login" variant="onDark" en="Login" ur="لاگ ان" />
            </div>
          </div>

          <div className="mt-12 grid items-center gap-10 sm:mt-16 md:grid-cols-[1.25fr_1fr]">
            <div className="rise">
              <p className="mb-4 inline-flex items-center gap-2 rounded-full bg-white/15 px-4 py-1.5 text-sm font-bold">
                <Icon name="heart" size={16} /> A trusted helper for public services
              </p>
              <h1 className="text-5xl font-extrabold leading-[1.05] tracking-tight sm:text-6xl">
                Your stipend.<br />
                <span className="text-saffron-300">Your voice.</span> Your say.
              </h1>
              <p dir="rtl" lang="ur" className="mt-3 text-3xl font-bold text-saffron-300 sm:text-4xl">
                آپ کی رقم۔ آپ کی آواز۔ آپ کا اختیار۔
              </p>
              <p className="mt-5 max-w-xl text-lg text-white/90">
                Bharosa helps people who cannot read forms get a missing or short relief payment resolved, on a weak signal, without middlemen, and
                without falling for fake messages.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <LinkButton href="/login?demo=1" variant="accent" size="lg" icon="sparkle" en="Try the demo" ur="ڈیمو آزمائیں" />
                <LinkButton href="/citizen/check" variant="onDark" size="lg" icon="shield" en="Check a message" ur="پیغام چیک کریں" />
              </div>
            </div>

            {/* A phone-style preview of the product promise */}
            <div className="rise rise-2 mx-auto w-full max-w-sm" aria-hidden>
              <div className="rounded-[34px] border border-white/25 bg-white/10 p-4 shadow-[0_30px_60px_rgb(0_0_0/0.25)] backdrop-blur">
                <div className="rounded-3xl bg-surface p-4 text-ink">
                  <p className="text-xs font-bold uppercase tracking-wide text-ink-soft">New SMS · 8888</p>
                  <p className="mt-1 text-sm">Your Sahara relief payment is on hold. Send your CNIC and PIN to claim now!</p>
                  <div className="mt-3 flex items-center gap-3 rounded-2xl bg-bad-soft p-3 text-bad-ink">
                    <Icon name="xCircle" size={30} />
                    <div className="leading-tight">
                      <p className="font-extrabold">Looks like a SCAM</p>
                      <p dir="rtl" lang="ur" className="font-bold">یہ جعلی لگتا ہے</p>
                    </div>
                  </div>
                  <div className="mt-3 flex items-center gap-2 text-sm font-bold text-brand">
                    <Icon name="volume" size={20} /> Listen · <span dir="rtl" lang="ur">سنیں</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 space-y-16 px-5 py-14">
        <section aria-labelledby="pillars">
          <h2 id="pillars" className="text-3xl font-extrabold text-heading">
            Three things you can do <span dir="rtl" lang="ur" className="ms-2 text-2xl text-saffron-600">تین کام جو آپ کر سکتے ہیں</span>
          </h2>
          <div className="mt-6 grid gap-5 md:grid-cols-3">
            {PILLARS.map((p, i) => (
              <a key={p.en} href={p.href} className={`card card-lift rise rise-${i + 1} flex flex-col gap-3 p-6`}>
                <span className={`flex h-16 w-16 items-center justify-center rounded-2xl ${p.tone}`}>
                  <Icon name={p.icon} size={34} />
                </span>
                <p className="flex items-baseline gap-3 text-2xl font-extrabold text-heading">
                  {p.en} <span dir="rtl" lang="ur" className="text-xl text-saffron-600">{p.ur}</span>
                </p>
                <p className="text-ink-soft">{p.body}</p>
                <p dir="rtl" lang="ur" className="text-lg text-ink-soft">{p.bodyUr}</p>
              </a>
            ))}
          </div>
        </section>

        <section aria-labelledby="how" className="grid items-start gap-10 md:grid-cols-2">
          <div>
            <h2 id="how" className="text-3xl font-extrabold text-heading">
              How it works <span dir="rtl" lang="ur" className="ms-2 text-2xl text-saffron-600">یہ کیسے کام کرتا ہے</span>
            </h2>
            <ol className="mt-6 space-y-4">
              {STEPS.map((s) => (
                <li key={s.n} className="card flex items-start gap-4 p-4">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-teal-700 text-lg font-extrabold text-white">{s.n}</span>
                  <span>
                    <span className="block font-bold">{s.en}</span>
                    <span dir="rtl" lang="ur" className="block text-ink-soft">{s.ur}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
          <div className="card p-7">
            <h3 className="text-2xl font-extrabold text-heading">Built to fail safely</h3>
            <p dir="rtl" lang="ur" className="text-left text-xl font-bold text-saffron-600">محفوظ طریقے سے ناکام ہونے کے لیے بنایا گیا</p>
            <ul className="mt-5 space-y-3">
              {SAFETY.map((s) => (
                <li key={s.en} className="flex items-center gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-brand">
                    <Icon name={s.icon} size={22} />
                  </span>
                  <span className="font-semibold">{s.en}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section aria-label="Prototype notice" className="rounded-3xl border-2 border-saffron-300 bg-saffron-50 p-6">
          <p className="flex items-center gap-2 text-lg font-extrabold text-heading">
            <Icon name="flask" size={22} /> Prototype only
          </p>
          <p className="mt-1">Not an official service. It uses the fictional &quot;Sahara Relief Programme&quot; and simulated identity, payment and SMS services.</p>
          <p dir="rtl" lang="ur" className="mt-1 text-lg">
            صرف نمونہ۔ سرکاری سروس نہیں۔ فرضی &quot;سہارا ریلیف پروگرام&quot; اور فرضی ڈیٹا استعمال ہوتا ہے۔
          </p>
        </section>
      </main>

      <footer className="border-t border-line py-8 text-center text-sm text-ink-soft">
        Bharosa · بھروسہ · Coder&apos;s Cup 2026 · The Last Mile: AI on Public Rails
      </footer>
    </>
  );
}
