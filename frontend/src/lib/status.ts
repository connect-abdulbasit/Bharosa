// How each case status looks to people (English + Urdu + colour). Shared by citizen, helper and officer screens.
export type StatusTone = "ok" | "bad" | "warn" | "info" | "neutral" | "brand";

export const STATUS_LOOK: Record<string, { tone: StatusTone; en: string; ur: string }> = {
  draft: { tone: "neutral", en: "Draft", ur: "مسودہ" },
  submitted: { tone: "info", en: "Submitted", ur: "جمع ہو گیا" },
  needs_more_proof: { tone: "warn", en: "Needs more proof", ur: "مزید ثبوت چاہیے" },
  with_officer: { tone: "brand", en: "With an officer", ur: "افسر کے پاس" },
  approved: { tone: "ok", en: "Approved", ur: "منظور" },
  rejected: { tone: "bad", en: "Not approved", ur: "منظور نہیں" },
  closed: { tone: "neutral", en: "Closed", ur: "بند" },
};

export function statusLook(status: string | null | undefined) {
  return STATUS_LOOK[status ?? ""] ?? STATUS_LOOK.submitted;
}
