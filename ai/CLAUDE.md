# ai/: Bharosa AI functions

**Owner:** Ali. **Depends on:** `/contracts` only. **Depended on by:** `/backend` (imports `bharosa_ai`).
Read the root `CLAUDE.md` first.

## Contract (from `contracts/ai_interface.py`)
```python
classify_message(text: str, sender: str) -> MessageVerdict        # label, confidence, reasons, model_version
match_person(name: str, cnic: Optional[str], candidates: List[PersonRecord]) -> MatchResult  # match_id|None, score, variants, confidence, model_version
extract_claim(transcript: str) -> Union[ClaimDraft, ExtractionError]
read_document(image_bytes: bytes) -> DocumentReading              # fields, blur_score, format_ok, confidence, model_version
decide(claim: ClaimDraft, evidence: Evidence, rule: RuleVersion) -> Decision  # action, confidence, reasons, trace, rule_version, model_version
explain(trace: dict, lang: Literal["ur", "en"]) -> str
```
Decision rule: `confidence >= rule.auto_handle_min` and no red flags -> `auto_handle`; `>= rule.ask_more_min` -> `ask_more`; else or any red flag -> `send_to_human`. Payment steps always need officer approval. Cost assumptions for eval: wrong approval 10, wrong rejection 5, human review 1.

## Rules
- Pure functions. **No DB or HTTP calls except the LLM** (extract_claim, explain).
- **Calibrated probabilities**: confidence must mean something (check on held-out data).
- **Thresholds come from the `RuleVersion` input, never hard-coded.**
- Every output has `confidence` + `model_version`. Never guess silently.
- Synthetic data only in `data/` (no real messages, names, CNICs, ID photos).
- Tests required for `decide` and `match_person` (spelling variants Muhammad/Mohammad, no-match returns None, lookalikes).
- Keep `stubs.py` working; backend/frontend depend on it. `AI_MODE=stub|real` picks in `bharosa_ai/__init__.py`.

## Tasks
- [ ] TODO(Ali): `classify.py` scam classifier (Urdu, Roman Urdu, English) with confidence and reasons; lookalike senders (`9O9O`).
- [ ] TODO(Ali): `matching.py` fuzzy name/CNIC matching for messy data (transliteration, order swaps, honorifics).
- [ ] TODO(Ali): `document.py` OCR on ID photos with blur check (`blur_score`, ask retake), format check.
- [ ] TODO(Ali): `extract.py` Urdu voice transcript -> `ClaimDraft` via LLM + Pydantic validation; return `ExtractionError` instead of guessing.
- [ ] TODO(Ali): `decide.py` combine confidences, apply rule version, red flags, trace.
- [ ] TODO(Ali): `explain.py` plain-language Urdu + English from the trace.
- [ ] TODO(Ali): `data/` synthetic scam/genuine messages, name pairs, sample images.
- [ ] TODO(Ali): `eval/run_eval.py` writes `eval_results.json` (shape: `contracts.schemas.EvalResults`) incl. cost totals.
- [ ] TODO(Ali): tests for `decide` and `match_person` against the real implementations.

## Run / test
```
make test                       # from repo root (runs all folders)
cd ai && ../.venv/bin/python -m pytest -q
AI_MODE=real python -c "import bharosa_ai"    # real mode
python eval/run_eval.py
```
