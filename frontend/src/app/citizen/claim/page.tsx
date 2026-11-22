"use client";
import { ClaimFlow } from "@/components/ClaimFlow";
import { PageShell } from "@/components/PageShell";
import { useSession } from "@/lib/auth";

export default function ClaimPage() {
  const session = useSession();
  return (
    <PageShell title="Claim help" urdu="مدد کا دعویٰ" roles={["citizen", "helper"]} back={{ href: "/citizen", label: "My Bharosa · میرا بھروسہ" }}>
      <ClaimFlow personId={session?.userId ?? ""} personName={session?.name} statusHref="/citizen/status" />
    </PageShell>
  );
}
