"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/Icon";
import { PageShell } from "@/components/PageShell";
import { Badge, EmptyState, Notice, Skeleton } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { statusLook } from "@/lib/status";
import type { Family } from "@/lib/types";

export default function HelperHome() {
  const [families, setFamilies] = useState<Family[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    api<{ items: Family[] }>("GET", "/helper/families", { token: getSession()?.token })
      .then((r) => setFamilies(r.items))
      .catch((e) => setError(errorText(e, "Could not load families.")));
  }, []);

  const shown = useMemo(() => families?.filter((f) => f.head_name.toLowerCase().includes(q.trim().toLowerCase())) ?? [], [families, q]);

  return (
    <PageShell title="Helper Mode" urdu="مددگار موڈ" roles={["helper"]} wide>
      <Notice tone="info" title="Choose whose case you are opening.">
        <p>Only open a person&apos;s case with their permission.</p>
        <p dir="rtl" lang="ur">جس کا کیس کھولنا ہے اسے چنیں۔ صرف ان کی اجازت سے کھولیں۔</p>
      </Notice>

      {families && families.length > 6 && (
        <div className="relative">
          <Icon name="search" size={22} className="absolute start-4 top-1/2 -translate-y-1/2 text-ink-soft" />
          <input className="input ps-12" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a name · نام تلاش کریں" aria-label="Find a name" />
        </div>
      )}

      {error && <Notice tone="bad">{error}</Notice>}
      {!families && !error && <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>}
      {families && shown.length === 0 && <EmptyState icon="users" en="No one found." ur="کوئی نہیں ملا۔" />}

      <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {shown.map((f, i) => {
          const look = f.latest_case_status ? statusLook(f.latest_case_status) : null;
          return (
            <li key={f.family_id} className={`rise rise-${Math.min(i + 1, 4)}`}>
              <Link href={`/helper/${f.family_id}`} className="card card-lift flex min-h-[88px] items-center gap-4 p-4">
                <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-teal-700 text-2xl font-extrabold text-white">
                  {f.head_name.charAt(0)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-xl font-extrabold text-heading">{f.head_name}</span>
                  <span className="block text-sm text-ink-soft">{f.open_cases} open · {f.last_action}</span>
                  <span className="mt-1 flex flex-wrap gap-2">
                    {look && <Badge tone={look.tone}>{look.en}</Badge>}
                    <Badge tone={f.consent_on_file ? "ok" : "bad"} icon={f.consent_on_file ? "lock" : "alert"}>
                      {f.consent_on_file ? "Consent on file" : "No consent"}
                    </Badge>
                  </span>
                </span>
                <Icon name="arrow" size={22} className="shrink-0 text-ink-soft" />
              </Link>
            </li>
          );
        })}
      </ul>
    </PageShell>
  );
}
