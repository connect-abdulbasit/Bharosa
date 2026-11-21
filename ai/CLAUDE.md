# ai/: Bharosa AI functions

**Owner:** Ali. **Depends on:** `/contracts` only. **Depended on by:** `/backend` (imports `bharosa_ai`).
Read the root `CLAUDE.md` first. For the full picture (flows, modules, limits) read `ai/architecture.md`.

## Contract (from `contracts/ai_interface.py`)
```python
classify_message(text: str, sender: str) -> MessageVerdict        # label, confidence, reasons, model_version
match_person(name: str, cnic: Optional[str], candidates: List[PersonRecord],
             father_name: Optional[str] = None, date_of_birth: Optional[str] = None) -> MatchResult  # match_id|None, score, variants, confidence, model_version
extract_claim(transcript: str) -> Union[ClaimDraft, ExtractionError]
read_document(image_bytes: bytes) -> DocumentReading              # fields, blur_score, format_ok, confidence, model_version
decide(claim: ClaimDraft, evidence: Evidence, rule: RuleVersion) -> Decision  # action, confidence, reasons, trace, rule_version, model_version
explain(trace: dict, lang: Literal["ur", "en"]) -> str
```
`father_name` and `date_of_birth` are optional extras of `match_person` (the contract has the first three arguments only); callers that pass three arguments get the original behaviour.
Decision rule: `confidence >= rule.auto_handle_min` and no red flags -> `auto_handle`; `>= rule.ask_more_min` -> `ask_more`; else or any red flag -> `send_to_human`. Payment steps always need officer approval. Cost assumptions for eval: wrong approval 10, wrong rejection 5, human review 1.

## Rules
- Pure functions. **No DB or HTTP calls except the optional LLM assist in `extract_claim`.** OCR and the scam text model run inside the process.
- **Calibrated probabilities**: confidence must mean something (check on held-out data).
- **Thresholds come from the `RuleVersion` input, never hard-coded.**
- Every output has `confidence` + `model_version` (at most 40 characters: `decisions.model_version` is `String(40)`). Never guess silently.
- Synthetic data only in `data/` (no real messages, names, CNICs, ID photos).
- Tests required for `decide` and `match_person` (spelling variants Muhammad/Mohammad, no-match returns None, lookalikes).
- Keep `stubs.py` working; backend/frontend depend on it. `AI_MODE=stub|real` picks in `bharosa_ai/__init__.py`.
- No secrets in any file or log. The LLM key lives only in the process environment (`LLM_API_KEY`); `ai/.env` is git-ignored and the package never reads it.

## Tasks
- [x] `classify.py` scam classifier (Urdu, Roman Urdu, English) with confidence and reasons; look-alike senders (`9O9O`); warnings such as "never share your OTP" are not treated as requests. Cue-weight rules.
- [x] `classify_ml.py` + generated `classify_ml_weights.py`: TF-IDF + logistic-regression text model in pure Python. Upgrade-only hybrid: it may turn a rule `unsure` into `scam` (p >= 0.85, never for the official sender `9090`). Regenerate with `eval/train_classifier.py` (needs scikit-learn) whenever `data/cases.py` changes.
- [x] `matching.py` fuzzy name/CNIC matching (transliteration, order swaps, honorifics, Urdu script) with optional father-name and date-of-birth corroboration.
- [x] `duplicates.py` `find_duplicates` (one CNIC two people; one person two CNICs). Not in the contract, not called by the backend yet.
- [x] `document.py` ID photo quality gate (`blur_score`, retake, format check) + optional local OCR (`ocr.py`, `idcard.py`): reads `cnic`, `name`, `father_name`, `date_of_birth` when RapidOCR or Tesseract is installed. Without an engine `fields` is `{}` and confidence is capped at 0.75; with OCR it is capped at 0.85.
- [x] `extract.py` voice transcript -> `ClaimDraft`: **offline rule parser first**, plus an optional LLM assist (`llm.py`) used only when the parser refused with `name_not_heard` / `no_claim_found`; strict reply schema, one validation retry; returns `ExtractionError` instead of guessing (including when no name is spoken).
- [x] `decide.py` combine confidences (weakest link), apply the rule version, red flags, document mismatch, trace.
- [x] `explain.py` plain-language Urdu + English from the trace (templates).
- [x] `data/` synthetic messages, name pairs, transcripts, 50 decision scenarios (`cases.py`, `decision_cases.py`) and fake card photos (`make_images.py`).
- [x] `eval/run_eval.py` writes `ai/eval/eval_results.json` (shape: `contracts.schemas.EvalResults` plus extra keys) and `ai/eval/cost_chart.png`.
- [x] tests for every function, a shared contract suite for stub and real, and the evaluation (670 tests).
- [x] No-key behaviour: with `AI_MODE=real` and no `LLM_API_KEY`/`LLM_MODEL`, `extract_claim` returns the offline draft with confidence -0.05 and `reasons=["llm_unavailable"]`; `bharosa_ai.capabilities()` / `describe()` report which function is real or a fallback (the backend logs it at startup and shows it on `/health` and `/eval`). AI_USE_LLM=0 is treated as a deliberate offline choice (no mark).
- [x] Live LLM check done with Gemini (`gemini-2.5-flash`, about 1 s per call; the Pro models need billing and the 3.x flash models take 4 to 11 s, longer than the 8 s timeout). Retries: 429/5xx are retried twice with a pause (Retry-After wins, capped at 5 s), a timeout once; after a failed burst the LLM is skipped for 20 s (`COOLDOWN_SECONDS`) so claims are not slowed. Free-tier keys hit 429 often.

