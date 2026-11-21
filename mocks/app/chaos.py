"""In-memory chaos switches. Reset with reset(). Not persisted; process-local on purpose."""
from typing import Any, Dict

DEFAULTS: Dict[str, Any] = {
    "timeout": False,
    "error_500": False,
    "missing_record": False,
    "duplicate_payment": False,
    "lookalike_sender": False,
    "slow_network_ms": 0,
}

_state: Dict[str, Any] = dict(DEFAULTS)


def get() -> Dict[str, Any]:
    return dict(_state)


def update(changes: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in changes.items():
        if key in DEFAULTS and value is not None:
            _state[key] = value
    return get()


def reset() -> Dict[str, Any]:
    _state.clear()
    _state.update(DEFAULTS)
    return get()


# Named bundles of switches for the Chaos Panel. "normal" is the same as reset().
PRESETS: Dict[str, Dict[str, Any]] = {
    "normal": {},
    "identity_down": {"error_500": True},
    "bad_day": {"timeout": True, "slow_network_ms": 1500},
    "slow_network": {"slow_network_ms": 2000},
    "scam_wave": {"lookalike_sender": True},
}


def apply_preset(name: str) -> Dict[str, Any]:
    """Reset to defaults, then apply the named preset. Raises KeyError for unknown names."""
    changes = PRESETS[name]
    reset()
    return update(changes)
