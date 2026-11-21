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
  image_url?: string | null;
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
  pipeline_steps?: { step: string; status: string; detail?: string }[];
};
export type ClaimProgress = {
  claim_id: string;
  case_id: string;
  status: CaseStatus;
  current_step: string;
  finished: boolean;
  steps_done: number;
  steps_total: number;
  steps: Record<string, string>[];
  job?: string | null;
  active: boolean;
  failed?: Record<string, unknown> | null;
  stopped?: Record<string, unknown> | null;
};
export type DocumentResult = {
  document_id: string;
  fields: Record<string, string>;
  blur_score: number;
  format_ok: boolean;
  confidence: number;
  retake_needed: boolean;
  explanation_ur: string;
  explanation_en: string;
  model_version: string;
  image_url?: string | null;
};
export type CaseSummary = {
  id: string;
  citizen_name: string;
  status: CaseStatus;
  claim_type: string;
  amount_claimed_pkr: number;
  risk_score: number;
  confidence: number;
  assigned_to?: string | null;
  created_at: string;
  updated_at: string;
};
export type RuleSummary = { id: string; name: string; current_version: number; updated_at: string };
export type RuleVersion = {
  rule_id: string;
  version: number;
  name: string;
  auto_handle_min: number;
  ask_more_min: number;
  red_flags: string[];
  logic: Record<string, unknown>;
  created_by?: string | null;
  created_at?: string | null;
  note?: string | null;
};
export type RuleSimulation = {
  rule_id: string;
  current_version: number;
  proposed: Record<string, unknown>;
  total_cases: number;
  simulated_cases: number;
  skipped_no_inputs: number;
  would_change: number;
  by_transition: Record<string, number>;
  examples: { case_id: string; old_action: string; new_action: string }[];
};
export type AuditEntry = {
  id: string;
  timestamp: string;
  actor: string;
  actor_type: string;
  action: string;
  target: string;
  entity?: string | null;
  entity_id?: string | null;
  request_id?: string | null;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
};
export type ScamMap = {
  generated_at: string;
  window_days: number;
  min_group_size: number;
  total: number;
  by_area: { area: string; count: number }[];
  by_day: { day: string; count: number }[];
  by_reason: { reason: string; count: number }[];
};
export type ChaosLive = { identity_down: boolean; ledger_down: boolean; payments_down: boolean; mocks?: { mode?: string; reachable?: boolean; url?: string }; note?: string };
export type Family = {
  family_id: string;
  citizen_id?: string | null; // not returned by /helper/families yet: see familyCitizenId()
  head_name: string;
  case_count: number;
  open_cases: number;
  last_action: string;
  latest_case_status?: CaseStatus | null;
  consent_on_file: boolean;
};
export type ConsentRecord = {
  id: string;
  citizen_id?: string | null;
  scope: string;
  granted: boolean;
  granted_at?: string | null;
  withdrawn_at?: string | null;
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
  ai_reason?: string | null;
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

/**
 * Helpers act for a citizen by user id (`on_behalf_of` / `citizen_id`), but GET /helper/families does not return it yet.
 * Until the backend adds `citizen_id` to that response, fall back to the seeded convention fam-00N -> u-citizen-N.
 */
export function familyCitizenId(f: Pick<Family, "family_id" | "citizen_id">): string {
  if (f.citizen_id) return f.citizen_id;
  const n = /(\d+)$/.exec(f.family_id)?.[1];
  return n ? `u-citizen-${parseInt(n, 10)}` : f.family_id;
}

export type InAppMessage = { id: string; key: string; text_ur?: string | null; text_en?: string | null; at?: number | null; simulated?: boolean };
