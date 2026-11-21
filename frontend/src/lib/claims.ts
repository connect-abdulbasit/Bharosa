"use client";
// Claim agent client: POST /claims answers 202 and runs in the background; poll /claims/{id}/progress until it settles,
// then read the full result. In fixtures mode POST /claims returns the finished result at once.
import { api } from "./api";
import { isLite } from "./lite";
import type { ClaimProgress, ClaimResponse } from "./types";

export type ClaimSubmit = { transcript?: string; document_id?: string | null; on_behalf_of?: string | null; intent?: "claim" | "payment_check"; month?: string };

type Accepted = ClaimResponse & { current_step?: string; finished?: boolean; progress_url?: string };

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function submitClaim(
  body: ClaimSubmit,
  token: string | null | undefined,
  onProgress?: (p: ClaimProgress) => void,
): Promise<ClaimResponse> {
  const first = await api<Accepted>("POST", "/claims", { body, token });
  if (!first.progress_url) return first; // fixtures mode or an already finished claim
  return await followClaim(first.claim_id, token, onProgress);
}

/** Poll until the background job is no longer active (finished OR paused with an officer note), then load the result. */
export async function followClaim(claimId: string, token: string | null | undefined, onProgress?: (p: ClaimProgress) => void): Promise<ClaimResponse> {
  const started = Date.now();
  for (;;) {
    if (typeof document !== "undefined" && document.hidden) {
      await wait(3000); // tab in the background: do not spend data
      continue;
    }
    const p = await api<ClaimProgress>("GET", `/claims/${claimId}/progress`, { token });
    onProgress?.(p);
    if (!p.active) break;
    if (Date.now() - started > 90_000) break; // never spin forever on weak signal: show what we have
    await wait(isLite() ? 2500 : p.steps_done === 0 ? 700 : 1000);
  }
  return await api<ClaimResponse>("GET", `/claims/${claimId}`, { token });
}
