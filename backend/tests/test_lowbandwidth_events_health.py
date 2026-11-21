import json
import logging

from sqlalchemy import select

from app.config import settings
from app.logging_setup import JsonFormatter
from app.models import AuditLog
from app.services import events
from tests.conftest import auth


# ----------------------------------------------------------------------------- low bandwidth
def test_case_detail_has_etag_and_answers_304(client):
    h = auth(client, "officer")
    first = client.get("/cases/case-0001", headers=h)
    etag = first.headers["ETag"]
    assert etag.startswith('W/"') and first.headers["Cache-Control"] == "private, no-cache"
    again = client.get("/cases/case-0001", headers=dict(h, **{"If-None-Match": etag}))
    assert again.status_code == 304 and again.content == b"" and again.headers["ETag"] == etag
    client.post("/cases/case-0001/assign", json={"officer_id": "u-officer-1"}, headers=auth(client, "admin"))  # state changes -> new representation
    changed = client.get("/cases/case-0001", headers=dict(h, **{"If-None-Match": etag}))
    assert changed.status_code == 200 and changed.headers["ETag"] != etag


def test_queue_etag(client):
    h = auth(client, "officer")
    etag = client.get("/queue", headers=h).headers["ETag"]
    assert client.get("/queue", headers=dict(h, **{"If-None-Match": etag})).status_code == 304
    assert client.get("/queue", headers=dict(h, **{"If-None-Match": '"other"'})).status_code == 200
    assert client.get("/queue", headers=dict(h, **{"If-None-Match": "*"})).status_code == 304


def test_etag_depends_on_who_asks(client):
    a = client.get("/cases/case-0004", headers=auth(client, "citizen")).headers["ETag"]
    assert client.get("/cases/case-0004", headers={**auth(client, "citizen"), "If-None-Match": a}).status_code == 304
    assert client.get("/cases/case-0001", headers=auth(client, "citizen")).status_code == 404  # no ETag games for others' cases


def test_unauthenticated_and_errors_get_no_etag(client):
    assert "ETag" not in client.get("/cases/case-0001").headers
    assert "ETag" not in client.get("/cases/nope", headers=auth(client, "officer")).headers


def test_responses_are_gzipped(client):
    r = client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200 and r.headers["Content-Encoding"] == "gzip" and r.json()["info"]["title"]
    plain = client.get("/openapi.json", headers={"Accept-Encoding": "identity"})
    assert "Content-Encoding" not in plain.headers  # clients that cannot gunzip still work
    with client.stream("GET", "/openapi.json", headers={"Accept-Encoding": "gzip"}) as resp:
        wire = sum(len(chunk) for chunk in resp.iter_raw())  # bytes actually sent (r.content is already decoded)
    assert wire < len(plain.content) / 3


def test_responses_omit_empty_fields(client):
    items = client.get("/cases", headers=auth(client, "officer")).json()["items"]
    unassigned = [i for i in items if i["id"] == "case-0001"][0]
    assert "assigned_to" not in unassigned and all(v is not None for i in items for v in i.values())
    detail = client.get("/cases/case-0004", headers=auth(client, "citizen")).json()
    assert "decision" not in detail and None not in detail.values()


# ----------------------------------------------------------------------------- events
def test_status_change_emits_an_event_and_audit_row(client, db):
    client.post("/cases/case-0004/escalate", json={"reason": "middleman asked for a fee"}, headers=auth(client, "helper"))
    assert len(events.EMITTED) == 1
    ev = events.EMITTED[0]
    assert ev["event"] == "case.status_changed"
    assert ev["payload"]["case_id"] == "case-0004" and ev["payload"]["from"] == "submitted" and ev["payload"]["to"] == "with_officer"
    assert ev["payload"]["by"] == "u-helper-1" and ev["payload"]["action"] == "case.escalate" and ev["payload"]["citizen_id"] == "u-citizen-1"
    row = db.execute(select(AuditLog).where(AuditLog.action == "event.case.status_changed")).scalar_one()
    assert row.actor_type == "system" and row.entity == "event" and row.entity_id == "case-0004" and row.after == ev


def test_no_event_when_the_change_is_rejected(client):
    client.post("/cases/case-0005/close", json={"resolution": "x"}, headers=auth(client, "officer"))  # 409: already closed
    assert len(events.EMITTED) == 0


def test_pipeline_status_changes_emit_too(client, mocks):
    client.post("/claims", json={"transcript": "mujhe is mahine ke paisay nahi mile"}, headers=auth(client, "citizen05"))
    assert [e["payload"]["to"] for e in events.EMITTED] == ["needs_more_proof"]


# ----------------------------------------------------------------------------- monitoring
def test_access_log_has_request_id_role_and_latency(client, caplog):
    h = dict(auth(client, "officer"), **{"X-Request-ID": "log-me-1"})
    with caplog.at_level(logging.INFO, logger="bharosa.access"):
        client.get("/me", headers=h)
        client.get("/me")  # anonymous
    recs = [r for r in caplog.records if r.name == "bharosa.access" and r.path == "/me"]
    assert [(r.status, r.role) for r in recs] == [(200, "officer"), (401, "anonymous")]
    assert isinstance(recs[0].latency_ms, float) and recs[0].method == "GET"


