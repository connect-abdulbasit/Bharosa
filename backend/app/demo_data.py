"""Demo data, loaded from the SHARED fixture contracts/fixtures/demo_people.json (additive; validated by contracts.schemas.DemoPeople).

Used by app/demo.py (accounts, consents, seeded case) and fake_mocks_client.py (identity, ledger, sender codes).
/mocks must load the same file (TODO(Hadi)), so the demo behaves the same with the real mocks. ALL FAKE.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List

PATH = Path(os.environ.get("DEMO_PEOPLE_PATH") or Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "demo_people.json")

_RAW: Dict[str, Any] = json.loads(PATH.read_text(encoding="utf-8"))

STUB_HEARD_NAME: str = _RAW["stub_heard_name"]
PROGRAMME: str = _RAW["programme"]
OFFICIAL_SENDERS: List[str] = list(_RAW["official_senders"])
LOOKALIKE_SENDERS: List[str] = list(_RAW["lookalike_senders"])
SCAM_SENDERS: List[str] = list(_RAW["scam_senders"])
AGENTS: List[Dict[str, str]] = list(_RAW["agents"])
SCENARIOS: List[Dict[str, Any]] = list(_RAW["people"])  # one dict per demo citizen (see contracts.schemas.DemoPerson)

FIRST_SCENARIO_FAMILY = 11  # fam-011 ...

# ---- Scam Map seed: 60 FAKE scam checks over fictional areas. Areas under 3 reports are grouped as 'other' by the API.
SCAM_AREAS = [("Noorabad", 18), ("Sahil Colony", 14), ("Bagh-e-Zubaida", 10), ("Mehran Town North", 8), ("Kausar Basti", 6), ("Tiny Village", 2), (None, 2)]
SCAM_CUES = ["http", "bit.ly", "fee", "urgent", "otp"]
