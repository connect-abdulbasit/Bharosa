# -*- coding: utf-8 -*-
"""Fifty hand-labelled end-to-end scenarios for the claim decision. FAKE people and amounts only.

Each case is run by eval/run_eval.py through the REAL extract_claim (spoken claims) -> match_person -> decide, with the ledger flags
worked out the way backend/app/services/pipeline.py does it. `expected` is what the written policy says the action should be (the labels
are written by the rule author, so the accuracy is an upper bound):
  - a spoken claim can never be auto_handle (extraction confidence is capped at 0.80), so a clean claim asks for more proof;
  - any red flag (short or duplicate payment, claim contradicting the ledger, failed service check) or an unmatched name goes to a person;
  - speech that cannot be understood stops early with ask_more;
  - a payment check (structured, confidence 1.0) is auto_handle only for a CONFIRMED full payment with a matching name.
Fields: id, kind ("claim" | "payment_check"), transcript, account (the citizen's account name, used by payment checks), identity (the name
on the identity record), aliases, payments (PKR amounts in the month; a repeated amount is a duplicate payment), photo ("none" | "clear"),
mock_failure, expected, note.
"""

AUTO, ASK, HUMAN = "auto_handle", "ask_more", "send_to_human"


def _c(cid, transcript, identity, payments, expected, note, aliases=(), photo="none", mock_failure=False, kind="claim", account=None):
    return {"id": cid, "kind": kind, "transcript": transcript, "account": account or identity, "identity": identity, "aliases": list(aliases),
            "payments": list(payments), "photo": photo, "mock_failure": mock_failure, "expected": expected, "note": note}


