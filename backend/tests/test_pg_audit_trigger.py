"""Runs only when a Postgres is available: TEST_POSTGRES_URL=postgresql+psycopg2://user:pw@host:port/db
(the user must be allowed to CREATE DATABASE; the test makes and drops its own database)."""
import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

URL = os.environ.get("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not URL, reason="set TEST_POSTGRES_URL to run the Postgres-only trigger test")
ROOT = Path(__file__).resolve().parents[1]


def test_audit_log_is_append_only_inside_postgres(monkeypatch):
    base = make_url(URL)
    name = "bharosa_trg_%s" % uuid.uuid4().hex[:8]
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text('CREATE DATABASE "%s"' % name))
    target = base.set(database=name).render_as_string(hide_password=False)
    try:
        monkeypatch.setenv("DATABASE_URL", target)
        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "migrations"))
        command.upgrade(cfg, "head")
        eng = create_engine(target)
        with eng.begin() as c:  # INSERT is allowed
            c.execute(text("INSERT INTO audit_log (actor_type, action, entity, created_at) VALUES ('system','test.insert','test', now())"))
        for sql in ("UPDATE audit_log SET action = 'tampered'", "DELETE FROM audit_log", "TRUNCATE audit_log"):
            with pytest.raises(DBAPIError) as e:
                with eng.begin() as c:
                    c.execute(text(sql))
            assert "append-only" in str(e.value), sql
        with eng.connect() as c:
            assert c.execute(text("SELECT count(*), min(action) FROM audit_log")).one() == (1, "test.insert")
        command.downgrade(cfg, "0002")  # the trigger goes away with the migration
        with eng.begin() as c:
            c.execute(text("DELETE FROM audit_log"))
        eng.dispose()
    finally:
        with admin.connect() as c:
            c.execute(text('DROP DATABASE IF EXISTS "%s" WITH (FORCE)' % name))
        admin.dispose()
