# e2e/: end-to-end tests and demo

**Owner:** Hadi. **Depends on:** the running stack (frontend, backend, mocks) via public interfaces and `/contracts`. **Depended on by:** nobody.
Read the root `CLAUDE.md` first.

## Scenarios (see README.md)
1. **Happy path**: citizen claim -> verified -> auto/ask_more -> officer approves payment.
2. **Misspelled name**: Mohammad vs Muhammad / messy spelling still matches (or goes to a human).
3. **Identity service down**: chaos `error_500`/`timeout` -> case goes `with_officer` with notes, no 500 to the user.
4. **Consent withdrawn**: withdraw `payments`; the next claim makes no ledger call and asks again.
5. **Rule changed mid-claim**: new rule version published; existing decision keeps its version, next decision uses the new one.

## Rules
- Use only public interfaces (HTTP API, UI). Do not import backend internals.
- Reset chaos (`POST /chaos/reset`) before and after every scenario.
- Assert behaviour: statuses, audit entries, `simulated: true`, rule version stored.

## Tasks
- [x] The five scenarios + chaos, RBAC and services checks (pytest + httpx). TODO(Hadi): Playwright for key UI flows (only if time allows).
- [ ] TODO(Hadi): `docs/demo-script.md` rehearsal, seed/reset script for demo data.
- [ ] TODO(Hadi): wire into CI once the stack is stable.

## Run / test
See `e2e/README.md` (Run). Needs the backend running with `DEMO_MODE=1` against the real mocks.
