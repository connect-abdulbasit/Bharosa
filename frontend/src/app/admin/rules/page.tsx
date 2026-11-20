import { PageShell } from "@/components/PageShell";

export default function AdminRulesPage() {
  return (
    <PageShell
      roles={["admin"]}
      title="Rule editor"
      urdu="اصول ایڈیٹر"
      note="TODO(Hani): versioned thresholds and red flags, no redeploy."
    />
  );
}
