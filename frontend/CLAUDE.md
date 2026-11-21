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
| `/citizen/data` | citizen, helper | Working: consent see / withdraw (confirm) / share again / correct name or phone |
| `/helper` | helper | Family list |
| `/helper/[familyId]` | helper | One person's case: "now helping" banner, status, consent, voice note saved per person, "Switch person" clears the screen. Accepts `1` or `fam-001` |
| `/officer` | officer, admin | Review queue |
| `/officer/case/[id]` | officer, admin | Case detail, AI confidence, reasons, rule version, full trace, notes, Approve / Reject / Ask for more proof (officer only) |
| `/admin` | admin | Users and roles list |
| `/admin/rules` | admin | Working: active version, threshold bar, history, propose + publish new version |
| `/admin/twin` | admin | Working: sliders -> `POST /rules/{id}/simulate` (real backend simulation) |
| `/admin/chaos` | admin | Working: backend `/admin/demo/chaos` switches, `/health`, demo reset |
| `/auditor` | auditor, admin | Working: filters, paging, before/after diff |
| `/eval` | officer, admin, auditor | Working: live `/eval` numbers + Scam Map |

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
- [x] `/citizen/data`, `/admin/rules`, `/admin/chaos`, `/auditor`, `/eval` (Scam Map included), API keys on `/admin`.
- [x] Design system "warm trust" (see below), live-mode API layer (202 + progress polling, real error format, 401 -> login), blur check in `PhotoCapture`, "Did my payment arrive?" button.
- [x] Service worker offline shell (`public/sw.js`, production builds only), data-saver / low-bandwidth mode (`lib/lite.ts`, ETag/304 in `lib/api.ts`), in-app notifications bell (`lib/notices.ts`), dark/light theme (`lib/theme.ts`).
- [x] Voice-note recorder where `SpeechRecognition` is missing (`VoiceNote.tsx`); the platform only accepts text, so typing stays required.
- [ ] TODO(Hani): Vercel deploy; URL in README.

## Deploy (Vercel)
Root directory `frontend`, env `NEXT_PUBLIC_API_MODE=live` and `NEXT_PUBLIC_API_URL=<backend URL>` (baked at build time: redeploy after changing them), then add the Vercel origin to the backend's `CORS_ORIGINS`. Full checklist: ../DEPLOY.md.

## Run / test
```
cd frontend
npm install
npm run sync-contracts     # after any /contracts change
npm run dev                # http://localhost:3000 (fixtures mode)
NEXT_PUBLIC_API_MODE=live NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
npm run lint && npm run build
```

## Design system (src/app/globals.css, src/components/ui.tsx)
- Tokens in `:root` (cream/teal/saffron). Use Tailwind names: `bg-teal-700`, `text-saffron-600`, `bg-cream-2`, `border-line`, `text-ink-soft`. Urdu text: `dir="rtl" lang="ur"` (Naskh face via `[lang="ur"]`).
- Primitives in `components/ui.tsx`: `Button`/`LinkButton` (English + Urdu), `Card`, `Badge`, `Notice`, `Field`, `Stat`, `Meter`, `Skeleton`, `EmptyState`, `SectionTitle`. Icons: `components/Icon.tsx` (no emoji).
- `PageShell` picks navigation by role: bottom tab bar for citizen/helper, top pills + wide layout for staff (`wide`).
- Page files may only export the default component: put shared constants in `lib/` (e.g. `lib/status.ts`).
- Loaders that set state go through `useLoader` (`lib/hooks.ts`) to satisfy the `react-hooks/set-state-in-effect` lint rule.
- `.env.local` (git-ignored) sets live mode; delete it to get fixtures mode.

## Backend gaps found while wiring live mode
- `GET /helper/families` does not return the citizen's user id; helpers need it for `on_behalf_of` / `citizen_id`. `familyCitizenId()` falls back to `fam-00N -> u-citizen-N`. TODO(Basit): add `citizen_id` to the response.
- No `GET /users` (admin users list): shown in fixtures mode only.

## Offline, data saver, notifications, theme (what to know)
- `public/sw.js` caches page HTML + build assets only, NEVER API responses (other origin). Unvisited pages redirect to `/offline`. It registers only in `next build` + `next start` (not in `next dev`). Bump `VERSION` in sw.js when its logic changes. Test offline by really stopping the web server: Chrome's offline emulation does not affect the worker's own requests.
- Data saver (`html[data-lite]`): auto-on for Save-Data / 2G, toggle in the header. Polling slows down and pauses while the tab is hidden. GETs send `If-None-Match` (ETag exists on `/cases/{id}`, `/queue`, `/claims/{id}/progress`, not on the `/cases` list).
- Notifications: no push channel exists, so `NotificationBell` checks `/cases` while the app is open and compares statuses. Browser alerts need the person's permission and only fire while the app/PWA is open. Notices are per user in localStorage and cleared on log out.
- Theme: `<html data-theme>` set by an inline script before paint; use the semantic colours (`text-heading`, `text-brand`, `bg-*-soft`, `text-*-ink`, `text-on-accent`) instead of raw teal-900/ok-700 for text/tints so dark mode stays readable. Utilities can override `.card` (it lives in `@layer components`).
- CORS: the backend only allows `http://localhost:3000`; run the frontend on port 3000 (dev or `next start -p 3000`).

## Layout (app shell)
- `PageShell`: header (logo left, controls right, never wraps) + content. Signed in at `lg+`: left sidebar (`NavBar variant="side"`) and content; below `lg`: bottom tab bar (citizen/helper) or pill row (staff). Frame is `max-w-[88rem]`.
- Pages are a focused reading column (`max-w-3xl`) by default. Pass `wide` for dashboards and two-column pages and use `grid lg:grid-cols-*` inside. Public pages (login, offline) have no nav.
- `.card` and `.input` live in `@layer components`, so Tailwind utilities (`ps-12`, `bg-*`, `border-*`) override them.
- Overflow check used before release: every page at 360 / 768 / 1280 / 1920 px in light and dark, zero horizontal overflow.
