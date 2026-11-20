"""Local stand-in for /mocks that returns contract shapes. Used when MOCKS_URL is empty."""
from typing import Any, Dict

SENDERS = ["9090", "9090-SAHARA", "SAHARA-GOV", "9091", "SAHARA-HELP"]


class FakeMocksClient:
    def identity(self, cnic: str) -> Dict[str, Any]:
        return {"cnic": cnic, "full_name": "Muhammad Aslam", "father_name": "Abdul Rehman",
                "date_of_birth": "1984-03-12", "district": "Karachi East",
                "aliases": ["Mohammad Aslam"], "phone_last4": "4471", "simulated": True}

    def ledger(self, cnic: str) -> Dict[str, Any]:
        return {"cnic": cnic, "payments": [{"payment_id": "pay-1001", "amount_pkr": 8000,
                "date": "2026-10-05", "agent_id": "agent-017", "programme": "Sahara Relief Programme"}],
                "simulated": True}

    def complaint(self, cnic: str, category: str, description: str) -> Dict[str, Any]:
        return {"ticket_id": "TKT-FAKE0001", "simulated": True}

    def senders(self) -> Dict[str, Any]:
        return {"senders": list(SENDERS), "simulated": True}

    def notify(self, to: str, message: str, channel: str = "sms") -> Dict[str, Any]:
        return {"message_id": "MSG-FAKE0001", "simulated": True}
