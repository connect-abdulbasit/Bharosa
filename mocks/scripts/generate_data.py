"""Deterministic synthetic data for the mock services (all FAKE, no real people).

Run from the repo root:  python mocks/scripts/generate_data.py
Writes mocks/app/data/{identity,ledger,senders,labels}.json. Same seed -> same files.

The first five records are kept exactly as before: the backend seeds and fixtures use them.
"""
import json
import random
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "mocks" / "app" / "data"
DEMO_PEOPLE = ROOT / "contracts" / "fixtures" / "demo_people.json"  # shared with the backend's fake client
PROGRAMME = "Sahara Relief Programme"
EXPECTED_PKR = 12000
BAD_AGENTS = ["agent-044", "agent-058", "agent-099"]  # 099 also short-pays demo scenario 3
GOOD_AGENTS = ["agent-%03d" % n for n in range(1, 31) if "agent-%03d" % n not in BAD_AGENTS]
DISTRICTS = ["Karachi East", "Karachi West", "Karachi Central", "Malir", "Korangi", "Keamari", "Karachi South"]

# The original five people and payments (unchanged).
BASE_IDENTITY: List[Dict[str, Any]] = [
    {"cnic": "0000042101001", "full_name": "Muhammad Aslam", "father_name": "Abdul Rehman", "date_of_birth": "1984-03-12", "district": "Karachi East", "aliases": ["Mohammad Aslam", "M. Aslam"], "phone_last4": "4471"},
    {"cnic": "0000042101002", "full_name": "Fatima Noor", "father_name": "Noor Muhammad", "date_of_birth": "1979-07-01", "district": "Karachi West", "aliases": ["Fatima Bibi", "Fatma Noor"], "phone_last4": "9902"},
    {"cnic": "0000042101003", "full_name": "Zubaida Khatoon", "father_name": "Ghulam Hussain", "date_of_birth": "1968-11-23", "district": "Malir", "aliases": ["Zubeda Khatun"], "phone_last4": "1356"},
    {"cnic": "0000042101004", "full_name": "Gul Bano", "father_name": "Mir Hassan", "date_of_birth": "1990-01-30", "district": "Korangi", "aliases": ["Gul Bano Bibi"], "phone_last4": "7720"},
    {"cnic": "0000042101005", "full_name": "Rashid Mehmood", "father_name": "Mehmood Ahmed", "date_of_birth": "1975-09-09", "district": "Karachi Central", "aliases": ["Rasheed Mahmood", "Mohammad Rashid"], "phone_last4": "3085"},
]
BASE_LEDGER: Dict[str, List[Dict[str, Any]]] = {
    "0000042101001": [{"payment_id": "pay-1001", "amount_pkr": 8000, "date": "2026-10-05", "agent_id": "agent-017", "programme": PROGRAMME}],
    "0000042101002": [{"payment_id": "pay-1002", "amount_pkr": 12000, "date": "2026-10-05", "agent_id": "agent-017", "programme": PROGRAMME}],
    "0000042101003": [],
    "0000042101004": [{"payment_id": "pay-1004", "amount_pkr": 12000, "date": "2026-09-05", "agent_id": "agent-022", "programme": PROGRAMME}],
    "0000042101005": [{"payment_id": "pay-1005", "amount_pkr": 12000, "date": "2026-10-06", "agent_id": "agent-031", "programme": PROGRAMME}],
}

FEMALE = ["Ayesha", "Fatima", "Zainab", "Khadija", "Rukhsana", "Shabana", "Nasreen", "Samina", "Parveen", "Bilqis",
          "Mumtaz", "Shamim", "Naseem", "Razia", "Saima", "Hajra", "Kalsoom", "Sakina", "Rabia", "Farzana"]
MALE = ["Imran", "Tariq", "Bilal", "Salman", "Kamran", "Naveed", "Shahid", "Irfan", "Javed", "Nadeem",
        "Asif", "Waseem", "Yaqoob", "Ilyas", "Saeed", "Zahid", "Arshad", "Habib", "Jamil", "Rafiq"]
SURNAMES = ["Khan", "Ahmed", "Hussain", "Ali", "Shah", "Baloch", "Memon", "Siddiqui", "Qureshi", "Malik",
            "Chaudhry", "Ansari", "Abbasi", "Soomro", "Jatoi", "Rind"]
FATHER_FIRST = ["Abdul Karim", "Ghulam Rasool", "Noor Muhammad", "Muhammad Yousuf", "Abdul Ghaffar", "Din Muhammad",
                "Allah Bux", "Mir Ahmed", "Haji Sultan", "Fazal Elahi"]
