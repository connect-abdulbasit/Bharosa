"""Compact JSON for weak connections: every route drops null fields from its response by default."""
from fastapi.routing import APIRoute


class CompactRoute(APIRoute):
    def __init__(self, *args, **kwargs):
        kwargs["response_model_exclude_none"] = True  # FastAPI passes an explicit False, so setdefault would never apply
        super().__init__(*args, **kwargs)
