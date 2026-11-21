"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { PageShell } from "@/components/PageShell";
import { Button, Card, Field, Notice, SectionTitle } from "@/components/ui";
import { API_MODE, errorText } from "@/lib/api";
import { DEMO_USERS, HOME_FOR_ROLE, login } from "@/lib/auth";
import type { Role } from "@/lib/enums";

const ROLE_INFO: Record<Role, { icon: IconName; en: string; ur: string; line: string }> = {
  citizen: { icon: "user", en: "Citizen", ur: "شہری", line: "Check scams, claim help, control data" },
  helper: { icon: "users", en: "Helper", ur: "مددگار", line: "Help 40 families on one shared phone" },
  officer: { icon: "gavel", en: "Officer", ur: "افسر", line: "Review cases, approve payments" },
  admin: { icon: "sliders", en: "Admin", ur: "منتظم", line: "Rules, Digital Twin, Chaos Panel" },
  auditor: { icon: "scroll", en: "Auditor", ur: "آڈیٹر", line: "Read-only audit trail" },
};

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function submit(u: string, p: string, who: string) {
    setBusy(who);
    setError(null);
    try {
      const s = await login(u, p);
      router.replace(HOME_FOR_ROLE[s.role]);
    } catch (e) {
      setError(errorText(e, "Wrong username or password. · غلط صارف نام یا پاس ورڈ"));
      setBusy(null);
    }
  }

  return (
    <PageShell title="Welcome back" urdu="خوش آمدید" wide>
      <div className="grid items-start gap-8 lg:grid-cols-2">
      <Card className="rise">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            void submit(username.trim(), password, "form");
          }}
        >
          <Field label="Username" ur="صارف نام">
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoCapitalize="none" autoComplete="username" required />
          </Field>
          <Field label="Password" ur="پاس ورڈ">
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </Field>
          {error && <Notice tone="bad" title="Could not log in · لاگ ان نہیں ہو سکا">{error}</Notice>}
          <Button type="submit" full size="lg" loading={busy === "form"} disabled={!!busy} icon="arrow" en="Log in" ur="لاگ ان" />
        </form>
      </Card>

      <section aria-labelledby="demo" className="rise rise-2">
        <SectionTitle icon="sparkle" en="Try a demo user" ur="ڈیمو صارف آزمائیں" />
        <p className="mb-3 text-sm text-ink-soft">
          Fake accounts for the prototype. Tap one to sign in
          {API_MODE === "live" ? " (connected to the live backend)." : " (running on built-in sample data, no backend needed)."}
        </p>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
          {DEMO_USERS.map((u) => {
            const info = ROLE_INFO[u.role];
            return (
              <li key={u.username}>
                <button
                  type="button"
                  disabled={!!busy}
                  onClick={() => void submit(u.username, u.password, u.username)}
                  className="card card-lift flex min-h-[84px] w-full items-center gap-4 p-4 text-left disabled:opacity-60"
                >
                  <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-teal-50 text-brand">
                    <Icon name={info.icon} size={28} />
                  </span>
                  <span className="min-w-0 flex-1 leading-tight">
                    <span className="flex items-baseline gap-2">
                      <span className="text-lg font-extrabold text-heading">{info.en}</span>
                      <span dir="rtl" lang="ur" className="font-bold text-saffron-600">{info.ur}</span>
                    </span>
                    <span className="block text-sm text-ink-soft">{info.line}</span>
                  </span>
                  <Icon name="arrow" size={20} className="shrink-0 text-ink-soft" />
                </button>
              </li>
            );
          })}
        </ul>
      </section>
      </div>
    </PageShell>
  );
}