URDU_FIRST = {"Ayesha": "عائشہ", "Fatima": "فاطمہ", "Zainab": "زینب", "Khadija": "خدیجہ", "Imran": "عمران",
              "Bilal": "بلال", "Tariq": "طارق", "Shahid": "شاہد", "Nasreen": "نسرین", "Parveen": "پروین"}
MUHAMMAD_FORMS = ["Muhammad", "Mohammad", "Muhammed", "Mohd", "Mohammed"]
LOOKALIKES = ["9O9O", "909O", "SAHARA-lNFO", "SAHRA-GOV", "9090-SAHARA-PAY", "SAHARA-GOV.", "9O90"]


def _dob(rng: random.Random) -> str:
    return "%d-%02d-%02d" % (rng.randint(1950, 1998), rng.randint(1, 12), rng.randint(1, 28))


def build() -> Dict[str, Any]:
    rng = random.Random(2026)
    identity: List[Dict[str, Any]] = [dict(p) for p in BASE_IDENTITY]
    ledger: Dict[str, List[Dict[str, Any]]] = {k: list(v) for k, v in BASE_LEDGER.items()}
    labels: Dict[str, Any] = {
        "expected_monthly_pkr": EXPECTED_PKR, "bad_agents": BAD_AGENTS, "name_variants": [],
        "missing_fields": [], "duplicate_identities": [], "wrong_records": [],
        "short_payments": [{"cnic": "0000042101001", "payment_id": "pay-1001", "expected_pkr": EXPECTED_PKR,
                            "paid_pkr": 8000, "agent_id": "agent-017"}],
        "duplicate_payments": [], "no_payment": ["0000042101003"],
    }

    # 75 generated people: CNIC ...010 to ...084 (the 1101+ range belongs to backend demo people).
    for i in range(75):
        n = 10 + i
        cnic = "00000421010%02d" % n if n < 100 else "0000042101%03d" % n
        female = i % 2 == 0
        first = rng.choice(FEMALE if female else MALE)
        last = rng.choice(SURNAMES)
        use_muhammad = (not female) and i % 3 == 1  # many men are named Muhammad X
        base_name = ("Muhammad %s" % first) if use_muhammad else ("%s %s" % (first, last))
        full_name = base_name
        aliases: List[str] = []
        if use_muhammad:
            forms = rng.sample(MUHAMMAD_FORMS[1:], 2)
            aliases = ["%s %s" % (f, first) for f in forms] + ["M. %s" % first]
            labels["name_variants"].append({"cnic": cnic, "canonical": base_name, "variants": aliases})
        elif i % 4 == 0:
            aliases = ["%s Bibi" % first] if female else ["%s %s" % (first, rng.choice(SURNAMES))]
        if first in URDU_FIRST:
            aliases.append(URDU_FIRST[first] + " " + last)
        if i % 13 == 5:
            full_name = "  %s  %s " % tuple(base_name.split(" ", 1))  # stray whitespace
            labels["name_variants"].append({"cnic": cnic, "canonical": base_name, "variants": [full_name]})
        rec: Dict[str, Any] = {
            "cnic": cnic, "full_name": full_name,
            "father_name": rng.choice(FATHER_FIRST) if i % 7 != 3 else None,
            "date_of_birth": _dob(rng) if i % 11 != 6 else None,
            "district": rng.choice(DISTRICTS), "aliases": aliases,
            "phone_last4": "%04d" % rng.randint(0, 9999),
        }
        if rec["father_name"] is None:
            labels["missing_fields"].append({"cnic": cnic, "field": "father_name"})
        if rec["date_of_birth"] is None:
            labels["missing_fields"].append({"cnic": cnic, "field": "date_of_birth"})
        identity.append(rec)

    # 6 duplicate identities: same name + DOB as an earlier person, different CNIC.
    sources = [p for p in identity[5:] if p["date_of_birth"] and p["father_name"]]
    for j in range(6):
        src = sources[j * 7 % len(sources)]
        dup_cnic = "00000421010%02d" % (90 + j)
        identity.append(dict(src, cnic=dup_cnic, aliases=[], phone_last4="%04d" % rng.randint(0, 9999)))
        labels["duplicate_identities"].append({"cnic": dup_cnic, "same_as": src["cnic"]})
        ledger[dup_cnic] = []

    # 4 wrong records: the registry DOB disagrees with what the person (and their card) says.
    wrong_pool = [p for p in identity[5:80] if p["date_of_birth"] and p["cnic"] not in {d["cnic"] for d in labels["duplicate_identities"]} | {d["same_as"] for d in labels["duplicate_identities"]}]
    for j in range(4):
        p = wrong_pool[j * 11 % len(wrong_pool)]
        true_dob = p["date_of_birth"]
        year = int(true_dob[:4])
        p["date_of_birth"] = "%d%s" % (year + 7, true_dob[4:])
        labels["wrong_records"].append({"cnic": p["cnic"], "field": "date_of_birth",
                                        "record_value": p["date_of_birth"], "true_value": true_dob})

    # Ledger for generated people.
    generated = [p["cnic"] for p in identity[5:80]]
    short_set = set(generated[2::6][:12])      # short-paid by a bad agent
    dup_set = set(generated[4::15][:5])        # paid twice in one month
    none_set = set(generated[8::14][:5])       # nothing paid
    short_order = sorted(short_set)
    for k, cnic in enumerate(generated):
        if cnic in none_set:
            ledger[cnic] = []
            labels["no_payment"].append(cnic)
            continue
        day = 5 + k % 4
        if cnic in short_set:
            slot = short_order.index(cnic) % 3
            agent = BAD_AGENTS[slot]
            paid = [8000, 9000, 10000][slot]
            pid = "pay-2%03d" % k
            ledger[cnic] = [{"payment_id": pid, "amount_pkr": paid, "date": "2026-10-%02d" % day,
                             "agent_id": agent, "programme": PROGRAMME}]
            labels["short_payments"].append({"cnic": cnic, "payment_id": pid, "expected_pkr": EXPECTED_PKR,
                                             "paid_pkr": paid, "agent_id": agent})
            continue
        agent = GOOD_AGENTS[k % len(GOOD_AGENTS)]
        pay = {"payment_id": "pay-2%03d" % k, "amount_pkr": EXPECTED_PKR, "date": "2026-10-%02d" % day,
               "agent_id": agent, "programme": PROGRAMME}
        ledger[cnic] = [pay]
        if cnic in dup_set:
            second = dict(pay, payment_id=pay["payment_id"] + "-b")
            ledger[cnic].append(second)
            labels["duplicate_payments"].append({"cnic": cnic, "payment_ids": [pay["payment_id"], second["payment_id"]]})

    # The 7 demo-scenario people shared with the backend (contracts/fixtures/demo_people.json).
    demo = json.loads(DEMO_PEOPLE.read_text(encoding="utf-8"))
    labels["demo_people"] = []
    for person in demo["people"]:
        cnic = person["cnic"]
        identity.append(dict(person["identity"], cnic=cnic))
        ledger[cnic] = [dict(x) for x in person["payments"]]
        labels["demo_people"].append({"cnic": cnic, "username": person["username"], "key": person["key"]})
        for x in person["payments"]:
            if x["amount_pkr"] < EXPECTED_PKR:
                labels["short_payments"].append({"cnic": cnic, "payment_id": x["payment_id"], "expected_pkr": EXPECTED_PKR,
                                                 "paid_pkr": x["amount_pkr"], "agent_id": x["agent_id"]})
        if not person["payments"]:
            labels["no_payment"].append(cnic)

    senders = {"official": list(demo["official_senders"]), "lookalikes": sorted(set(LOOKALIKES) | set(demo["lookalike_senders"]))}
    labels["official_senders"] = senders["official"]
    labels["scam_senders"] = sorted(set(LOOKALIKES) | set(demo["scam_senders"]))
    labels["bad_agent_note"] = "Short payments cluster on 3 agents: this is the pattern the system should surface."
    return {"identity": identity, "ledger": ledger, "senders": senders, "labels": labels}


def _dump_lines(items: List[Dict[str, Any]]) -> str:
    return "[\n" + ",\n".join("  " + json.dumps(x, ensure_ascii=False) for x in items) + "\n]\n"


def main() -> None:
    out = build()
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "identity.json").write_text(_dump_lines(out["identity"]), encoding="utf-8")
    ledger_lines = ",\n".join('  %s: %s' % (json.dumps(k), json.dumps(v, ensure_ascii=False)) for k, v in out["ledger"].items())
    (DATA / "ledger.json").write_text("{\n" + ledger_lines + "\n}\n", encoding="utf-8")
    (DATA / "senders.json").write_text(json.dumps(out["senders"], indent=2) + "\n", encoding="utf-8")
    (DATA / "labels.json").write_text(json.dumps(out["labels"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("people=%d ledger=%d" % (len(out["identity"]), len(out["ledger"])))


if __name__ == "__main__":
    main()
