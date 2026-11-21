"""HTTP client for /mocks. Callers must have checked consent first.

get_mocks_client(): the real mocks when MOCKS_URL is set AND reachable, otherwise the in-process fake client.
Failures (timeout, 5xx, 404) raise MockUnavailable; the pipeline turns them into a `with_officer` case
with notes, NEVER a 500 to the user.
"""
import logging
import time
from typing import Any, Dict, Optional, Tuple

import httpx

from app.config import settings
from app.fake_mocks_client import FakeMocksClient, _outage
from app.services.mock_errors import MockUnavailable

log = logging.getLogger("bharosa.mocks")
__all__ = ["MockUnavailable", "MocksClient", "get_mocks_client"]


class MocksClient:
    name = "real"

    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _call(self, method: str, path: str, **kw: Any) -> Dict[str, Any]:
        try:
            r = httpx.request(method, self.base_url + path, timeout=self.timeout, **kw)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MockUnavailable("%s %s failed: %s" % (method, path, (str(exc).splitlines() or ["error"])[0]))

    def identity(self, cnic: str) -> Dict[str, Any]:
        return self._call("GET", "/identity/%s" % cnic)

    def ledger(self, cnic: str) -> Dict[str, Any]:
        return self._call("GET", "/ledger/%s" % cnic)

    def complaint(self, cnic: str, category: str, description: str) -> Dict[str, Any]:
        return self._call("POST", "/complaints", json={"cnic": cnic, "category": category, "description": description})

    def senders(self) -> Dict[str, Any]:
        return self._call("GET", "/senders")

    def disburse(self, case_id: str, cnic: str, amount_pkr: int, idempotency_key: str) -> Dict[str, Any]:
        """Pay out through POST /payments/disburse. The mocks service may not have that endpoint yet
        (TODO(Hadi)): on 404 fall back to the /complaints top-up ticket, which is what we used before.
        The same idempotency_key must never pay twice (the endpoint is expected to honour it)."""
        _outage("payments_down", "POST /payments/disburse")  # Chaos Panel: the mocks have no payout-only switch, so it is enforced here
        try:
            r = httpx.post(self.base_url + "/payments/disburse", timeout=self.timeout, headers={"Idempotency-Key": idempotency_key},
                           json={"case_id": case_id, "cnic": cnic, "amount_pkr": amount_pkr, "idempotency_key": idempotency_key})
        except httpx.HTTPError as exc:
            raise MockUnavailable("POST /payments/disburse failed: %s" % (str(exc).splitlines() or ["error"])[0])
        if r.status_code == 404:
            res = self.complaint(cnic, "payment_topup", "Approved top-up of PKR %d for case %s (key %s)" % (amount_pkr, case_id, idempotency_key))
            return {"payment_ref": res["ticket_id"], "via": "complaints_fallback", "duplicate": False, "simulated": True}
        try:
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MockUnavailable("POST /payments/disburse failed: %s" % (str(exc).splitlines() or ["error"])[0])
        return {"payment_ref": data.get("payment_ref"), "via": "payments", "duplicate": bool(data.get("duplicate")), "simulated": True}

    def notify(self, to: str, message: str, channel: str = "sms") -> Dict[str, Any]:
        return self._call("POST", "/notify", json={"to": to, "message": message, "channel": channel})


_probe: Tuple[float, Optional[bool]] = (0.0, None)


def _reachable(url: str) -> bool:
    """/health is never affected by chaos switches, so this only detects a mocks service that is not running."""
    global _probe
    now = time.time()
    if _probe[1] is not None and now - _probe[0] < 10:
        return bool(_probe[1])
    try:
        httpx.get(url.rstrip("/") + "/health", timeout=1.0).raise_for_status()
        ok = True
    except (httpx.HTTPError, ValueError):
        ok = False
    _probe = (now, ok)
    return ok


def get_mocks_client():
    if settings.MOCKS_URL:
        if _reachable(settings.MOCKS_URL):
            return MocksClient(settings.MOCKS_URL)
        log.warning("MOCKS_URL=%s is unreachable: using the in-process fake mocks client", settings.MOCKS_URL)
    return FakeMocksClient()


def mocks_status() -> dict:
    """For /health: which mocks are in use and whether the real ones answer."""
    if not settings.MOCKS_URL:
        return {"mode": "fake", "reachable": True}
    ok = _reachable(settings.MOCKS_URL)
    return {"mode": "real" if ok else "fake (real unreachable)", "reachable": ok, "url": settings.MOCKS_URL}


def push_real_chaos(flags: dict) -> None:
    """Chaos Panel -> the REAL mocks service (no-op with the fake client, which reads the flags itself).
    identity_down -> error_500, ledger_down -> missing_record (the mocks' switches are global, so the claim pauses at the first lookup)."""
    if not settings.MOCKS_URL or not _reachable(settings.MOCKS_URL):
        return
    import os
    headers = {"X-Chaos-Token": os.environ["MOCKS_CHAOS_TOKEN"]} if os.environ.get("MOCKS_CHAOS_TOKEN") else {}
    try:
        httpx.post(settings.MOCKS_URL.rstrip("/") + "/chaos", timeout=3.0, headers=headers,
                   json={"error_500": bool(flags.get("identity_down")), "missing_record": bool(flags.get("ledger_down"))}).raise_for_status()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("could not forward chaos to the real mocks: %s", exc)
