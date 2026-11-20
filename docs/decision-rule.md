# Decision rule

Implemented by `decide()` in `/ai` (`contracts/ai_interface.py`), with thresholds read from the active **rule version** (editable by admins, versioned, no redeploy).

| Condition | Action | What happens |
|---|---|---|
| combined confidence >= **0.90** and **no red flags** | `auto_handle` | Pipeline continues. A payment step **still needs officer approval**. |
| **0.60 to 0.90** (no red flags) | `ask_more` | Citizen is asked for specific missing proof (clearer photo, another detail), in plain Urdu/English. |
| **below 0.60**, or **any red flag** | `send_to_human` | Case goes to the officer queue with case notes and the reasons. |

**Red flags** (examples): short payment, duplicate payment, lookalike sender, mock service failure, name matched only via variant, blurred document.

## Why
- *Behaviour over claims*: the system must show what it does when unsure. Unsure never means "guess".
- Costs are asymmetric. For evaluation: **wrong approval = 10**, **wrong rejection = 5**, **human review = 1**. A human check is cheap relative to paying the wrong person, so we send uncertain cases to people.
- Combined confidence is conservative (weakest link), so one poor signal (e.g. blurred ID) lowers the whole decision.
- Every decision stores `rule_version` and a `trace`, so a result can be replayed and explained later (`explain()` turns the trace into plain Urdu/English).
- Payments are never fully automatic: any payment step needs an officer.
