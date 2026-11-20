// API layer. NEXT_PUBLIC_API_MODE=fixtures (default) serves contract fixtures with NO backend needed.
// NEXT_PUBLIC_API_MODE=live calls the platform API at NEXT_PUBLIC_API_URL.
// Fixtures are copied from /contracts by `npm run sync-contracts`.
import fx_apikeys from "@/fixtures/apikeys.json";
import fx_audit_list from "@/fixtures/audit_list.json";
import fx_auth_login from "@/fixtures/auth_login.json";
import fx_case_assign from "@/fixtures/case_assign.json";
import fx_case_close from "@/fixtures/case_close.json";
import fx_case_create from "@/fixtures/case_create.json";
import fx_case_decide from "@/fixtures/case_decide.json";
import fx_case_detail from "@/fixtures/case_detail.json";
import fx_case_escalate from "@/fixtures/case_escalate.json";
import fx_cases_list from "@/fixtures/cases_list.json";
import fx_claim_create from "@/fixtures/claim_create.json";
import fx_consent_list from "@/fixtures/consent_list.json";
import fx_consent_withdraw from "@/fixtures/consent_withdraw.json";
import fx_document_upload from "@/fixtures/document_upload.json";
import fx_eval from "@/fixtures/eval.json";
import fx_helper_families from "@/fixtures/helper_families.json";
import fx_me from "@/fixtures/me.json";
import fx_message_check from "@/fixtures/message_check.json";
import fx_queue from "@/fixtures/queue.json";
import fx_rule_versions from "@/fixtures/rule_versions.json";
import fx_rules_list from "@/fixtures/rules_list.json";
// Frontend-only fixtures (not in /contracts yet; see frontend/CLAUDE.md).
import fx_users from "@/fixtures/local/users.json";
import fx_twin from "@/fixtures/local/twin_proposals.json";

export type ApiMode = "fixtures" | "live";
export const API_MODE: ApiMode = process.env.NEXT_PUBLIC_API_MODE === "live" ? "live" : "fixtures";
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Route = { method: string; pattern: RegExp; data: unknown };

const ROUTES: Route[] = [
  { method: "GET", pattern: new RegExp("^/users$"), data: fx_users },
  { method: "GET", pattern: new RegExp("^/twin/proposals$"), data: fx_twin },
  { method: "POST", pattern: new RegExp("^/auth/login$"), data: fx_auth_login },
  { method: "GET", pattern: new RegExp("^/me$"), data: fx_me },
  { method: "GET", pattern: new RegExp("^/cases$"), data: fx_cases_list },
  { method: "POST", pattern: new RegExp("^/cases$"), data: fx_case_create },
  { method: "GET", pattern: new RegExp("^/cases/[^/]+$"), data: fx_case_detail },
  { method: "POST", pattern: new RegExp("^/cases/[^/]+/assign$"), data: fx_case_assign },
  { method: "POST", pattern: new RegExp("^/cases/[^/]+/escalate$"), data: fx_case_escalate },
  { method: "POST", pattern: new RegExp("^/cases/[^/]+/decide$"), data: fx_case_decide },
  { method: "POST", pattern: new RegExp("^/cases/[^/]+/close$"), data: fx_case_close },
  { method: "POST", pattern: new RegExp("^/claims$"), data: fx_claim_create },
  { method: "POST", pattern: new RegExp("^/messages/check$"), data: fx_message_check },
  { method: "POST", pattern: new RegExp("^/documents$"), data: fx_document_upload },
  { method: "GET", pattern: new RegExp("^/rules$"), data: fx_rules_list },
  { method: "GET", pattern: new RegExp("^/rules/[^/]+/versions$"), data: fx_rule_versions },
  { method: "GET", pattern: new RegExp("^/consent$"), data: fx_consent_list },
  { method: "POST", pattern: new RegExp("^/consent/[^/]+/withdraw$"), data: fx_consent_withdraw },
  { method: "GET", pattern: new RegExp("^/audit$"), data: fx_audit_list },
  { method: "GET", pattern: new RegExp("^/queue$"), data: fx_queue },
  { method: "GET", pattern: new RegExp("^/helper/families$"), data: fx_helper_families },
  { method: "GET", pattern: new RegExp("^/apikeys$"), data: fx_apikeys },
  { method: "GET", pattern: new RegExp("^/eval$"), data: fx_eval },
];

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T = unknown>(
  method: "GET" | "POST",
  path: string,
  opts: { body?: unknown; token?: string | null } = {},
): Promise<T> {
  if (API_MODE === "fixtures") {
    const route = ROUTES.find((r) => r.method === method && r.pattern.test(path));
    if (!route) throw new ApiError(404, `No fixture for ${method} ${path}`);
    return structuredClone(route.data) as T;
  }
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(opts.token ? { Authorization: `Bearer ${opts.token}` } : {}),
    },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return (await res.json()) as T;
}
