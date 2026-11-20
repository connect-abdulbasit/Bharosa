"""Local stand-in for /mocks (same 5 seed people as mocks/app/data). Used when MOCKS_URL is empty or unreachable.
Unknown CNICs behave like the real mock: not found -> MockUnavailable."""
import itertools
from typing import Any, Dict, List

from app.services.mock_errors import MockUnavailable

SENDERS = ["9090", "9090-SAHARA", "SAHARA-GOV", "9091", "SAHARA-HELP"]
_PROG = "Sahara Relief Programme"
IDENTITY: Dict[str, Dict[str, Any]] = {
    "0000042101001": {"full_name": "Muhammad Aslam", "father_name": "Abdul Rehman", "date_of_birth": "1984-03-12", "district": "Karachi East", "aliases": ["Mohammad Aslam", "M. Aslam"], "phone_last4": "4471"},
    "0000042101002": {"full_name": "Fatima Noor", "father_name": "Noor Muhammad", "date_of_birth": "1979-07-01", "district": "Karachi West", "aliases": ["Fatima Bibi", "Fatma Noor"], "phone_last4": "9902"},
    "0000042101003": {"full_name": "Zubaida Khatoon", "father_name": "Ghulam Hussain", "date_of_birth": "1968-11-23", "district": "Malir", "aliases": ["Zubeda Khatun"], "phone_last4": "1356"},
    "0000042101004": {"full_name": "Gul Bano", "father_name": "Mir Hassan", "date_of_birth": "1990-01-30", "district": "Korangi", "aliases": ["Gul Bano Bibi"], "phone_last4": "7720"},
    "0000042101005": {"full_name": "Rashid Mehmood", "father_name": "Mehmood Ahmed", "date_of_birth": "1975-09-09", "district": "Karachi Central", "aliases": ["Rasheed Mahmood", "Mohammad Rashid"], "phone_last4": "3085"},
}
LEDGER: Dict[str, List[Dict[str, Any]]] = {
    "0000042101001": [{"payment_id": "pay-1001", "amount_pkr": 8000, "date": "2026-10-05", "agent_id": "agent-017", "programme": _PROG}],
    "0000042101002": [{"payment_id": "pay-1002", "amount_pkr": 12000, "date": "2026-10-05", "agent_id": "agent-017", "programme": _PROG}],
    "0000042101003": [],
    "0000042101004": [{"payment_id": "pay-1004", "amount_pkr": 12000, "date": "2026-09-05", "agent_id": "agent-022", "programme": _PROG}],
    "0000042101005": [{"payment_id": "pay-1005", "amount_pkr": 12000, "date": "2026-10-06", "agent_id": "agent-031", "programme": _PROG}],
}
_tickets = itertools.count(1)


class FakeMocksClient:
    name = "fake"

    def identity(self, cnic: str) -> Dict[str, Any]:
        if cnic not in IDENTITY:
            raise MockUnavailable("GET /identity/%s: record not found" % cnic)
        return dict(IDENTITY[cnic], cnic=cnic, simulated=True)

    def ledger(self, cnic: str) -> Dict[str, Any]:
        if cnic not in LEDGER:
            raise MockUnavailable("GET /ledger/%s: record not found" % cnic)
        return {"cnic": cnic, "payments": [dict(p) for p in LEDGER[cnic]], "simulated": True}

    def complaint(self, cnic: str, category: str, description: str) -> Dict[str, Any]:
        return {"ticket_id": "TKT-FAKE%04d" % next(_tickets), "simulated": True}

    def senders(self) -> Dict[str, Any]:
        return {"senders": list(SENDERS), "simulated": True}

    def notify(self, to: str, message: str, channel: str = "sms") -> Dict[str, Any]:
        return {"message_id": "MSG-FAKE%04d" % next(_tickets), "simulated": True}
