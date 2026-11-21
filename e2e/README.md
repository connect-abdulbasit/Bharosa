# End-to-end scenarios

Implemented in `test_scenarios.py` (pytest + httpx, public HTTP only). Tests skip cleanly when the stack is not running.

| # | Scenario | Setup | Expected behaviour |
|---|---|---|---|
| 1 | Happy path | Seed person `0000042101002` | Verified, decision stored with rule version, payment still needs officer approval, audit entries for every step |
| 2 | Misspelled name | Claim as "Mohammad Aslam" vs record "Muhammad Aslam" | Match with variant, lower confidence noted; wrong/uncertain match -> `send_to_human`, never silent approve |
| 3 | Identity service down | `POST /chaos {"error_500": true}` | Case `with_officer` with notes; user sees a calm message, no 500 |
| 4 | Consent withdrawn | Withdraw `payments` consent mid-flow | No ledger call afterwards; audit shows withdrawal; user asked again |
| 5 | Rule changed mid-claim | Admin publishes new rule version during a claim | Old decision keeps its version; new decisions use the new one; both visible in audit |

## Extra checks
| # | Test | What it proves |
|---|---|---|
| 3b | identity failure x `error_500`, `timeout`, `missing_record` | every failure style ends `with_officer`, then resumes |
| 6 | `duplicate_payment` chaos on a payment check | a normally auto-closed case goes to a human with the `duplicate_payment` flag |
| 7 | RBAC | citizen/auditor cannot approve (403), no or bad token (401), citizen cannot read the audit log |
| 8 | notifications (services) | default-deny, sent after consent, blocked again after withdrawal, 401 without the service key |
| 10 | Digital Twin | a loosening rule is flagged for review before publishing, a tightening one only adds workload, and nothing is published |
| 9 | webhooks (services) | signed delivery verifies; one changed byte breaks the signature |

Scenarios 1 and 4 use the mocks' `GET /calls` counter to prove a call was made once (`POST /payments/disburse`) or **not** made (`GET /ledger/<cnic>` after consent withdrawal).

## Run
```
# 1. mocks (:8001), 2. backend with MOCKS_URL pointing at them and DEMO_MODE=1, 3. optional: services
cd mocks && PYTHONPATH=.. python -m uvicorn app.main:app --port 8001
cd backend && DEMO_MODE=1 MOCKS_URL=http://localhost:8001 PYTHONPATH=..:../ai python -m uvicorn app.main:app --port 8000   # Windows: use ; in PYTHONPATH
WEBHOOKS_ALLOW_LOCAL=1 PYTHONPATH=. python -m uvicorn services.main:app --port 8002      # from the repo root
# then, from the repo root:
PYTHONPATH=.:e2e python -m pytest e2e -v          # Windows: PYTHONPATH=".;e2e"
```
Env: `BASE`, `MOCKS_URL`, `SERVICES_URL`, `SERVICES_API_KEY`. Each test starts from a reset (`POST /reset` on the mocks, `POST /admin/demo/reset` on the backend) and the run ends reset.
