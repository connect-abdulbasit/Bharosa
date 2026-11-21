# Real vs simulated

Bharosa is a **prototype**. It is not an official service and is not affiliated with any government body.

| Area | Status | Notes |
|---|---|---|
| Programme ("Sahara Relief Programme", short code 9090) | **Fictional** | No real programme names or logos |
| Identity (NADRA-like) | **Simulated** | `/mocks` `GET /identity/{cnic}`, 5 seed people |
| Payments (Raast-like) | **Simulated** | `/mocks` `GET /ledger/{cnic}`; no money moves |
| Complaints | **Simulated** | `POST /complaints` returns a fake ticket |
| SMS / notifications | **Simulated** | `POST /notify`; nothing is sent |
| CNICs and people | **Fake** | 13 digits starting `00000`; invented names |
| Auth, RBAC, JWT, audit log, consent, rules | **Real code** | Genuinely enforced server-side |
| AI models | **Real code** (when `AI_MODE=real`), stubs otherwise | Trained/evaluated on synthetic data only |
| Database | **Real** Postgres + Alembic | Contains only synthetic data |
| Deployment | **Real** | Hosted prototype |

Every mock response carries `"simulated": true`; the UI shows a "PROTOTYPE - simulated data" banner on every page.


## Backend (what is real inside the platform API)
| Piece | Status | Notes |
|---|---|---|
| Auth, RBAC, row-level access, audit log | **Real** | bcrypt + JWT, server-side roles, append-only audit (also enforced by a Postgres trigger) |
| Consent (grant / withdraw / correct, helper PIN) | **Real** | checked before every identity / payment / complaint call; blocked attempts are logged |
| Claim agent, background jobs, resume | **Real** | database job table, in-process worker, steps saved and resumable |
| Rules (versioned json-logic, validation) | **Real** | new version active immediately, old decisions keep their version |
| Public API keys, rate limiting, error format | **Real** | hashed keys, scopes, per-key limits |
| Payments | **Simulated money, real safety logic** | no money moves; the idempotency-key logic (one payment per decision) is real. The mock `/payments/disburse` is TODO(Hadi); until then the backend falls back to a `/complaints` ticket |
| Identity, ledger, SMS, complaints | **Simulated** | `/mocks`, or the in-process fake client when `MOCKS_URL` is empty/unreachable |
| AI (`AI_MODE=stub`) | **Stub by default** | fixed realistic outputs; the stub claim reader always hears "Mohammad Aslam" |
| ID photos | **Real files** (synthetic data only) | resized and stored in Postgres (`documents_blob`); local disk is only an optional cache |
| Demo scenarios, Scam Map data | **Seeded fake data** | 6 scenario citizens in the backend's fake mocks, 60 fake scam checks; reset with `POST /admin/demo/reset` |
| Webhooks | **Not yet** | `events.emit` records events locally; delivery is TODO(Hadi) |
