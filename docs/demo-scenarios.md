# Demo scenarios (backend)

Eight named scenarios, seeded so each one **reliably reaches a different outcome even with the stub AI**. The data (people, identity records, ledger entries, `agent-099`, sender codes, and each scenario's expected result) lives in one shared file: [`contracts/fixtures/demo_people.json`](../contracts/fixtures/demo_people.json).
All people, ID numbers (`00000…`), amounts and services are **fake / simulated**.

## Before you start
```bash
docker compose up --build                           # real mocks by default (they serve the same people: contracts/fixtures/demo_people.json)
make demo-scenarios                                 # resets, then runs all seven over HTTP and prints each outcome
# also works with the built-in fake mocks (BACKEND_MOCKS_URL= docker compose up) and with AI_MODE=real (default AI period 2026-10)
```
- **Reset any time**: `POST /admin/demo/reset` (admin) or `make demo-reset`. It wipes cases, claims, decisions, jobs, ID photos, checked messages and consent changes, restores the seeded users, and re-seeds. **Rules and their history are kept** unless you pass `{"include_rules": true}` (`make demo-reset ARGS=--rules`). The append-only audit log is never wiped; the reset itself is audited (`demo.reset`).
- All scenario citizens use the demo citizen password `citizen-demo-123` and are linked to the helper (`helper` / `helper-demo-123`), who can file for them with `on_behalf_of` (user ids `u-demo-1` … `u-demo-7`).
- Officer: `officer` / `officer-demo-123`. Admin: `admin` / `admin-demo-123`.
- Claim text used below: **missing** = `mujhe is mahine ke paisay nahi mile`, **short** = `mujhe paisay kam mile hain`.

> **Why most outcomes are "needs more proof" with the stub AI.** The stub claim reader always hears the name "Mohammad Aslam" at confidence **0.81**, which is below the 0.90 auto-handle threshold, so the AI can never fully approve a *claim*, and any payment needs an officer anyway. Scenario 7 is different on purpose: a **payment check** is a structured question (a button, no speech), so there is nothing uncertain to read, and the official ledger answers it. With `AI_MODE=real` the AI decides on real evidence; the scenario data still exercises the same safeguards.

## At a glance
| # | Scenario | Login | AI / pipeline result | Status | Then |
|---|---|---|---|---|---|
| 1 | Clean approval | `s1-clean` | ask_more (confidence 0.81) | `needs_more_proof` | officer approves, **PKR 12000 paid once** |
| 2 | Misspelled name | `s2-spelling` | ask_more, name matched as a spelling variant | `needs_more_proof` | asks for more proof |
| 3 | Short payment by a bad agent | `s3-shortpay` | send_to_human, red flag `short_payment` | `with_officer` | officer tops up PKR 4000 |
| 4 | Duplicate claim, same month | `s4-duplicate` | send_to_human, flag `duplicate_claim` | `with_officer` | points at `case-demo-4` |
| 5 | Consent withdrawn | `s5-consent` | paused at `ledger_lookup`, blocked + logged | `with_officer` | grant again, **resume** completes |
| 6 | Identity service down | `s6-idown` | paused at `identity_lookup` | `with_officer` | service back, **resume** completes |
| 7 | Auto-handled payment check | `s7-autohandle` | **auto_handle** (confidence 0.95), no red flags | `closed` | nothing owed, **no payment, no officer** |
| 8 | **Live demo citizen** | `demo-live` | ask_more (stub 0.81 / real offline 0.65) | `needs_more_proof` | officer review; for use in front of judges |

## 1. Clean approval — "Rukhsana Bibi"
**Shows:** a clean claim is verified end to end, a payment is approved by a person, and it is paid exactly once.
1. Log in as `s1-clean`. `POST /claims` `{"transcript": "<missing>"}` → **202** at once (`case_id`, `current_step`). Poll `GET /claims/{id}/progress` until `active` is false.
2. Result: 8 of 8 steps done, **no red flags**, shortfall PKR 12000, AI `ask_more`, status `needs_more_proof`.
3. Log in as `officer`. `POST /cases/{case_id}/decide` `{"action": "approve", "reason": "Clean claim, ledger confirms nothing was paid"}` → `approved`, payment reference `PAY-FAKE-…`.
4. Repeat the same approval → **409**. Only one payment exists (`GET /audit?action=payment.release`).

## 2. Misspelled name (ask more) — "Muhammed Aslam"
**Shows:** messy names do not cause a silent guess or an automatic rejection.
1. Log in as `s2-spelling`, file the **missing** claim.
2. The AI heard "Mohammad Aslam"; the identity record says "Muhammad Aslam". The `match_person` step reads **"name matched (score 1.0)"**: a spelling variant, no red flags.
3. Result: `ask_more` → `needs_more_proof`, with a list of what is needed.

## 3. Short payment by a bad agent (officer) — "Shabana Kausar"
**Shows:** a short payment is a red flag; a human decides; the paying agent is named.
1. Log in as `s3-shortpay`, file the **short** claim.
2. The ledger shows PKR 8000 of 12000, paid by `agent-099`. Result: `send_to_human`, trace `flags: ["short_payment"]`, reason *"Short payment: received PKR 8000 of 12000, paid by agent-099."*
3. `officer`: `GET /queue` shows it with the short AI reason. Approve with a reason → PKR **4000** top-up, paid once.

## 4. Duplicate claim, same month (officer) — "Naseem Akhtar"
**Shows:** one open claim per citizen per month; the second is flagged, not paid.
1. `case-demo-4` is already open for 2026-10 (seeded).
2. Log in as `s4-duplicate`, file the **missing** claim.
3. Result: `with_officer`, flag `duplicate_claim`, reason *"Duplicate claim: … already has an open claim for 2026-10 (case case-demo-4)."* The pipeline stops at the first step (no lookups are made).

## 5. Consent withdrawn (blocked and logged) — "Hameeda Begum"
**Shows:** consent is checked before every external call; blocked attempts are on record; the work resumes after consent returns.
1. Her **payments** consent is seeded as *withdrawn*.
2. Log in as `s5-consent`, file the **missing** claim. Identity is looked up (identity consent is granted); `ledger_lookup` is **blocked**: status `with_officer`, note *"Consent for 'payments' is withdrawn…"*.
3. Admin: `GET /audit?action=consent.blocked&actor_id=u-demo-5` → one entry (scope `payments`).
4. As `s5-consent`: `POST /consent` `{"scope": "payments"}`, then `POST /claims/{id}/resume` → 8 of 8 steps done, `needs_more_proof`.

## 6. Identity service down (paused, then resume) — "Parveen Akhtar"
**Shows:** a failing service never becomes an error page: the case goes to a person with a note, and resumes.
1. Admin: `POST /admin/demo/chaos` `{"identity_down": true}` (the fake mocks' outage switch; with real mocks use their Chaos Panel).
2. As `s6-idown`, file the **missing** claim → **200-class response, no 500**: `with_officer`, `identity_lookup` failed *"…service unavailable (simulated outage)"*, case note "Pipeline paused at step 'identity_lookup'…".
3. Admin: `POST /admin/demo/chaos` `{"identity_down": false}`. As `s6-idown`: `POST /claims/{id}/resume` → completes; the finished steps (e.g. `extract_claim`) are **not** redone.

## 7. Auto-handled: payment check, nothing owed — "Gulshan Bibi"
**Shows:** the system answers by itself when (and only when) the answer is certain; nothing is paid; the reasoning is on record.
1. Log in as `s7-autohandle`. `POST /claims` `{"intent": "payment_check", "month": "2026-10"}` (a question, **not** a claim: no speech, nothing claimed). → **202**, poll `/progress`.
2. The agent builds the request from the account (confidence 1.0, `model_version: structured-input`), looks up identity and the ledger (consent first), and `match_person` matches the account name. The ledger shows **PKR 12000 paid on 2026-10-05 by agent-017**: no shortfall, no red flags.
3. The AI's `decide` returns **`auto_handle`** (confidence 0.95 ≥ 0.90, no red flags). No payment is needed, so the case is **`closed`** with the explanation: *"Good news: your payment of PKR 12000 for 2026-10 was paid on 2026-10-05 (agent agent-017). Nothing more is owed… If you did not receive the money, tell your helper."* (Urdu too; an SMS is sent if she consented.)
4. Nothing is paid: `GET /audit?entity=case&entity_id=<case>&action=payment.release` is empty. No officer was involved.

**Why a payment check and not "auto-close a claim whose ledger says paid"?** A citizen who says "I was not paid" while the ledger says "paid" is the classic bad-agent case, so the system keeps sending **claims** like that to an officer (`claim_contradicts_ledger`). A *question* is different: nothing is claimed, and only a **confirmed full payment** is auto-handled. Anything else is routed, never guessed: no payment on record -> asks her whether to file a claim (`needs_more_proof`); a short or duplicate payment -> officer (`with_officer`). Checks never create a payment, never count as an "open claim" for the duplicate rule, and obey consent and the live rule (a stricter rule stops auto-handling).

## Also seeded for the demo
- **60 scam checks** over fictional areas (Noorabad, Sahil Colony, Bagh-e-Zubaida, Mehran Town North, Kausar Basti, plus two tiny groups) for `GET /scam-map`. Areas and reasons with fewer than 3 reports appear only as `other`.
- Digital Twin: after running scenarios, `POST /rules/rule-stipend-short-payment/simulate` (admin) with e.g. `{"auto_handle_min": 0.99, "ask_more_min": 0.6}` shows how many past decisions would change. It saves nothing.

## Shared data and real mocks
All scenario data is in [`contracts/fixtures/demo_people.json`](../contracts/fixtures/demo_people.json) (validated by `contracts.schemas.DemoPeople`; it also lists each scenario's expected result, and a backend test checks they hold). The backend's built-in fake mocks read it. With the real `/mocks` service the scenario people get "record not found" (a handy extra failure demo) until `/mocks` loads the same file. TODO(Hadi).

## Login limit while demoing
`/auth/login` is limited per IP. `LOGIN_RATE_LIMIT` unset means **30/minute while `DEMO_MODE=1`** (so the runner can log in as nine different users without waiting) and **5/minute** once `DEMO_MODE=0`. Set `LOGIN_RATE_LIMIT` to override either.


## Verified outcomes (final integration run, 22 Nov)
Real mocks (docker compose), all eight PASS with the stub AI and with `AI_MODE=real` **without an LLM key** (offline parser, reason `llm_unavailable`, confidence 0.05 lower). With real AI the citizen says their name first (the real extractor refuses a claim with no name instead of guessing).

| # | Stub AI | Real AI, no key (offline) |
|---|---|---|
| 1 | ask_more 0.81 -> officer approves, PKR 12000 once | ask_more 0.65 -> same |
| 2 | ask_more 0.81, name variant matched | ask_more 0.65, same |
| 3 | send_to_human, `short_payment`, PKR 4000 | send_to_human 0.55, same flag and top-up |
| 4 | send_to_human, `duplicate_claim` | same |
| 5 | blocked at `ledger_lookup`, resume completes | same |
| 6 | paused at `identity_lookup` (mocks `error_500`), resume completes | same |
| 7 | auto_handle 0.95, closed | auto_handle 0.97, closed |
| 8 | ask_more 0.81, all 8 steps, no duplicate flag | ask_more 0.65, same |

## 8. Live demo citizen (`demo-live`) — "Samina Parveen"
**Shows:** a clean live run in front of judges. This account has **no open October claim**, a clean identity record and an empty ledger, and PIN `1234` (fake) for helper consent grants, so it never hits the duplicate rule of scenario 4.
1. Log in as `demo-live` (`citizen-demo-123`), Claim: say or type "mera naam Samina Parveen hai. Mujhe is mahine ke paisay nahi mile" (the real extractor needs the name; the stub ignores it).
2. Result: all 8 steps done, no red flags, shortfall PKR 12000, `needs_more_proof`. The citizen home then shows an Urdu + English message under **My messages**.
3. Run `make demo-reset` (or Admin > Chaos Panel > Reset demo data) between takes: the next claim is again a first claim. The scenario 4 citizen (`s4-duplicate`) stays as the duplicate demo.
