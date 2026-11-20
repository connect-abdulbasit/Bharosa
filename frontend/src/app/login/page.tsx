"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { PageShell } from "@/components/PageShell";
import { DEMO_USERS, HOME_FOR_ROLE, login } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(u: string, p: string) {
    setBusy(true);
    setError(null);
    try {
      const s = await login(u, p);
      router.replace(HOME_FOR_ROLE[s.role]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
      setBusy(false);
    }
  }

  return (
    <PageShell title="Login" urdu="لاگ ان">
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          void submit(username, password);
        }}
      >
        <label className="block text-lg font-semibold">
          Username · صارف نام
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoCapitalize="none" autoComplete="username" className="mt-1 min-h-[56px] w-full rounded-xl border-2 p-3 text-xl text-black" />
        </label>
        <label className="block text-lg font-semibold">
          Password · پاس ورڈ
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" className="mt-1 min-h-[56px] w-full rounded-xl border-2 p-3 text-xl text-black" />
        </label>
        {error && <p role="alert" className="font-semibold text-red-700">{error}</p>}
        <button disabled={busy} className="min-h-[64px] w-full rounded-2xl border-2 border-teal-900 bg-teal-700 text-xl font-bold text-white disabled:opacity-50">
          Login · لاگ ان
        </button>
      </form>

      <section aria-labelledby="demo" className="rounded-xl border-2 border-dashed p-3">
        <h2 id="demo" className="text-xl font-bold">Demo users · ڈیمو صارفین</h2>
        <p className="text-sm opacity-80">Fake accounts for the prototype. Tap one to sign in.</p>
        <ul className="mt-2 space-y-2">
          {DEMO_USERS.map((u) => (
            <li key={u.username}>
              <button
                type="button"
                disabled={busy}
                onClick={() => void submit(u.username, u.password)}
                className="flex min-h-[56px] w-full items-center justify-between rounded-xl border-2 px-3 text-left"
              >
                <span className="text-lg font-bold capitalize">{u.role}</span>
                <span className="text-sm opacity-80">{u.username} / {u.password}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </PageShell>
  );
}
