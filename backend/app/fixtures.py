"""Loads contract fixtures. Temporary: routers return these until real logic exists (TODO(Basit))."""
import json
from typing import Any

from app.config import settings


def fixture(name: str) -> Any:
    return json.loads((settings.FIXTURES_DIR / ("%s.json" % name)).read_text(encoding="utf-8"))
