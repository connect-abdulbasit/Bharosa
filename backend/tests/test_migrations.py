"""The Alembic migration must create exactly the tables the models declare."""
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.models import Base

ROOT = Path(__file__).resolve().parents[1]


def test_upgrade_head_matches_models(tmp_path, monkeypatch):
    url = "sqlite:///%s" % (tmp_path / "mig.db")
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(cfg, "head")
    insp = inspect(create_engine(url))
    tables = set(insp.get_table_names()) - {"alembic_version"}
    assert tables == set(Base.metadata.tables)
    for name, table in Base.metadata.tables.items():
        assert {c["name"] for c in insp.get_columns(name)} == {c.name for c in table.columns}, name
    command.downgrade(cfg, "base")
    assert set(inspect(create_engine(url)).get_table_names()) == {"alembic_version"}
    assert os.environ["DATABASE_URL"] == url
