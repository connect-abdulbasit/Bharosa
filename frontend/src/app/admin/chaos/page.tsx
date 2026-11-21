"use client";
import { useCallback, useState } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { PageShell } from "@/components/PageShell";
import { Badge, Button, Card, Notice, SectionTitle, Skeleton } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { useLoader } from "@/lib/hooks";
import type { ChaosLive } from "@/lib/types";

type Key = "identity_down" | "ledger_down" | "payments_down";
const SWITCHES: { key: Key; icon: IconName; en: string; ur: string; effect: string }[] = [
  { key: "identity_down", icon: "user", en: "Identity service down", ur: "شناختی سروس بند", effect: "New claims pause with an officer note. No guessing, no 500." },
  { key: "ledger_down", icon: "list", en: "Payment record down", ur: "ادائیگی ریکارڈ بند", effect: "We cannot see payments, so a person must decide." },
  { key: "payments_down", icon: "send", en: "Payments rail down", ur: "ادائیگی نظام بند", effect: "Approval fails safely (503). Nobody is paid twice on retry." },
];

type Health = { status: string; database: string; mocks?: { mode?: string; reachable?: boolean }; ai_mode?: string; worker?: { mode?: string; alive?: boolean }; version?: string };

export default function ChaosPage() {
  const [state, setState] = useState<ChaosLive | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getSession()?.token;
    try {
      setState(await api<ChaosLive>("GET", "/admin/demo/chaos", { token }));
      setError(null);
    } catch (e) {
      setError(errorText(e, "Chaos controls are not available (is DEMO_MODE on?)."));
    }
    try {
      setHealth(await api<Health>("GET", "/health"));
    } catch {
      setHealth(null);
    }
  }, []);
  useLoader(load);

  async function toggle(key: Key) {
    if (!state) return;
    setBusy(key);
    try {
      const next = await api<ChaosLive>("POST", "/admin/demo/chaos", { body: { [key]: !state[key] }, token: getSession()?.token });
      setState((s) => ({ ...(s as ChaosLive), ...next }));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  async function reset() {
    setBusy("reset");
    setMsg(null);
    try {
      await api("POST", "/admin/demo/reset", { body: { include_rules: false }, token: getSession()?.token });
      setMsg("Demo state restored. Rules and the audit log were kept.");
      setConfirmReset(false);
      void load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  const anyDown = state ? SWITCHES.some((s) => state[s.key]) : false;

  return (
    <PageShell title="Chaos Panel" urdu="خرابی کا پینل" roles={["admin"]} back={{ href: "/admin", label: "Admin · ایڈمن" }} wide>
      <Notice tone="info" title="Break things on purpose to show the system fails safely.">
        <p>A failure never becomes a raw error for the citizen: the case goes to a person with notes.</p>
      </Notice>
      {error && <Notice tone="bad">{error}</Notice>}

      <div className="grid items-start gap-5 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          {!state && !error && <Skeleton className="h-56" />}
          {state && (
            <>
              {anyDown && <Notice tone="warn" title="Something is switched off right now. Remember to switch it back on." />}
              {SWITCHES.map((s) => {
                const down = state[s.key];
                return (
                  <Card key={s.key} className={`rise flex flex-wrap items-center gap-4 ${down ? "border-bad-700 bg-bad-soft" : ""}`}>
                    <span className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl ${down ? "bg-bad-700 text-white" : "bg-teal-50 text-brand"}`}><Icon name={s.icon} size={28} /></span>
                    <div className="min-w-0 flex-1">
                      <p className="text-lg font-extrabold">{s.en} <span dir="rtl" lang="ur" className="text-saffron-600">· {s.ur}</span></p>
                      <p className="text-sm text-ink-soft">{s.effect}</p>
                    </div>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={down}
                      aria-label={s.en}
                      disabled={busy === s.key}
                      onClick={() => void toggle(s.key)}
                      className={`relative h-10 w-[72px] shrink-0 rounded-full transition ${down ? "bg-bad-700" : "bg-line"} disabled:opacity-60`}
                    >
                      <span className={`absolute top-1 h-8 w-8 rounded-full bg-surface shadow transition-all ${down ? "left-[36px]" : "left-1"}`} />
                    </button>
                  </Card>
                );
              })}
            </>
          )}
        </div>

        <div className="space-y-5">
          <Card className="space-y-3">
            <SectionTitle icon="bolt" en="System health" ur="نظام کی صحت" />
            {!health ? <p className="text-sm text-ink-soft">Health check unavailable.</p> : (
              <ul className="space-y-2 text-sm">
                <li className="flex justify-between"><span>API</span><Badge tone={health.status === "ok" ? "ok" : "bad"}>{health.status}</Badge></li>
                <li className="flex justify-between"><span>Database</span><Badge tone={health.database === "ok" ? "ok" : "bad"}>{health.database}</Badge></li>
                <li className="flex justify-between"><span>Mocks ({health.mocks?.mode})</span><Badge tone={health.mocks?.reachable ? "ok" : "bad"}>{health.mocks?.reachable ? "reachable" : "down"}</Badge></li>
                <li className="flex justify-between"><span>Worker ({health.worker?.mode})</span><Badge tone={health.worker?.alive ? "ok" : "bad"}>{health.worker?.alive ? "alive" : "stopped"}</Badge></li>
                <li className="flex justify-between"><span>AI mode</span><Badge tone="neutral">{health.ai_mode}</Badge></li>
              </ul>
            )}
            <Button variant="ghost" full icon="refresh" en="Refresh" onClick={() => void load()} />
          </Card>

          <Card className="space-y-3">
            <SectionTitle icon="refresh" en="Reset the demo" ur="ڈیمو ری سیٹ" />
            <p className="text-sm text-ink-soft">Restores the known demo cases and users. The audit log is never wiped.</p>
            {msg && <Notice tone="ok">{msg}</Notice>}
            {confirmReset ? (
              <div className="grid grid-cols-2 gap-3">
                <Button variant="danger" loading={busy === "reset"} icon="trash" en="Yes, reset" onClick={() => void reset()} />
                <Button variant="ghost" disabled={busy === "reset"} en="Cancel" onClick={() => setConfirmReset(false)} />
              </div>
            ) : (
              <Button variant="ghost" full icon="refresh" en="Reset demo data" ur="ڈیمو ڈیٹا ری سیٹ" onClick={() => setConfirmReset(true)} />
            )}
          </Card>
        </div>
      </div>
    </PageShell>
  );
}
