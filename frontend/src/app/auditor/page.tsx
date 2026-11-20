import { PageShell } from "@/components/PageShell";

export default function AuditorPage() {
  return (
    <PageShell
      roles={["auditor", "admin"]}
      title="Audit log"
      urdu="آڈٹ لاگ"
      note="TODO(Hani): filterable audit log of user, AI and agent actions."
    />
  );
}
