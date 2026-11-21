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
import fx_helper_families from "@/fixtures/helper_families.json";
import fx_me from "@/fixtures/me.json";
import fx_message_check from "@/fixtures/message_check.json";
import fx_notifications from "@/fixtures/notifications.json";
import fx_queue from "@/fixtures/queue.json";
import fx_rule_versions from "@/fixtures/rule_versions.json";
import fx_rules_list from "@/fixtures/rules_list.json";
import fx_scam_map from "@/fixtures/scam_map.json";
import fx_eval_live from "@/fixtures/eval_live.json";
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
  { method: "GET", pattern: new RegExp("^/me/notifications$"), data: fx_notifications },
  { method: "GET", pattern: new RegExp("^/apikeys$"), data: fx_apikeys },
  { method: "GET", pattern: new RegExp("^/eval$"), data: fx_eval_live },
  { method: "POST", pattern: new RegExp("^/consent$"), data: fx_consent_list.items[0] },
  { method: "POST", pattern: new RegExp("^/consent/[^/]+/correct$"), data: fx_consent_list.items[0] },
  { method: "POST", pattern: new RegExp("^/apikeys$"), data: { ...fx_apikeys.items[0], key: "bhr_live_FIXTURE_ONLY_NOT_A_REAL_KEY" } },
  { method: "POST", pattern: new RegExp("^/apikeys/[^/]+/revoke$"), data: { ...fx_apikeys.items[0], revoked: true } },
  { method: "POST", pattern: new RegExp("^/rules/[^/]+/versions$"), data: fx_rule_versions.versions[0] },
  {
    method: "POST",
    pattern: new RegExp("^/rules/[^/]+/simulate$"),
    data: {
      rule_id: "rule-stipend-short-payment",
      current_version: 1,
      proposed: { auto_handle_min: 0.95, ask_more_min: 0.6 },
      total_cases: 12,
      simulated_cases: 9,
      skipped_no_inputs: 3,
      would_change: 3,
      by_transition: { "auto_handle -> ask_more": 2, "ask_more -> send_to_human": 1 },
      examples: [
        { case_id: "case-0003", old_action: "auto_handle", new_action: "ask_more" },
        { case_id: "case-0002", old_action: "ask_more", new_action: "send_to_human" },
      ],
    },
  },
  { method: "GET", pattern: new RegExp("^/health$"), data: { status: "ok", database: "ok", mocks: { mode: "fake", reachable: true }, ai_mode: "stub", worker: { mode: "thread", alive: true }, version: "fixtures", environment: "fixtures", simulated: true } },
  { method: "GET", pattern: new RegExp("^/scam-map$"), data: fx_scam_map },
  { method: "GET", pattern: new RegExp("^/admin/demo/chaos$"), data: { identity_down: false, ledger_down: false, payments_down: false, mocks: { mode: "fixtures", reachable: false } } },
  { method: "POST", pattern: new RegExp("^/admin/demo/chaos$"), data: { identity_down: false, ledger_down: false, payments_down: false } },
  { method: "POST", pattern: new RegExp("^/admin/demo/reset$"), data: { ok: true } },
];

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
    public fields?: unknown,
    public requestId?: string,
  ) {
    super(message);
  }
}

/** Backend errors are always { error, message, request_id } (+ fields on 422). Never show raw JSON to a user. */
async function toApiError(res: Response): Promise<ApiError> {
  let message = `Request failed (${res.status})`;
  let code: string | undefined;
  let fields: unknown;
  let requestId: string | undefined;
  try {
    const j = (await res.json()) as { error?: string; message?: string; detail?: unknown; fields?: unknown; request_id?: string };
    code = j.error;
    fields = j.fields;
    requestId = j.request_id;
    if (typeof j.message === "string") message = j.message;
    else if (typeof j.detail === "string") message = j.detail;
  } catch {
    /* not json */
  }
  return new ApiError(res.status, message, code, fields, requestId);
}

type Opts = { body?: unknown; token?: string | null; signal?: AbortSignal };

// Conditional GETs: the backend sends ETags on polled endpoints (/queue, /cases/{id}, /claims/{id}/progress ...).
// We send If-None-Match and reuse the last body on 304, so a poll with no news costs almost no data on a weak signal.
// Keyed by token + path so one person's data is never served to another.
const etagCache = new Map<string, { etag: string; data: unknown }>();
const ETAG_LIMIT = 150;

export async function api<T = unknown>(method: "GET" | "POST", path: string, opts: Opts = {}): Promise<T> {
  if (API_MODE === "fixtures") {
    await new Promise((r) => setTimeout(r, 180)); // feel like a network so loading states are visible
    const route = ROUTES.find((r) => r.method === method && r.pattern.test(path.split("?")[0]));
    if (!route) throw new ApiError(404, `No fixture for ${method} ${path}`);
    return structuredClone(route.data) as T;
  }
  const cacheKey = `${opts.token ?? ""}|${path}`;
  const cached = method === "GET" ? etagCache.get(cacheKey) : undefined;
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      signal: opts.signal,
      headers: {
        ...(opts.body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(opts.token ? { Authorization: `Bearer ${opts.token}` } : {}),
        ...(cached ? { "If-None-Match": cached.etag } : {}),
      },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check your connection.", "network");
  }
  if (res.status === 304 && cached) return structuredClone(cached.data) as T;
  if (res.status === 401 && opts.token) onUnauthorized();
  if (!res.ok) throw await toApiError(res);
  const data = (await res.json()) as T;
  const etag = res.headers.get("ETag");
  if (method === "GET" && etag) {
    if (etagCache.size >= ETAG_LIMIT) etagCache.delete(etagCache.keys().next().value as string);
    etagCache.set(cacheKey, { etag, data: structuredClone(data) });
  }
  return data;
}

/** Multipart upload (ID photo). Fixtures mode returns the contract fixture. */
export async function apiUpload<T = unknown>(path: string, form: FormData, token?: string | null): Promise<T> {
  if (API_MODE === "fixtures") {
    await new Promise((r) => setTimeout(r, 400));
    const route = ROUTES.find((r) => r.method === "POST" && r.pattern.test(path));
    if (!route) throw new ApiError(404, `No fixture for POST ${path}`);
    return structuredClone(route.data) as T;
  }
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method: "POST", body: form, headers: token ? { Authorization: `Bearer ${token}` } : {} });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check your connection.", "network");
  }
  if (res.status === 401 && token) onUnauthorized();
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

/** Fetch a protected image (ID photo) and return an object URL. */
export async function apiImage(path: string, token?: string | null): Promise<string | null> {
  if (API_MODE === "fixtures") return null;
  try {
    const res = await fetch(path.startsWith("http") ? path : `${API_URL}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!res.ok) return null;
    return URL.createObjectURL(await res.blob());
  } catch {
    return null;
  }
}

function onUnauthorized() {
  etagCache.clear();
  // Token expired or revoked: drop the session so RoleGuard sends the person to /login.
  try {
    window.localStorage.removeItem("bharosa.session");
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new Event("bharosa:session"));
}

/** Human-friendly message for any thrown error (never a stack trace, never raw JSON). */
export function errorText(e: unknown, fallback = "Something went wrong. Please try again."): string {
  if (e instanceof ApiError) {
    if (e.status === 0) return "No connection. Your work is saved here: try again when signal is better.";
    if (e.status === 429) return "Too many tries. Please wait a minute and try again.";
    if (e.status >= 500) return "The service is having trouble. A person has been told; please try again later.";
    return e.message || fallback;
  }
  return fallback;
}
