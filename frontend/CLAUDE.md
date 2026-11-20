# frontend/: Bharosa PWA (Next.js + TypeScript + Tailwind)

**Owner:** Hani. **Depends on:** `/contracts` only (copied in by `npm run sync-contracts`). **Depended on by:** `/e2e`.
Read the root `CLAUDE.md` first. Also read `AGENTS.md`: this Next.js version has breaking changes; check `node_modules/next/dist/docs/` before using APIs.

## Contract
- Fixtures in `src/fixtures/*.json` and `src/lib/enums.ts` are **copies** of `/contracts`. Never edit them by hand; run `npm run sync-contracts`.
- `src/lib/api.ts`: `api(method, path, {body, token})`. `NEXT_PUBLIC_API_MODE=fixtures` (default) needs no backend; `live` calls `NEXT_PUBLIC_API_URL`. Response shapes: `contracts/schemas.py`.

## Rules
- **Mobile-first**, large tap targets and icons; users cannot read well.
- **Every result has read-aloud** (Web Speech API, Urdu + English).
- **Every form step is saved to IndexedDB** (weak signal: resume after reload/offline).
- **Works in `fixtures` mode without a backend**.
- **Urdu + English labels** everywhere (Urdu RTL: `dir="rtl" lang="ur"`).
- **"PROTOTYPE - simulated data" banner on every page** (`components/Banner.tsx`, already in `PageShell`).
- Never trust the UI for security: hide actions by role for UX only; the backend enforces RBAC.
- Show uncertainty honestly: low confidence -> say "we need a person to check", never a confident-looking guess.
- No real personal data; use fixtures.

## Routes (17 pages, all wrapped in `PageShell`: prototype banner + `RoleGuard`)
| Route | Role(s) | Status |
|---|---|---|
| `/` | public | Landing page (pitch, problem, 3 big cards, prototype notice, Login / Try demo) |
| `/login` | public | Working: demo user buttons + form (fixtures mode checks the fake demo passwords locally; live mode calls `/auth/login` + `/me`) |
| `/citizen` | citizen, helper | Home with `BigIconButton`s |
| `/citizen/check` | citizen, helper | Working: scam verdict + `ReadAloud` |
| `/citizen/claim` | citizen, helper | Working: `MicButton` + `PhotoCapture`, progress saved in IndexedDB per person, result + `ReadAloud` |
| `/citizen/status` | citizen, helper | Claim timeline (`StatusTimeline`) + `ReadAloud` |
| `/citizen/data` | citizen, helper | Stub (TODO(Hani): consent see/share/withdraw/correct) |
| `/helper` | helper | Family list |
| `/helper/[familyId]` | helper | One person's case: "now helping" banner, status, consent, voice note saved per person, "Switch person" clears the screen. Accepts `1` or `fam-001` |
| `/officer` | officer, admin | Review queue |
| `/officer/case/[id]` | officer, admin | Case detail, AI confidence, reasons, rule version, full trace, notes, Approve / Reject / Ask for more proof (officer only) |
| `/admin` | admin | Users and roles list |
| `/admin/rules` | admin | Stub (TODO(Hani): versioned rule editor) |
| `/admin/twin` | admin | Digital Twin: pick a rule change, see "X past cases would change decision" (fixture data) |
| `/admin/chaos` | admin | Stub (TODO(Hani): Chaos Panel UI over Hadi's `/chaos`) |
| `/auditor` | auditor, admin | Stub (TODO(Hani): audit log viewer) |
| `/eval` | officer, admin, auditor | Stub (TODO(Hani): evaluation dashboard) |

PWA manifest: `src/app/manifest.ts`. Dynamic pages that call `useParams()` must be wrapped in `<Suspense>` (Next 16 build fails otherwise).

## Components (`src/components`)
`PrototypeBanner` (on every page via `PageShell`), `PageShell`, `RoleGuard` (UX-only redirect to `/login`), `SessionBar`, `BigIconButton` (icon + English + Urdu), `MicButton` (Urdu `ur-PK` speech with Yes/No confirm; typed fallback), `ReadAloud` (Urdu voice if available, otherwise English), `PhotoCapture` (camera/file, preview, retake), `StatusTimeline`.

## Lib (`src/lib`)
`api.ts` (fixtures/live), `auth.ts` (session in localStorage, demo users), `offline.ts` (IndexedDB via `idb`: `saveProgress/loadProgress/clearProgress` per page and per person), `speech.ts` (recognition + synthesis helpers), `types.ts` (hand-written response types), `enums.ts` (synced).

## Frontend-only fixtures (move to `/contracts` later)
Kept in `src/fixtures/local/` so `npm run sync-contracts` never deletes them. Not in `/contracts` and **no backend endpoint exists yet**:
- `users.json` -> `GET /users` (admin users list). TODO(Basit): add endpoint + contract.
- `twin_proposals.json` -> `GET /twin/proposals` (Digital Twin). TODO(Hadi): own the real simulation, then add to contracts.
Also: `/citizen/status` and `/helper/[familyId]` use the first case from `GET /cases` because the backend does not link cases to families yet.

## Tasks
- [x] Login + role redirect, session, logout (demo users).
- [x] Landing, citizen home/check/claim/status, helper list + person view, officer queue + case, admin users, Digital Twin.
- [x] Read-aloud on every citizen result; saved progress on claim and helper person pages.
- [ ] TODO(Hani): `/citizen/data` consent screen, `/admin/rules`, `/admin/chaos`, `/auditor`, `/eval`.
- [ ] TODO(Hani): service worker / offline shell, low-bandwidth mode, notifications UI.
- [ ] TODO(Hani): blur check hint from `/documents` in `PhotoCapture`; real audio capture for Urdu where `SpeechRecognition` is missing.
- [ ] TODO(Hani): Vercel deploy; URL in README.

## Run / test
```
cd frontend
npm install
npm run sync-contracts     # after any /contracts change
npm run dev                # http://localhost:3000 (fixtures mode)
NEXT_PUBLIC_API_MODE=live NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
npm run lint && npm run build
```
