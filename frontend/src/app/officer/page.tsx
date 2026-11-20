"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { PageShell } from "@/components/PageShell";
import { api } from "@/lib/api";
import { getSession } from "@/lib/auth";
import type { QueueItem } from "@/lib/types";

export default function OfficerQueue() {
  const [items, setItems] = useState<QueueItem[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api<{ items: QueueItem[] }>("GET", "/queue", { token: getSession()?.token })
      .then((r) => setItems(r.items))
      .catch(() => setError(true));
  }, []);

  return (
    <PageShell title="Review queue" urdu="جائزہ قطار" roles={["officer", "admin"]}>
      <p className="text-sm opacity-80">Sorted by risk (high first), then confidence (low first). · خطرے کے لحاظ سے ترتیب۔</p>
      {error && <p role="alert" className="font-semibold text-red-700">Could not load the queue.</p>}
      {!items && !error && <p>Loading…</p>}
      <ul className="space-y-3">
        {items?.map((q) => (
          <li key={q.case_id}>
            <Link href={`/officer/case/${q.case_id}`} className="block rounded-2xl border-2 p-4">
              <span className="flex items-center justify-between">
                <span className="text-xl font-bold">{q.citizen_name}</span>
                <span className="rounded-full bg-red-100 px-3 py-1 text-sm font-bold text-red-900">risk {Math.round(q.risk_score * 100)}%</span>
              </span>
              <span className="block text-sm">confidence {Math.round(q.confidence * 100)}% · suggested: {q.recommended_action.replace(/_/g, " ")}</span>
              <span className="block text-sm opacity-80">{q.reasons.join("; ")}</span>
            </Link>
          </li>
        ))}
      </ul>
    </PageShell>
  );
}
