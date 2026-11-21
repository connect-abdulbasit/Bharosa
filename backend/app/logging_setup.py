"""Structured JSON logs: one line per event, request_id on everything."""
import json
import logging
import sys
from datetime import datetime, timezone

from app.config import settings
from app.services import audit

_STD = set(logging.LogRecord("x", 0, "x", 0, "", None, None).__dict__) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z", "level": record.levelname.lower(),
               "logger": record.name, "msg": record.getMessage(), "request_id": audit.request_id_var.get()}
        for k, v in record.__dict__.items():
            if k not in _STD and v is not None:
                out[k] = v
        if record.exc_info:
            out["exception"] = self.formatException(record.exc_info)  # full trace goes to the LOG only
        return json.dumps(out, default=str, ensure_ascii=False)


def setup() -> None:
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)  # add, never replace: keeps pytest/uvicorn handlers working
    root.setLevel(settings.LOG_LEVEL.upper())
    logging.getLogger("uvicorn.access").disabled = True  # replaced by our own access log (with role + latency)
