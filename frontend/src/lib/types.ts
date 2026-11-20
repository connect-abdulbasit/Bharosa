// Hand-written minimal response types, mirroring contracts/schemas.py. Keep additive.
import type { CaseStatus, MessageLabel, Role } from "./enums";

export type Session = { token: string; role: Role; userId: string; name: string; username: string };

export type CaseNote = { author: string; text: string; created_at: string };
export type Decision = {
  action: string;
  confidence: number;
  reasons: string[];
  trace: Record<string, unknown>;
  rule_version: number;
  requires_officer_approval: boolean;
  model_version: string;
};
export type CaseDetail = {
  id: string;
  citizen_name: string;
  status: CaseStatus;
  claim_type: string;
  amount_claimed_pkr: number;
  risk_score: number;
  confidence: number;
  assigned_to: string | null;
  created_at: string;
  updated_at: string;
  cnic_masked: string;
  programme: string;
  notes: CaseNote[];
  decision: Decision | null;
  explanation_ur: string | null;
  explanation_en: string | null;
  pipeline_steps: { step: string; status: string; detail: string }[];
  rule_version: number | null;
};
export type MessageCheck = {
  label: MessageLabel;
  confidence: number;
  reasons: string[];
  official_sender: boolean;
  explanation_ur: string;
  explanation_en: string;
  model_version: string;
};
export type ClaimResponse = {
  claim_id: string;
  case_id: string;
  status: CaseStatus;
  draft: Record<string, unknown>;
  decision: Decision;
  explanation_ur: string;
  explanation_en: string;
};
export type Family = {
  family_id: string;
  head_name: string;
  case_count: number;
  open_cases: number;
  last_action: string;
  consent_on_file: boolean;
};
export type ConsentRecord = {
  id: string;
  scope: string;
  granted: boolean;
  shared_with: string[];
  purpose: string;
};
export type QueueItem = {
  case_id: string;
  citizen_name: string;
  risk_score: number;
  confidence: number;
  recommended_action: string;
  reasons: string[];
  waiting_since: string;
};
export type UserRow = {
  user_id: string;
  username: string;
  display_name: string;
  role: Role;
  active: boolean;
  last_login: string;
};
export type TwinProposal = {
  id: string;
  title: string;
  description: string;
  would_change: number;
  breakdown: Record<string, number>;
  estimated_cost_delta: number;
  examples: { case_id: string; citizen_name: string; old: string; new: string }[];
};
