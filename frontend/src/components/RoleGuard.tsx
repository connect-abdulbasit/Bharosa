"use client";
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import type { Role } from "@/lib/enums";
import { useSession } from "@/lib/auth";

/**
 * UX guard only: redirects to /login when the signed-in role is not allowed.
 * Real enforcement is server-side RBAC in the backend.
 */
export function RoleGuard({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const session = useSession();
  const router = useRouter();
  const allowed = session ? roles.includes(session.role) : false;

  useEffect(() => {
    if (session === undefined) return; // still reading storage
    if (!allowed) router.replace("/login");
  }, [session, allowed, router]);

  if (!allowed) {
    return (
      <p role="status" className="p-6 text-center text-lg">
        Checking access… · رسائی چیک ہو رہی ہے…
      </p>
    );
  }
  return <>{children}</>;
}
