"""LOGIN_RATE_LIMIT: unset = 5/minute, or 30/minute while DEMO_MODE=1; an explicit value always wins."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import default_login_limit

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("explicit,demo,expected", [
    ("", True, "30/minute"), ("", False, "5/minute"), ("7/minute", True, "7/minute"), ("9/hour", False, "9/hour"),
])
def test_default_logic(explicit, demo, expected):
    assert default_login_limit(explicit, demo) == expected


def effective(**env):
    clean = {k: v for k, v in os.environ.items() if k not in ("LOGIN_RATE_LIMIT", "DEMO_MODE")}
    clean.update(env, PYTHONPATH="%s:%s" % (ROOT, ROOT / "ai"))
    out = subprocess.run([sys.executable, "-c", "from app.config import settings; print(settings.LOGIN_RATE_LIMIT)"],
                         cwd=str(ROOT / "backend"), env=clean, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def test_environment_is_honoured_by_the_real_settings_object():
    assert effective() == "30/minute"                                         # nothing set: demo mode is the default
    assert effective(DEMO_MODE="0") == "5/minute"
    assert effective(DEMO_MODE="1", LOGIN_RATE_LIMIT="7/minute") == "7/minute"
    assert effective(DEMO_MODE="0", LOGIN_RATE_LIMIT="9/hour") == "9/hour"
    assert effective(DEMO_MODE="1", LOGIN_RATE_LIMIT="") == "30/minute"        # blank counts as unset
    assert effective(DEMO_MODE="1", LOGIN_RATE_LIMIT="# a comment") == "30/minute"  # so does docker's inline-comment leftover
