"""Pure data for the demo scenarios (no imports): used by app/demo.py (users, cases) and fake_mocks_client.py (identity, ledger).

ALL FAKE. The stub AI always 'hears' the name "Mohammad Aslam" (claim confidence 0.81), so each scenario person's FAKE identity
record lists that name as an alias, except scenario 2 where the record says "Muhammad Aslam" (a pure spelling variant).
"""
STUB_HEARD_NAME = "Mohammad Aslam"
PROGRAMME = "Sahara Relief Programme"
FIRST_SCENARIO_FAMILY = 11  # fam-011 ... fam-016


def _id(name, aliases, father, district):
    return {"full_name": name, "father_name": father, "date_of_birth": "1980-01-01", "district": district, "aliases": aliases, "phone_last4": "0000"}


def _pay(pid, amount, agent):
    return [{"payment_id": pid, "amount_pkr": amount, "date": "2026-10-05", "agent_id": agent, "programme": PROGRAMME}]


SCENARIOS = [
    {"n": 1, "key": "clean-approval", "title": "Clean approval", "username": "s1-clean", "user_id": "u-demo-1", "name": "Rukhsana Bibi",
     "cnic": "0000042101101", "identity": _id("Rukhsana Bibi", [STUB_HEARD_NAME], "Noor Din", "Malir"), "payments": [],
     "transcript": "mujhe is mahine ke paisay nahi mile",
     "expect": "needs_more_proof (stub AI confidence 0.81), then the officer approves and PKR 12000 is paid exactly once"},
    {"n": 2, "key": "misspelled-name", "title": "Misspelled name (ask more)", "username": "s2-spelling", "user_id": "u-demo-2",
     "name": "Muhammed Aslam", "cnic": "0000042101102", "identity": _id("Muhammad Aslam", [], "Abdul Rehman", "Korangi"), "payments": [],
     "transcript": "mujhe is mahine ke paisay nahi mile",
     "expect": "needs_more_proof: the heard name 'Mohammad Aslam' matches 'Muhammad Aslam' only as a spelling variant"},
    {"n": 3, "key": "short-payment-bad-agent", "title": "Short payment by a bad agent (officer)", "username": "s3-shortpay", "user_id": "u-demo-3",
     "name": "Shabana Kausar", "cnic": "0000042101103", "identity": _id("Shabana Kausar", [STUB_HEARD_NAME], "Mir Hassan", "Karachi East"),
     "payments": _pay("pay-9003", 8000, "agent-099"), "transcript": "mujhe paisay kam mile hain",
     "expect": "with_officer: short_payment red flag, PKR 8000 of 12000 paid by agent-099"},
    {"n": 4, "key": "duplicate-claim", "title": "Duplicate claim, same month (officer)", "username": "s4-duplicate", "user_id": "u-demo-4",
     "name": "Naseem Akhtar", "cnic": "0000042101104", "identity": _id("Naseem Akhtar", [STUB_HEARD_NAME], "Ghulam Nabi", "Malir"), "payments": [],
     "transcript": "mujhe is mahine ke paisay nahi mile", "open_case": "case-demo-4",
     "expect": "with_officer: an open claim for 2026-10 already exists (case-demo-4)"},
    {"n": 5, "key": "consent-withdrawn", "title": "Consent withdrawn (blocked and logged)", "username": "s5-consent", "user_id": "u-demo-5",
     "name": "Hameeda Begum", "cnic": "0000042101105", "identity": _id("Hameeda Begum", [STUB_HEARD_NAME], "Allah Bakhsh", "Korangi"), "payments": [],
     "transcript": "mujhe is mahine ke paisay nahi mile", "withdrawn": "payments",
     "expect": "with_officer: the ledger step is blocked (payments consent withdrawn) and logged; after the citizen grants again, resume completes"},
    {"n": 6, "key": "identity-service-down", "title": "Identity service down (paused, then resume)", "username": "s6-idown", "user_id": "u-demo-6",
     "name": "Parveen Akhtar", "cnic": "0000042101106", "identity": _id("Parveen Akhtar", [STUB_HEARD_NAME], "Din Muhammad", "Karachi West"), "payments": [],
     "transcript": "mujhe is mahine ke paisay nahi mile",
     "expect": "with_officer paused at identity_lookup with a note; after the service is back, resume completes"},
]

# ---- Scam Map seed: 60 FAKE scam checks over fictional areas. Areas under 3 reports are grouped as 'other' by the API.
SCAM_AREAS = [("Noorabad", 18), ("Sahil Colony", 14), ("Bagh-e-Zubaida", 10), ("Mehran Town North", 8), ("Kausar Basti", 6), ("Tiny Village", 2), (None, 2)]
SCAM_SENDERS = ["SAHARA-INFO", "9O9O", "RELIEF-PAY", "SAHARA-lNFO", "0300-0000000", "GOV-RELIEF"]
SCAM_CUES = ["http", "bit.ly", "fee", "urgent", "otp"]
