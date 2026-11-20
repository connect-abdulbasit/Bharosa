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

## Routes (all exist as stubs)
`/login`, `/citizen`, `/citizen/check`, `/citizen/claim`, `/citizen/data`, `/helper`, `/officer`, `/admin/rules`, `/admin/chaos`, `/auditor`, `/eval`, plus PWA manifest (`src/app/manifest.ts`).

## Tasks
- [ ] TODO(Hani): login + role-based redirect, JWT storage, logout.
- [ ] TODO(Hani): Citizen home with big-icon Check / Claim / My data.
- [ ] TODO(Hani): Check screen: paste SMS -> verdict, confidence, reasons, read-aloud (ur/en).
- [ ] TODO(Hani): Claim screen: voice recording (Urdu), ID photo with blur retake prompt, saved progress, submit, explanation.
- [ ] TODO(Hani): Data & consent: see / share / withdraw / correct per scope.
- [ ] TODO(Hani): Helper Mode: ~40 families, per-family consent, quick switch.
- [ ] TODO(Hani): Officer queue (risk/confidence sort), case detail, approve/reject/ask more.
- [ ] TODO(Hani): Admin rule editor (versions), Chaos Panel UI (calls Hadi's `/chaos`), Auditor log, Eval dashboard.
- [ ] TODO(Hani): service worker/offline shell, low-bandwidth mode, notifications UI.
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
