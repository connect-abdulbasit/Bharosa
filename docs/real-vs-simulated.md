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
