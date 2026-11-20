"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { PageShell } from "@/components/PageShell";
import { api } from "@/lib/api";
import { getSession } from "@/lib/auth";
import type { Family } from "@/lib/types";

export default function HelperHome() {
  const [families, setFamilies] = useState<Family[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api<{ items: Family[] }>("GET", "/helper/families", { token: getSession()?.token })
      .then((r) => setFamilies(r.items))
      .catch(() => setError(true));
  }, []);

  return (
    <PageShell title="Helper Mode" urdu="مددگار موڈ" roles={["helper"]}>
      <p className="text-lg">Choose whose case you are opening. Only open a person&apos;s case with their permission. · جس کا کیس کھولنا ہے اسے چنیں۔ صرف ان کی اجازت سے کھولیں۔</p>
      {error && <p role="alert" className="font-semibold text-red-700">Could not load families. · فہرست لوڈ نہیں ہوئی۔</p>}
      {!families && !error && <p>Loading… · لوڈ ہو رہا ہے…</p>}
      <ul className="space-y-3">
        {families?.map((f, i) => (
          <li key={f.family_id}>
            <Link href={`/helper/${i + 1}`} className="flex min-h-[72px] items-center justify-between rounded-2xl border-2 p-4">
              <span>
                <span className="block text-xl font-bold">{f.head_name}</span>
                <span className="text-sm opacity-80">{f.open_cases} open · {f.last_action}</span>
              </span>
              <span aria-hidden className="text-3xl">{f.consent_on_file ? "🔐" : "⚠️"}</span>
            </Link>
          </li>
        ))}
      </ul>
    </PageShell>
  );
}
