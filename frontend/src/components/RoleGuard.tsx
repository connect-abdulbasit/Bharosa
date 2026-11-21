"use client";
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import type { Role } from "@/lib/enums";
import { HOME_FOR_ROLE, useSession } from "@/lib/auth";
import { Skeleton } from "./ui";

/**
 * UX guard only: sends people without the right role elsewhere.
 * Real enforcement is server-side RBAC in the backend.
 */
export function RoleGuard({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const session = useSession();
  const router = useRouter();
  const allowed = session ? roles.includes(session.role) : false;

  useEffect(() => {
    if (session === undefined) return; // still reading storage
    if (!session) router.replace("/login");
    else if (!allowed) router.replace(HOME_FOR_ROLE[session.role]);
  }, [session, allowed, router]);

  if (!allowed) {
    return (
      <div role="status" aria-label="Checking access" className="space-y-4 py-6">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
        <p className="text-center text-sm text-ink-soft">
          Checking access… · <span dir="rtl" lang="ur">رسائی چیک ہو رہی ہے…</span>
        </p>
      </div>
    );
  }
  return <>{children}</>;
}