## Real mode (`AI_MODE=real`): what the team must know
- All six functions are implemented and work **offline** (deterministic, no network). The only optional network call is the LLM assist in `extract_claim` (`bharosa_ai/llm.py`, stdlib `urllib`, any OpenAI-compatible chat-completions API). It is ON only when the process environment has `LLM_API_KEY` and `LLM_MODEL` (`LLM_BASE_URL` defaults to xAI `https://api.x.ai/v1`: SET IT for your provider, e.g. Gemini `https://generativelanguage.googleapis.com/v1beta/openai`; https only) and `AI_USE_LLM` is not `0`. With any of those missing, on timeout, bad JSON or a failed check the offline result is returned unchanged. Names only are listed in `ai/.env.example`; the package never reads `ai/.env`, and `docker COPY ai ./ai` would bake it into an image, so keep the key in the platform environment.
- The LLM can only FIND a claim type and the speaker's name: the name must be spoken in the transcript next to an introduction word, the speech must mention money or a payment, month/amount/CNIC still come from the offline parser, CNIC and phone digits are redacted before sending, and a disagreement on the claim type is an `ExtractionError`. Results it helped to make carry `model_version="extract-llm-1.0"`.
- `decide`, `match_person`, `classify_message`, `explain` and the photo gate never call an LLM. The ID photo never leaves the process.
- **OCR is optional.** `pip install "./ai[ocr]"` adds RapidOCR (pure pip, CPU, about 4 to 5 seconds per photo). Tesseract is the fallback (also needs its binary). `AI_USE_OCR=0` turns it off; `AI_OCR_ENGINE=rapidocr|tesseract` forces one. When a card CNIC or name disagrees with the claim, `decide` sends the case to a person (`document_mismatch`, `document_name_mismatch`). The backend Docker image installs the Tesseract binary with the English and Urdu packs plus `pytesseract` (`AI_OCR_LANG` overrides the default `eng+urd`).
- The **scam text model** runs on every `classify_message` call (about 0.2 ms); `AI_USE_ML=0` switches it off.
- `extract_claim` **refuses a transcript with no spoken name** (`ExtractionError`, `name_not_heard`): the stub invents "Mohammad Aslam", real mode does not. The backend demo scenarios (`contracts/fixtures/demo_people.json` transcripts have no name) therefore do not reproduce their stub outcomes in real mode; keep the demo on `AI_MODE=stub` or use transcripts like "Mera naam Rukhsana Bibi hai. Mujhe is mahine ke paisay nahi mile".
- "This month" (`is mahine`) resolves to the calendar month, or to `AI_DEFAULT_PERIOD` (`YYYY-MM`) when that env var is set: set `AI_DEFAULT_PERIOD=2026-10` to match the demo ledger.
- Claim confidence is capped at 0.80 and photo confidence at 0.75 (0.85 with OCR), so a spoken claim never auto-handles; only structured inputs (confidence 1.0, e.g. a payment check) can.
- `decide` ignores `RuleVersion.logic` on purpose and reads only `auto_handle_min`, `ask_more_min`; a missing name match, any red flag or any failed service check always goes to a person.
- `ai/eval/eval_results.json` is git-ignored at the repo root, but `GET /eval` reads it: run `python ai/eval/run_eval.py` in the build, or un-ignore it. With the file present, one backend test (`test_eval.py::test_seeded_counts_and_shape`) fails locally.

## Env flags (all optional; names only, see `.env.example`)
`AI_MODE`, `AI_DEFAULT_PERIOD`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, `AI_USE_LLM`, `AI_USE_ML`, `AI_USE_OCR`, `AI_OCR_ENGINE`, `LLM_PRICE_PER_1M_TOKENS` (evaluation only). `conftest.py` turns the LLM, text model and OCR off for every test.

## Run / test
```
make test                       # from repo root (runs all folders)
cd ai && ../.venv/bin/python -m pytest -q       # 670 tests; real-engine tests skip when an extra is missing
pip install "./ai[ocr]"         # optional OCR; "./ai[ml]" only for the dev scripts below
AI_MODE=real python -c "import bharosa_ai"    # real mode
python eval/run_eval.py         # writes ai/eval/eval_results.json + cost_chart.png (all cases; --split test for the hash hold-out, --no-images to skip photos, --no-chart)
python eval/run_eval.py --llm   # also compares offline vs LLM-assisted extraction (loads ai/.env, calls the LLM; the default run never does)
python eval/compare_ml.py       # dev: rules vs text model vs hybrid, cross-validated (scikit-learn)
python eval/train_classifier.py # dev: retrain the text model and regenerate bharosa_ai/classify_ml_weights.py (scikit-learn)
```
