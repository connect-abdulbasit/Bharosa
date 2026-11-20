// Shared enums. Keep in sync with enums.py (additive changes only).

export const Role = {
  citizen: "citizen",
  helper: "helper",
  officer: "officer",
  admin: "admin",
  auditor: "auditor",
} as const;
export type Role = (typeof Role)[keyof typeof Role];

export const CaseStatus = {
  draft: "draft",
  submitted: "submitted",
  needs_more_proof: "needs_more_proof",
  with_officer: "with_officer",
  approved: "approved",
  rejected: "rejected",
  closed: "closed",
} as const;
export type CaseStatus = (typeof CaseStatus)[keyof typeof CaseStatus];

export const DecisionAction = {
  auto_handle: "auto_handle",
  ask_more: "ask_more",
  send_to_human: "send_to_human",
} as const;
export type DecisionAction = (typeof DecisionAction)[keyof typeof DecisionAction];

export const MessageLabel = {
  scam: "scam",
  genuine: "genuine",
  unsure: "unsure",
} as const;
export type MessageLabel = (typeof MessageLabel)[keyof typeof MessageLabel];

export const ConsentScope = {
  identity: "identity",
  payments: "payments",
  complaints: "complaints",
  notifications: "notifications",
} as const;
export type ConsentScope = (typeof ConsentScope)[keyof typeof ConsentScope];
