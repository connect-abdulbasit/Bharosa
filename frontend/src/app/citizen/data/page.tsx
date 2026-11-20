import { PageShell } from "@/components/PageShell";

export default function CitizenDataPage() {
  return (
    <PageShell
      roles={["citizen", "helper"]}
      title="My data & consent"
      urdu="میرا ڈیٹا اور رضامندی"
      note="TODO(Hani): see / share / withdraw / correct consent per scope."
    />
  );
}
