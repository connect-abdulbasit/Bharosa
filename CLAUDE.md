# Bharosa: instructions for AI coding agents

Read this first, then the `CLAUDE.md` of the folder you were asked to work in.

## What this is
- **Bharosa** (Urdu: "trust") is a trusted assistance layer between citizens and public services. It does NOT replace government systems.
- Built for **Coder's Cup 2026 AI Hackathon** (ACM NUCES, FAST-NUCES Karachi). Theme: "The Last Mile: AI on Public Rails" (identity like NADRA, payments like Raast).
- Build window closes **Sunday 22 Nov 2026, 6:00 PM PKT**. 48-hour hackathon: ship working behaviour, not scaffolding.
- **PROTOTYPE ONLY.** Fictional programme **"Sahara Relief Programme"**, fictional official short code **"9090"**. All identity, payment, complaint and SMS services are mocked.
- Personas: the **widow** (cannot read, weak signal), the **shopkeeper** (gets fake relief-payment SMS), the **community helper** (40 families on one shared phone).
- Roles: `citizen`, `helper`, `officer`, `admin`, `auditor`.
- Pillars: **Check** (scam messages), **Claim** (voice + photo, verified, decided), **Control** (consent).

**The one task:** "We help low-literacy women on a shared phone get a missing or short-paid relief stipend resolved, even though they can't read forms, have weak signal, and are targeted by scam messages and middlemen."

**Judging priorities:** judges score *behaviour, not claims*: how the system handles risk, mistakes, uncertainty, bad data and security. Prefer a small thing that fails safely over a big thing that fails silently. Security is enforced **server-side**.

## Folder ownership (only edit the folder you were asked to work in)
| Person | Folder(s) | Owns |
|---|---|---|
| Ali | `/ai` | Classifier, name matching, OCR, claim extraction, decide, explain, evaluation |
| Basit | `/backend` | FastAPI platform, DB + Alembic, auth/RBAC, cases, claim pipeline, rules, consent, audit, API keys, deploy |
| Hani | `/frontend` | Next.js PWA, all role screens, voice/read-aloud, saved progress, Helper Mode UI |
| Hadi | `/mocks`, `/services`, `/e2e` | Mock government services, synthetic data, Chaos Panel backend, notifications, webhooks, Digital Twin, end-to-end tests, demo |
| Everyone | `/contracts`, `/docs` | Shared contracts. **Changes are additive only** and announced to the team |

Rules: never edit another person's folder (open an issue or message them). `/contracts` changes: add, never rename/remove/repurpose; run `cd frontend && npm run sync-contracts` afterwards.

## Non-negotiables
1. **No real personal data, no real programme names, logos or CNICs.** CNICs are fake 13-digit numbers starting `00000`.
2. **Every AI output has `confidence` and `model_version`.**
3. **Never silently guess.** Uncertain -> `ask_more` or `send_to_human`.
4. **Every state change writes to the audit log** (user, AI and agent actions): `audit.log(actor, action, before, after)`.
5. **RBAC is enforced server-side** (`require_role`). The UI hiding a button is not security.
6. **Consent is checked before any mock call** (identity, payments, complaints, notifications).
7. **Mocks return `"simulated": true`** on every response, and the UI shows a "PROTOTYPE - simulated data" banner.
8. Any **payment step always needs officer approval**.
9. Mock/service failure never produces a raw 500 for the user: the case goes to a human with notes.

## Run and test
Python 3.9+ locally (3.11 in Docker). One venv for all Python folders.
```
make install      # create .venv, install ai, backend, mocks (+ dev deps)
make test         # runs ai, backend, mocks tests
make lint         # ruff
make dev          # mocks :8001 + backend :8000 locally
docker compose up --build   # postgres + backend + mocks
cd frontend && npm install && npm run sync-contracts && npm run dev   # :3000
```
Per-folder commands are in each folder's `CLAUDE.md`.

## Env flags
| Flag | Values | Meaning |
|---|---|---|
| `AI_MODE` | `stub` (default) / `real` | `stub`: `bharosa_ai` returns fixed realistic outputs (`stubs.py`). `real`: uses the implementations in `classify.py` etc. (unimplemented ones raise `NotImplementedError`). Switch is in `ai/bharosa_ai/__init__.py` |
| `MOCKS_URL` | URL or empty | Backend calls this for identity/ledger/etc. Empty -> `fake_mocks_client.py` |
| `NEXT_PUBLIC_API_MODE` | `fixtures` (default) / `live` | Frontend serves `contracts/fixtures` or calls the backend |
| `DATABASE_URL`, `JWT_SECRET`, `LLM_API_KEY` | | See `.env.example` |

## Commits
- Small commits. Message format `area: what changed`, e.g. `backend: add consent withdraw endpoint`.
- **Do NOT add `Co-Authored-By` or any AI attribution trailer** to commit messages.
- Stay in your folder; one area per commit.

## Glossary
- **CNIC**: Computerised National Identity Card, 13-digit number. NADRA issues the real ones; ours are fake (`00000...`).
- **NADRA**: Pakistan's national identity authority. Here: simulated by `GET /identity/{cnic}`.
- **Raast**: Pakistan's instant payment rail. Here: simulated by `GET /ledger/{cnic}`.
- **Helper**: community helper who acts, with consent, for many families on one shared phone (Helper Mode).
- **Officer**: government-side reviewer who approves any payment and handles `send_to_human` cases.
- **Rule version**: immutable, versioned decision rule (thresholds + red flags as json-logic); every decision stores the version used.
- **Consent scope**: `identity`, `payments`, `complaints`, `notifications`; each can be seen, shared, withdrawn, corrected.
- **Chaos switch**: in-memory failure toggle in `/mocks` (timeout, error_500, missing_record, duplicate_payment, lookalike_sender, slow_network_ms) used to show safe behaviour under failure.
- **Decision rule**: `>= 0.90` and no red flags -> `auto_handle`; `0.60-0.90` -> `ask_more`; `< 0.60` or any red flag -> `send_to_human`. See `docs/decision-rule.md`.
