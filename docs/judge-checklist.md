# "Try to break it": checklist for judges

Prototype with simulated data. Demo logins are in the README (username = role). Suggested probes:

**Security**
- [ ] Call an officer-only endpoint (`POST /cases/{id}/decide`) as a citizen -> expect 403.
- [ ] Call any endpoint with no token or a tampered token -> expect 401.
- [ ] Open `/audit` as a citizen -> expect 403; as auditor -> entries for user, AI and agent actions.
- [ ] Try to use an API key outside its scope; hammer an endpoint -> rate limit.

**Uncertainty and bad data**
- [ ] Submit a blurry ID photo -> asked to retake, not guessed.
- [ ] Misspell a name (Mohammad/Muhammad, swapped order) -> matches with noted variant, or goes to a human.
- [ ] Submit an incoherent voice transcript -> `ExtractionError`/asks again, no invented claim.
- [ ] Paste an ambiguous SMS -> `unsure`, not a confident label.

**Failure handling (Chaos Panel)**
- [ ] Turn on `error_500`, `timeout`, `missing_record`, `slow_network_ms` -> case goes to an officer with notes; user never sees a stack trace.
- [ ] `duplicate_payment` -> flagged, sent to a human.
- [ ] `lookalike_sender` -> scam detection still flags it.

**Consent and control**
- [ ] Withdraw a consent scope -> later claim makes no call for that scope; audit shows it.
- [ ] Correct a wrong data item -> change is logged.

**Rules**
- [ ] Admin publishes a new rule version -> no redeploy; new decisions store the new version; old ones keep theirs.
- [ ] Any payment step -> always needs officer approval.

**Honesty**
- [ ] Every mock response says `"simulated": true`; every page shows the prototype banner.
- [ ] Evaluation dashboard shows errors and cost of wrong approvals vs rejections.
