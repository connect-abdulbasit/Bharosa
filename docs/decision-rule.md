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

## Cost of being wrong, by threshold
Source: `python ai/eval/run_eval.py` (`cost_curve` in `ai/eval/eval_results.json`, chart `ai/eval/cost_chart.png`; also on the Insights page `/eval`). Synthetic data, so these are upper bounds. Per 1000 cases, costs: wrong approval 10, wrong rejection 5, human review 1; a case with confidence c is legitimate with probability c.

| auto-handle threshold | wrong approvals | human reviews | total cost |
|---|---|---|---|
| 0.50 | 125 | 500 | 1750 |
| 0.70 | 45 | 700 | 1150 |
| 0.80 | 20 | 800 | 1000 |
| **0.90 (chosen)** | **5** | **900** | **950 (cheapest tested)** |
| 0.95 | 1.25 | 950 | 962.5 |
| 0.99 | 0.05 | 990 | 990.5 |

Below 0.90 the cost is dominated by wrong approvals (10 each); above it, by reviews. Simple alternatives are far worse on the 1000-case decision set: "claim confidence only" costs 5196, "average confidence with no stops" 2750, "always send to a human" 2775, against 551 for the real rule (0 wrong approvals, 28 wrong rejections, 411 reviews).
