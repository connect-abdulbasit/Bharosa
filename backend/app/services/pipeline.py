"""Claim agent pipeline. TODO(Basit).

Ordered steps (each saved to pipeline_steps so a failed run RESUMES, not restarts):
  1. consent_check    -> services.consent.require_consent (identity, payments)
  2. extract_claim    -> bharosa_ai.extract_claim
  3. read_document    -> bharosa_ai.read_document (if a photo exists; ask retake if blurry)
  4. identity_lookup  -> mocks_client.identity + bharosa_ai.match_person
  5. ledger_lookup    -> mocks_client.ledger (detect short/duplicate payment -> red flags)
  6. decide           -> bharosa_ai.decide with services.rules.get_active_rule()
  7. explain          -> bharosa_ai.explain (ur + en)
  8. persist + audit  -> every step calls services.audit.log(actor_type="agent"/"ai")

Rules: any mock failure -> case goes to `with_officer` with notes. Payment steps ALWAYS need officer approval.
"""
STEPS = [
    "consent_check", "extract_claim", "read_document", "identity_lookup",
    "ledger_lookup", "decide", "explain", "persist",
]


def run_claim_pipeline(*args, **kwargs):
    raise NotImplementedError("TODO(Basit): implement claim pipeline")
