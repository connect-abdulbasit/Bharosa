# contracts/ — shared contracts (everyone, additive only)

**Owner:** everyone. **Depends on:** nothing. **Depended on by:** every other folder.

## Rules
- Changes are **additive only**: add enum values/fields/endpoints; never rename, remove or change meaning. Breaking a contract breaks 4 people.
- Announce every change to the team (chat + mention in the PR) before merging.
- `enums.py` and `enums.ts` must always have identical values. After editing fixtures or `enums.ts`, tell Hani to run `npm run sync-contracts`.
- Python code here must stay Python 3.9 compatible (`Optional[X]`, `List[X]`).
- Every mock response model carries `simulated: bool = True`. Every AI output carries `confidence` and `model_version`.
- Fixtures: fake data only. CNICs are 13 digits starting `00000`. Names include spelling variants (Muhammad/Mohammad). Amounts in PKR. Explanations in Urdu + English.

## Files
| File | Purpose |
|---|---|
| `enums.py` / `enums.ts` | Role, CaseStatus, DecisionAction, MessageLabel, ConsentScope |
| `ai_interface.py` | Protocol + Pydantic models for the 6 AI functions |
| `schemas.py` | Request/response models for platform API and mock services |
| `openapi-platform.yaml` | Platform endpoint list (roles, request, response model) |
| `openapi-mocks.yaml` | Mock service endpoint list |
| `fixtures/*.json` | One realistic response per platform endpoint; backend serves them as stubs, frontend uses them in `fixtures` mode |

## Shared demo data: `fixtures/demo_people.json`
The demo citizens (accounts, identity records, ledger entries, fictional `agent-099` / `agent-017`, official and look-alike sender codes) live in ONE file, validated by `schemas.DemoPeople`. `/backend` reads it for its in-process fake mocks and for seeding accounts. **TODO(Hadi): `/mocks` must load the same file** (identity by `cnic`, ledger by `cnic`, `/senders`) so the demo scenarios behave identically against the real mocks. Additive changes only (add people, never change existing CNICs).

## Checklist
- [ ] TODO(Basit): confirm response models match what routers return (backend tests validate fixtures against `schemas.py`).
- [ ] TODO(Hani): confirm fixtures contain every state the UI needs (empty list, error, low confidence).
- [ ] TODO(Ali): confirm `ai_interface.py` fields are enough for eval and explain.
- [ ] TODO(Hadi): confirm mock shapes and chaos fields.

## Run / test
Validated by `backend/tests/test_fixtures.py` (`make test`).
