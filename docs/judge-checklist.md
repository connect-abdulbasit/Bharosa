# "Try to break it": checklist for judges

Prototype with **simulated data**. Start: `docker compose up --build`, then the frontend (README, Quick start). Logins are in the README (username = role, fake passwords). API base `http://localhost:8000` (Swagger at `/docs`). Every item below works in the integrated system; where a command is shown you can paste it.

```bash
API=http://localhost:8000
tok() { curl -s $API/auth/login -H 'content-type: application/json' -d "{\"username\":\"$1\",\"password\":\"$2\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])'; }
CIT=$(tok citizen citizen-demo-123); OFF=$(tok officer officer-demo-123); ADM=$(tok admin admin-demo-123); AUD=$(tok auditor auditor-demo-123)
```

**Security (enforced on the server, not by hidden buttons)**
- [ ] Citizen calls an officer endpoint: `curl -s -o /dev/null -w "%{http_code}\n" $API/queue -H "Authorization: Bearer $CIT"` -> **403**.
- [ ] No token / tampered token on any endpoint -> **401**.
- [ ] A citizen asks for someone else's case: `$API/cases/case-0001` as `$CIT` -> **404** (not 403, so ids do not leak).
- [ ] Auditor tries to change something (`POST /cases`) -> **403**; auditor reads `/audit` -> user, AI and agent entries.
- [ ] Citizen opens `/audit` -> **403**. Open `/admin` in the browser as a citizen -> sent to login; the API still refuses.
- [ ] Use an API key outside its scope, on a private route, or hammer `/public/messages/check` -> **403 / 429** with `Retry-After`. Wrong passwords 31 times in a minute -> **429**.
- [ ] Try to update or delete the audit log in Postgres -> `ERROR: audit_log is append-only`.

**Uncertainty and bad data**
- [ ] Citizen > Claim: a blurry or unreadable ID photo -> told to **retake**, never guessed. (Samples: `ai/data/sample_id_specimen.jpg` is read by OCR, `sample_id_specimen_blurry.jpg` is sent for retake.)
- [ ] Say the problem with no name (real AI: `AI_MODE=real`) -> asked for the name, no invented claim. (Stub AI always hears one name; that is a stub.)
- [ ] No LLM key (`GET /health` shows `extract_claim: real_offline_fallback`): claims still work, with 0.05 lower confidence and the reason `llm_unavailable`.
- [ ] Spelling variant (demo user `s2-spelling`, "Muhammed Aslam") -> matched as a variant at lower confidence, `needs_more_proof`, never auto-approved.
- [ ] Citizen > Check: ambiguous SMS -> `unsure`; lookalike sender `9O9O` -> scam; official `9090` -> genuine.
- [ ] Low confidence screens say "we need a person to check", not a confident guess.

**Failure handling (Admin > Chaos Panel drives the real mocks)**
- [ ] Switch **Identity service down**, then file a claim as `demo-live` (or Helper > Gulshan Bibi > Send) -> the claim **pauses at the identity step**, case `with_officer`, officer note, calm message, no stack trace.
- [ ] Switch **Payment record down** instead -> identity still works and the claim **pauses at the payment-record step** (ledger only). The Chaos page says which switches are on and has **Reset all**.
- [ ] Switch it off, press **Try again** on the result screen -> the claim resumes where it stopped and finishes.
- [ ] **Payments rail down**: officer approves a shortfall -> **503**, nothing changed; switch off, approve again -> paid once.
- [ ] Duplicate click / retry on **Approve** -> second call **409**; `GET /audit?action=payment.release` shows **one** payment per case. The mocks' `POST /payments/disburse` with the same `Idempotency-Key` returns the same `payment_ref`.
- [ ] Any payment always needs an officer decision with a written reason (empty reason -> refused).

**Consent and control**
- [ ] Citizen > My data > **Take it back** (confirm) -> the next claim makes **no** ledger call and is blocked and logged: `GET /audit?action=consent.blocked`.
- [ ] Helper > a person whose consent is missing -> PIN `1234` needed (fake) to grant it; **Switch person** clears the screen.
- [ ] Correct a data item -> the change is in the audit log.

**Rules**
- [ ] Admin > Rules: change a threshold, add a reason, publish -> live at once, no restart; old decisions keep their version. A rule that auto-approves everything is refused (**422 Unsafe rule**).
- [ ] Admin > Digital Twin: run a stricter rule on past cases -> "N cases would change" before you publish; nothing is published.

**Live claim in front of you**
- [ ] Log in as `demo-live`, Claim with your own words and a photo (say your name: "mera naam Samina Parveen hai ...") -> `needs more proof`, no duplicate warning; the citizen home shows **My messages** in Urdu + English. `s4-duplicate` shows the duplicate rule instead.

**Weak signal and shared phone**
- [ ] `POST /claims` answers **202** at once; the screen shows live progress and survives a reload (answers saved on the phone).
- [ ] Turn on **data saver** (header): polling slows down; repeat polls answer 304 (ETag).

**Honesty**
- [ ] Every page shows "PROTOTYPE - simulated data"; every mock response has `"simulated": true` (`curl localhost:8001/identity/0000042101101`).
- [ ] Officer or Admin > Insights (`/eval`): errors and cost of wrong approvals vs wrong rejections, overrides of the AI, Scam Map (areas with fewer than 3 reports are hidden in "other").
- [ ] `make demo-scenarios` prints all 8 outcomes; `docs/demo-scenarios.md` explains each one.