MISSING = "Mera naam %s hai. Mujhe is mahine ke paisay nahi mile"
CASES = [
    # ---- speech that cannot be turned into a claim: stops early and asks again
    _c("s01", "mujhe is mahine ke paisay nahi mile", "Fatima Noor", [], ASK, "no name spoken"),
    _c("s02", "mujhe paisay kam mile hain", "Fatima Noor", [], ASK, "no name spoken, short payment"),
    _c("s03", "hello", "Fatima Noor", [], ASK, "too short"),
    _c("s04", "Mera naam Fatima Noor hai", "Fatima Noor", [], ASK, "no problem mentioned"),
    _c("s05", "Mera naam Fatima Noor hai. Mujhe paisay nahi mile aur kam mile", "Fatima Noor", [], ASK, "two conflicting problems"),
    _c("s06", "مجھے اس مہینے کے پیسے نہیں ملے", "Fatima Noor", [], ASK, "no name spoken (Urdu)"),
    _c("s07", "asdf qwer zxcv bnmm poiu lkjh", "Fatima Noor", [], ASK, "gibberish"),
    # ---- clean claims, name matches: more proof is asked (a spoken claim never reaches 0.90)
    _c("s08", MISSING % "Rukhsana Bibi", "Rukhsana Bibi", [], ASK, "exact name"),
    _c("s09", MISSING % "Mohammad Aslam", "Muhammad Aslam", [], ASK, "Muhammad / Mohammad"),
    _c("s10", MISSING % "Fatma Noor", "Fatima Noor", [], ASK, "spelling variant"),
    _c("s11", "My name is Gul Bano Bibi. I did not receive my payment this month", "Gul Bano", [], ASK, "honorific suffix"),
    _c("s12", "میرا نام فاطمہ نور ہے۔ مجھے اس مہینے کے پیسے نہیں ملے", "Fatima Noor", [], ASK, "Urdu script name"),
    _c("s13", MISSING % "Fatima Bibi", "Fatima Noor", [], ASK, "alias on the record", aliases=["Fatima Bibi"]),
    _c("s14", "Mera naam Zubeda Khatun hai, october ke paisay nahi mile", "Zubaida Khatoon", [], ASK, "spelling variant, month named"),
    _c("s15", "Mera naam Naseem Akhtar hai. Mujhe paisay nahi mile", "Nasim Akhtar", [], ASK, "variant, month assumed"),
    # ---- the name does not match the identity record: a person must look
    _c("s16", MISSING % "Ahmed Raza", "Fatima Noor", [], HUMAN, "different person"),
    _c("s17", MISSING % "Rashid Mehmood", "Gul Bano", [], HUMAN, "different person"),
    _c("s18", "میرا نام احمد رضا ہے۔ مجھے اس مہینے کے پیسے نہیں ملے", "Fatima Noor", [], HUMAN, "different person (Urdu)"),
    _c("s19", MISSING % "Muhammad Asim", "Muhammad Aslam", [], HUMAN, "look-alike first name"),
    _c("s20", "Mera naam Salma Noor hai. Mujhe paisay nahi mile", "Salman Noor", [], HUMAN, "one letter apart in a short name"),
    _c("s21", "Mera naam Abdul Rehman hai. Is mahine paisay nahi mile", "Abdul Rahim", [], HUMAN, "look-alike second name"),
    # ---- short payment: red flag
    _c("s22", "Mera naam Gul Bano hai. Mujhe is mahine paisay kam mile hain", "Gul Bano", [8000], HUMAN, "ledger shows 8000 of 12000"),
    _c("s23", "Mera naam Gul Bano hai. Mujhe is mahine paisay kam mile hain", "Gul Bano", [4000], HUMAN, "ledger shows 4000 of 12000"),
    _c("s24", "My name is Zubaida Khatoon and I got less than the full payment", "Zubaida Khatoon", [9000], HUMAN, "ledger shows 9000"),
    _c("s25", "Mera naam Parveen Akhtar hai. Poore paisay nahi mile", "Parveen Akhtar", [6000], HUMAN, "ledger shows 6000"),
    _c("s26", "میرا نام گل بانو ہے۔ مجھے پیسے کم ملے ہیں", "Gul Bano", [8000], HUMAN, "ledger shows 8000 (Urdu)"),
    # ---- duplicate payment in the ledger: red flag
    _c("s27", MISSING % "Rukhsana Bibi", "Rukhsana Bibi", [12000, 12000], HUMAN, "the same payment twice"),
    _c("s28", "Mera naam Gul Bano hai. Mujhe is mahine paisay kam mile hain", "Gul Bano", [8000, 8000], HUMAN, "short and duplicated"),
    _c("s29", MISSING % "Fatima Noor", "Fatima Noor", [5000, 5000], HUMAN, "duplicated small payment"),
    # ---- the claim contradicts the ledger: red flag
    _c("s30", MISSING % "Rukhsana Bibi", "Rukhsana Bibi", [12000], HUMAN, "says missing, ledger shows paid in full"),
    _c("s31", "Mera naam Gul Bano hai. Mujhe is mahine paisay kam mile hain", "Gul Bano", [], HUMAN, "says short, ledger shows nothing"),
    _c("s32", "میرا نام فاطمہ نور ہے۔ مجھے اس مہینے کے پیسے نہیں ملے", "Fatima Noor", [12000], HUMAN, "says missing (Urdu), ledger shows paid"),
    _c("s33", "Mera naam Gul Bano hai. Mujhe is mahine paisay kam mile hain", "Gul Bano", [12000], HUMAN, "says short, ledger shows full"),
    # ---- a service check failed: never a guess, never an error page
    _c("s34", MISSING % "Rukhsana Bibi", "Rukhsana Bibi", [], HUMAN, "identity service down", mock_failure=True),
    _c("s35", "Mera naam Gul Bano hai. Mujhe is mahine paisay kam mile hain", "Gul Bano", [8000], HUMAN, "ledger service down", mock_failure=True),
    _c("s36", MISSING % "Fatma Noor", "Fatima Noor", [], HUMAN, "timeout, variant name", mock_failure=True),
    # ---- with a clear ID photo
    _c("s37", MISSING % "Rukhsana Bibi", "Rukhsana Bibi", [], ASK, "clear photo, clean claim", photo="clear"),
    _c("s38", MISSING % "Mohammad Aslam", "Muhammad Aslam", [], ASK, "clear photo, variant name", photo="clear"),
    # ---- says missing but part of the money was paid
    _c("s39", MISSING % "Gul Bano", "Gul Bano", [8000], HUMAN, "ledger shows 8000, not nothing"),
    _c("s40", MISSING % "Fatima Noor", "Fatima Noor", [3000], HUMAN, "ledger shows 3000, not nothing"),
    # ---- "did my payment arrive?" (structured, confidence 1.0)
    _c("s41", "", "Rukhsana Bibi", [12000], AUTO, "paid in full, name matches", kind="payment_check"),
    _c("s42", "", "Gul Bano", [12000], AUTO, "paid in full, name matches", kind="payment_check"),
    _c("s43", "", "Fatima Noor", [12000], AUTO, "paid in full, name matches", kind="payment_check"),
    _c("s44", "", "Muhammad Aslam", [12000], AUTO, "paid in full, Mohammad / Muhammad", kind="payment_check", account="Mohammad Aslam"),
    _c("s45", "", "Hamida Bibi", [12000], ASK, "paid in full but the account spelling differs from the record", kind="payment_check", account="Hameeda Begum"),
    _c("s46", "", "Gul Bano", [8000], HUMAN, "paid short", kind="payment_check"),
    _c("s47", "", "Gul Bano", [4000], HUMAN, "paid short", kind="payment_check"),
    _c("s48", "", "Fatima Noor", [12000, 12000], HUMAN, "paid twice", kind="payment_check"),
    _c("s49", "", "Fatima Noor", [], ASK, "no payment on record: asks whether to file a claim", kind="payment_check"),
    _c("s50", "", "Zubaida Khatoon", [12000], HUMAN, "account name differs from the identity record", kind="payment_check", account="Fatima Noor"),
]
