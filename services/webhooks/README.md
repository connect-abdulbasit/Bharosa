# Webhooks

HMAC-SHA256 signed, timestamped deliveries; SSRF-safe targets; retry 1/5/30 s then dead-letter; delivery log. Code: `service.py` (`verify()` is for receivers). Served by `services/main.py` at `/webhooks/*` and `/events`.
