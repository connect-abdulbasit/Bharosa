"use client";
import { useEffect, useState } from "react";
import { PageShell } from "@/components/PageShell";
import { api } from "@/lib/api";
import { getSession } from "@/lib/auth";
import type { TwinProposal } from "@/lib/types";

export default function TwinPage() {
  const [data, setData] = useState<{ past_cases_total: number; proposals: TwinProposal[] } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api<{ past_cases_total: number; proposals: TwinProposal[] }>("GET", "/twin/proposals", { token: getSession()?.token })
      .then(setData)
      .catch(() => setError(true));
  }, []);

  const p = data?.proposals.find((x) => x.id === selected);

  return (
    <PageShell title="Digital Twin" urdu="ڈیجیٹل ٹوِن" roles={["admin"]} back={{ href: "/admin", label: "Admin / ایڈمن" }}>
      <p>Test a rule change on past cases before you publish it. (Simulated results for now.) · اصول بدلنے سے پہلے پرانے کیسوں پر آزمائیں۔</p>
      {error && <p role="alert" className="font-semibold text-red-700">Could not load proposals.</p>}
      {!data && !error && <p>Loading…</p>}
      <fieldset className="space-y-2">
        <legend className="text-xl font-bold">Choose a proposed change</legend>
        {data?.proposals.map((x) => (
          <label key={x.id} className={`block min-h-[64px] cursor-pointer rounded-2xl border-2 p-3 ${selected === x.id ? "border-teal-900 bg-teal-50 text-black" : ""}`}>
            <input type="radio" name="proposal" className="mr-2 h-5 w-5" checked={selected === x.id} onChange={() => setSelected(x.id)} />
            <span className="text-lg font-bold">{x.title}</span>
            <span className="block text-sm opacity-80">{x.description}</span>
          </label>
        ))}
      </fieldset>

      {p && data && (
        <section aria-live="polite" className="space-y-3 rounded-2xl border-2 border-teal-900 p-4">
          <p className="text-3xl font-extrabold">
            {p.would_change} of {data.past_cases_total} past cases would change decision
          </p>
          <ul className="list-disc pl-6">
            {Object.entries(p.breakdown).map(([k, v]) => <li key={k}>{k.replace(/_/g, " ")}: {v}</li>)}
          </ul>
          <p>Estimated cost change: <strong>{p.estimated_cost_delta > 0 ? "+" : ""}{p.estimated_cost_delta}</strong> (wrong approval 10, wrong rejection 5, review 1)</p>
          <h3 className="font-bold">Examples</h3>
          <ul className="space-y-1">
            {p.examples.map((e) => (
              <li key={e.case_id} className="rounded-lg bg-gray-100 p-2 text-black">
                {e.citizen_name} ({e.case_id}): {e.old.replace(/_/g, " ")} → <strong>{e.new.replace(/_/g, " ")}</strong>
              </li>
            ))}
          </ul>
        </section>
      )}
    </PageShell>
  );
}
