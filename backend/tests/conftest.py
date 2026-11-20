import os

os.environ["BCRYPT_ROUNDS"] = "4"  # fast hashing in tests; must be set before app import
os.environ["DATABASE_URL"] = "sqlite://"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import seed  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

ROLES = ["citizen", "helper", "officer", "admin", "auditor"]
# Seeded ids (deterministic, see app/seed.py)
CITIZEN1 = "u-citizen-1"      # demo citizen, linked to the helper, owns case-0004 (submitted)
CITIZEN2 = "u-citizen-2"      # linked, owns case-0001 (with_officer)
UNLINKED = "u-citizen-11"     # NOT linked to the helper, owns case-0005 (closed)


@pytest.fixture()
def SessionLocal():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with maker() as db:
        seed.run(db)
    yield maker
    engine.dispose()


@pytest.fixture()
def db(SessionLocal):
    with SessionLocal() as session:
        yield session


@pytest.fixture()
def client(SessionLocal):
    def override():
        with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def password_for(username: str) -> str:
    role = username if username in settings.DEMO_PASSWORDS else "citizen"
    return settings.DEMO_PASSWORDS[role]


def auth(client, username: str) -> dict:
    r = client.post("/auth/login", json={"username": username, "password": password_for(username)})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


class ScriptedMocks:
    """Stand-in for the mocks service whose answers (and failures) a test controls. Records every call."""

    name = "scripted"

    def __init__(self, identity=None, payments=None, fail=None, senders=None):
        self.identity_rec = identity or {"full_name": "Muhammad Aslam", "aliases": ["Mohammad Aslam"], "father_name": "Abdul Rehman"}
        self.payments = payments if payments is not None else []
        self.fail = set(fail or [])
        self.official = senders or ["9090", "9090-SAHARA", "SAHARA-GOV"]
        self.calls = []

    def _go(self, name):
        from app.services.mock_errors import MockUnavailable

        self.calls.append(name)
        if name in self.fail:
            raise MockUnavailable("%s timed out (simulated)" % name)

    def identity(self, cnic):
        self._go("identity")
        return dict(self.identity_rec, cnic=cnic, simulated=True)

    def ledger(self, cnic):
        self._go("ledger")
        return {"cnic": cnic, "payments": list(self.payments), "simulated": True}

    def complaint(self, cnic, category, description):
        self._go("complaint")
        return {"ticket_id": "TKT-TEST0001", "simulated": True}

    def senders(self):
        self._go("senders")
        return {"senders": list(self.official), "simulated": True}

    def notify(self, to, message, channel="sms"):
        self._go("notify")
        return {"message_id": "MSG-TEST0001", "simulated": True}


@pytest.fixture()
def mocks(monkeypatch):
    m = ScriptedMocks()
    for mod in ("claims", "cases", "messages"):
        monkeypatch.setattr("app.routers.%s.get_mocks_client" % mod, lambda: m)
    return m


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "uploads")