def test_json_formatter_emits_one_valid_json_object_with_request_id():
    from app.services import audit

    token = audit.request_id_var.set("abc123")
    try:
        rec = logging.LogRecord("bharosa.access", logging.INFO, "f", 1, "request", None, None)
        rec.status, rec.latency_ms, rec.role = 200, 1.5, "officer"
        out = json.loads(JsonFormatter().format(rec))
    finally:
        audit.request_id_var.reset(token)
    assert out["request_id"] == "abc123" and out["status"] == 200 and out["role"] == "officer" and out["level"] == "info" and out["ts"].endswith("Z")


def test_health_reports_database_and_mocks(client, monkeypatch):
    r = client.get("/health")
    b = r.json()
    assert r.status_code == 200 and b["status"] == "ok" and b["database"] == "ok" and b["mocks"] == {"mode": "fake", "reachable": True}
    assert b["worker"]["mode"] == "inline" and b["simulated"] is True and b["version"]
    monkeypatch.setattr(settings, "MOCKS_URL", "http://127.0.0.1:9")  # nothing listens there
    from app.services import mocks_client

    monkeypatch.setattr(mocks_client, "_probe", (0.0, None))
    degraded = client.get("/health")
    assert degraded.status_code == 200 and degraded.json()["status"] == "degraded" and degraded.json()["mocks"]["reachable"] is False


def test_health_is_503_when_the_database_is_down(client, monkeypatch):
    def broken():
        raise RuntimeError("db down")

    monkeypatch.setattr("app.main.session_factory", broken)
    r = client.get("/health")
    assert r.status_code == 503 and r.json()["status"] == "down" and r.json()["database"] == "down"


def test_sentry_is_optional(monkeypatch, caplog):
    import asyncio

    from app.main import app, lifespan

    monkeypatch.setattr(settings, "SENTRY_DSN", "https://fake@example.invalid/1")
    monkeypatch.setitem(__import__("sys").modules, "sentry_sdk", None)  # simulate "not installed"

    async def go():
        async with lifespan(app):
            pass

    with caplog.at_level(logging.WARNING, logger="bharosa"):
        asyncio.run(go())
    assert any("sentry-sdk is not installed" in r.getMessage() for r in caplog.records)


# ----------------------------------------------------------------------------- swagger
def test_swagger_is_presentable(client):
    spec = client.get("/openapi.json").json()
    tags = {t["name"]: t.get("description") for t in spec["tags"]}
    assert all(tags.values()) and {"auth", "cases", "claims", "public", "apikeys", "eval", "consent", "rules"} <= set(tags)
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            assert op.get("tags") and set(op["tags"]) <= set(tags), (method, path)
            assert op.get("summary") or op.get("description"), (method, path)
    scheme = spec["components"]["securitySchemes"]["ApiKeyAuth"]
    assert scheme["type"] == "apiKey" and scheme["in"] == "header" and scheme["name"] == "X-API-Key"
    assert {"ApiKeyAuth": []} in spec["paths"]["/public/cases/{case_id}/status"]["get"]["security"]
    assert "X-API-Key" in spec["info"]["description"] and "5/min" in spec["info"]["description"]
    claims = spec["paths"]["/claims"]["post"]
    assert "202" in claims["responses"] and claims["requestBody"]["content"]["application/json"]["examples"]
    assert spec["paths"]["/auth/login"]["post"]["requestBody"]["content"]["application/json"]["examples"]


def test_blank_or_comment_env_values_fall_back_to_defaults(monkeypatch):
    """docker env_file can deliver `KEY=   # comment` as the value '# comment': that must count as unset."""
    from app.config import _env

    monkeypatch.setenv("X_BLANK", "   ")
    monkeypatch.setenv("X_COMMENT", "# optional; needs sentry-sdk")
    monkeypatch.setenv("X_REAL", "  value  ")
    assert _env("X_BLANK", "d") == "d" and _env("X_COMMENT", "d") == "d" and _env("X_REAL", "d") == "value" and _env("X_MISSING", "d") == "d"


def test_a_malformed_sentry_dsn_never_stops_startup(monkeypatch, caplog):
    import asyncio
    import sys
    import types

    from app.main import app, lifespan

    def bad_init(**kw):
        raise ValueError("Unsupported scheme ''")

    monkeypatch.setattr(settings, "SENTRY_DSN", "not-a-dsn")
    monkeypatch.setitem(sys.modules, "sentry_sdk", types.SimpleNamespace(init=bad_init))

    async def go():
        async with lifespan(app):
            return "started"

    with caplog.at_level(logging.WARNING, logger="bharosa"):
        assert asyncio.run(go()) == "started"
    assert any("continuing without it" in r.getMessage() for r in caplog.records)
