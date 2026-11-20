"""Consent checks. Must run BEFORE any mock/identity/payment call.

TODO(Basit): read the consents table; raise ConsentRequired when scope is not granted.
"""
from contracts.enums import ConsentScope


class ConsentRequired(Exception):
    def __init__(self, scope: ConsentScope):
        super().__init__("Consent for '%s' is required" % scope.value)
        self.scope = scope


def require_consent(user_id: str, scope: ConsentScope) -> None:
    # TODO(Basit): real lookup. Prototype: always granted.
    return None
