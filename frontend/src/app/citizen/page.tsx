import { BigIconButton } from "@/components/BigIconButton";
import { PageShell } from "@/components/PageShell";

export default function CitizenHome() {
  return (
    <PageShell title="My Bharosa" urdu="میرا بھروسہ" roles={["citizen", "helper"]}>
      <div className="space-y-3">
        <BigIconButton href="/citizen/check" icon="🛡️" en="Check a message" ur="پیغام چیک کریں" tone="primary" />
        <BigIconButton href="/citizen/claim" icon="🗣️" en="Claim help" ur="مدد کا دعویٰ کریں" tone="primary" />
        <BigIconButton href="/citizen/status" icon="📍" en="Where is my claim?" ur="میرا دعویٰ کہاں ہے؟" />
        <BigIconButton href="/citizen/data" icon="🔐" en="My data" ur="میرا ڈیٹا" />
      </div>
    </PageShell>
  );
}
