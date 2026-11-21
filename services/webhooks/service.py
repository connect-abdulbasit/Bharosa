"""Signed webhooks: subscribe, HMAC-SHA256 sign (timestamped), SSRF-safe targets, retry then dead-letter, delivery log."""
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import socket
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from services.common import audit, retry

SUBS: Dict[str, Dict[str, Any]] = {}
LOG: List[Dict[str, Any]] = []
EVENTS = {"case.created", "case.decided", "case.status_changed", "consent.withdrawn"}  # case.status_changed is what the backend emits today


def sign(secret: str, ts: int, body: bytes) -> str:
    return "t=%d,v1=%s" % (ts, hmac.new(secret.encode(), b"%d." % ts + body, hashlib.sha256).hexdigest())


def verify(secret: str, header: str, body: bytes, tolerance: int = 300, now: Optional[float] = None) -> bool:
    """For receivers: rejects a changed body, a wrong secret and an old timestamp (replay)."""
    try:
        ts = int(dict(p.split("=", 1) for p in header.split(","))["t"])
    except (ValueError, KeyError):
        return False
    return abs((now or time.time()) - ts) <= tolerance and hmac.compare_digest(sign(secret, ts, body), header)


def safe_url(url: str) -> bool:
    """http/https only; no loopback/private targets unless WEBHOOKS_ALLOW_LOCAL=1 (demo). Limit: DNS rebinding is not covered."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        return False
    if os.environ.get("WEBHOOKS_ALLOW_LOCAL") == "1":
        return True
    try:
        ips = {ipaddress.ip_address(a[4][0]) for a in socket.getaddrinfo(u.hostname, None)}
    except (socket.gaierror, ValueError):
        return False
    return not any(i.is_private or i.is_loopback or i.is_link_local or i.is_reserved for i in ips)


def subscribe(url: str, events: List[str]) -> Dict[str, Any]:
    if not safe_url(url):
        raise ValueError("url not allowed")
    if not events or not set(events) <= EVENTS:
        raise ValueError("unknown event")
    sub = {"id": "wh-" + uuid.uuid4().hex[:8], "url": url, "events": sorted(events), "secret": secrets.token_urlsafe(24)}
    SUBS[sub["id"]] = sub
    audit("webhook.subscribed", id=sub["id"], url=url, events=sub["events"])
    return sub  # the secret is shown once, here only


def deliver(sub: Dict[str, Any], event: str, payload: Dict[str, Any], post: Optional[Callable] = None) -> Dict[str, Any]:
    body = json.dumps({"event": event, "payload": payload, "simulated": True}, separators=(",", ":")).encode()
    headers = {"Content-Type": "application/json", "X-Bharosa-Event": event}

    def attempt() -> int:
        headers["X-Bharosa-Signature"] = sign(sub["secret"], int(time.time()), body)  # fresh timestamp per try
        r = (post or httpx.post)(sub["url"], content=body, headers=headers, timeout=5)
        r.raise_for_status()
        return r.status_code

    job = retry("webhook:%s:%s" % (sub["id"], event), attempt)
    rec = {"sub": sub["id"], "event": event, "status": "delivered" if job["status"] == "done" else "dead",
           "attempts": job["attempts"], "error": job["error"], "simulated": True}
    LOG.append(rec)
    audit("webhook." + rec["status"], sub=sub["id"], event=event)
    return rec


def dispatch(event: str, payload: Dict[str, Any], post: Optional[Callable] = None) -> List[Dict[str, Any]]:
    """One thread per subscriber: a dead receiver retrying for ~36 s must not delay everyone else."""
    targets = [s for s in list(SUBS.values()) if event in s["events"]]
    with ThreadPoolExecutor(max_workers=max(1, len(targets))) as pool:
        return list(pool.map(lambda s: deliver(s, event, payload, post), targets))
