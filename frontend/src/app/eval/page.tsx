import { PageShell } from "@/components/PageShell";

export default function EvalPage() {
  return (
    <PageShell
      roles={["officer", "admin", "auditor"]}
      title="Evaluation"
      urdu="جائزہ"
      note="TODO(Hani): accuracy, confusion matrix, cost of wrong decisions from /eval."
    />
  );
}
