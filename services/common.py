"""Shared by notifications and webhooks: bounded retry with dead-letter, and an in-process audit trail."""
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, Tuple

AUDIT: Deque[Dict[str, Any]] = deque(maxlen=1000)  # TODO(Hadi): forward to the backend audit API once it has an ingest endpoint
JOBS: Deque[Dict[str, Any]] = deque(maxlen=1000)
DELAYS: Tuple[float, ...] = (1, 5, 30)             # tests set (0, 0, 0)


def audit(action: str, **data: Any) -> None:
    AUDIT.append({"ts": time.time(), "action": action, "simulated": True, **data})


def retry(name: str, fn: Callable[[], Any]) -> Dict[str, Any]:
    """Run fn up to 1+len(DELAYS) times with backoff. Never loops forever: ends as `done` or `dead` (needs a human)."""
    job: Dict[str, Any] = {"name": name, "status": "dead", "attempts": 0, "error": None}
    for i in range(len(DELAYS) + 1):
        job["attempts"] = i + 1
        try:
            job["result"], job["status"], job["error"] = fn(), "done", None
            break
        except Exception as exc:  # any failure is retried, then handed to a human
            job["error"] = str(exc)[:200]
            if i < len(DELAYS):
                time.sleep(DELAYS[i])
    JOBS.append(job)
    audit("job." + job["status"], job=name, attempts=job["attempts"], error=job["error"])
    return job
