"""POST /claims returns 202 at once; the agent runs in a background worker backed by the jobs table."""
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import Job
from app.services import jobs
from tests.conftest import auth

SPEECH = {"transcript": "mujhe is mahine ke paisay nahi mile"}


@pytest.fixture()
def threaded(SessionLocal, monkeypatch, mocks):
    """A client whose app runs the real background worker thread (lifespan starts it)."""
    monkeypatch.setattr(settings, "PIPELINE_MODE", "thread")
    monkeypatch.setattr(settings, "JOB_POLL_SECONDS", 0.05)

    def override():
        with SessionLocal() as s:
            yield s

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def wait_for(client, headers, claim_id, until, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        p = client.get("/claims/%s/progress" % claim_id, headers=headers).json()
        if until(p):
            return p
        time.sleep(0.05)
    raise AssertionError("timed out; last progress: %s" % p)


def test_request_returns_quickly_even_when_the_mock_is_slow(threaded, mocks):
    mocks.delay = {"identity": 2.0, "ledger": 1.0}  # a slow, weak-signal day
    h = auth(threaded, "citizen05")
    started = time.perf_counter()
    r = threaded.post("/claims", json=SPEECH, headers=h)
    elapsed = time.perf_counter() - started
    assert r.status_code == 202 and elapsed < 1.0, elapsed  # the lookups alone take 3 s
    b = r.json()
    assert b["case_id"] and b["claim_id"] and b["finished"] is False and b["progress_url"] == "/claims/%s/progress" % b["claim_id"]
    assert b["current_step"] in ("queued", "extract_claim", "read_document", "identity_lookup")
    final = wait_for(threaded, h, b["claim_id"], lambda p: p["finished"])
    assert final["status"] == "needs_more_proof" and final["steps_done"] == 8 and final["job"] == "done" and final["active"] is False
    assert r.json()["finished"] is False
    assert threaded.get("/claims/%s" % b["claim_id"], headers=h).json()["decision"]["action"] == "ask_more"


def test_progress_polling_is_cheap_with_etag(threaded, mocks):
    mocks.delay = {"identity": 2.0}
    h = auth(threaded, "citizen05")
    cid = threaded.post("/claims", json=SPEECH, headers=h).json()["claim_id"]
    wait_for(threaded, h, cid, lambda p: p["current_step"] == "identity_lookup")  # stable for ~2 s
    first = threaded.get("/claims/%s/progress" % cid, headers=h)
    etag = first.headers["ETag"]
    again = threaded.get("/claims/%s/progress" % cid, headers=dict(h, **{"If-None-Match": etag}))
    assert again.status_code == 304 and again.content == b"" and again.headers["ETag"] == etag
    final = wait_for(threaded, h, cid, lambda p: p["finished"])
    changed = threaded.get("/claims/%s/progress" % cid, headers=dict(h, **{"If-None-Match": etag}))
    assert changed.status_code == 200 and changed.headers["ETag"] != etag and changed.json() == final


def test_resume_works_in_the_background(threaded, mocks):
    mocks.fail = {"identity"}
    h = auth(threaded, "citizen05")
    cid = threaded.post("/claims", json=SPEECH, headers=h).json()["claim_id"]
    p = wait_for(threaded, h, cid, lambda x: x["finished"] is False and x["status"] == "with_officer" and x["job"] == "done")
    assert p["failed"]["step"] == "identity_lookup" and p["active"] is False  # paused: nothing running, so stop polling
    mocks.fail = set()
    r = threaded.post("/claims/%s/resume" % cid, headers=h)
    assert r.status_code == 202
    done = wait_for(threaded, h, cid, lambda x: x["finished"])
    assert done["steps_done"] == 8 and done["status"] == "needs_more_proof"


def test_progress_is_limited_to_people_who_can_see_the_claim(client, mocks):
    cid = client.post("/claims", json=SPEECH, headers=auth(client, "citizen05")).json()["claim_id"]
    assert client.get("/claims/%s/progress" % cid, headers=auth(client, "citizen")).status_code == 404
    assert client.get("/claims/%s/progress" % cid, headers=auth(client, "helper")).status_code == 200
    assert client.get("/claims/nope/progress", headers=auth(client, "helper")).status_code == 404
    assert client.get("/claims/%s/progress" % cid).status_code == 401


def test_inline_mode_progress_shape(client, mocks):
    h = auth(client, "citizen05")
    b = client.post("/claims", json=SPEECH, headers=h).json()
    assert b["finished"] is True and b["current_step"] == "completed"
    p = client.get("/claims/%s/progress" % b["claim_id"], headers=h).json()
    assert p["steps_total"] == 8 and p["steps_done"] == 8 and p["job"] == "done" and [s["step"] for s in p["steps"]][0] == "extract_claim"
    assert "failed" not in p and set(p["steps"][0]) == {"step", "status"}  # compact


def test_each_claim_creates_a_job_row_and_repeat_resume_does_not_duplicate(client, db, mocks):
    mocks.fail = {"identity"}
    h = auth(client, "citizen05")
    b = client.post("/claims", json=SPEECH, headers=h).json()
    assert [j.status for j in db.execute(select(Job)).scalars()] == ["done"]
    mocks.fail = set()
    client.post("/claims/%s/resume" % b["claim_id"], headers=h)
    client.post("/claims/%s/resume" % b["claim_id"], headers=h)  # finished by now: a no-op, no third job
    assert db.query(Job).count() == 2


def test_enqueue_is_idempotent_while_a_job_is_active(client, db, mocks):
    from app.models import Claim

    b = client.post("/claims", json=SPEECH, headers=auth(client, "citizen05")).json()
    claim = db.get(Claim, b["claim_id"])
    db.query(Job).delete()
    db.commit()
    j1 = jobs.enqueue(db, "claim_resume", claim, "u-citizen-5")
    j2 = jobs.enqueue(db, "claim_resume", claim, "u-citizen-5")
    assert j1.id == j2.id


def test_queued_jobs_survive_a_restart_and_are_picked_up(client, db, mocks):
    """The job table is the queue: a job written but never run is processed by the next worker."""
    from app.models import User
    from app.services import pipeline

    citizen = db.get(User, "u-citizen-5")
    case, claim = pipeline.create(db, citizen, citizen, SPEECH["transcript"], None)
    job = jobs.enqueue(db, "claim_start", claim, citizen.id)
    db.commit()  # ...and the process dies here
    assert jobs.process_job() is True  # the "restarted" worker takes the oldest queued job
    db.expire_all()
    assert db.get(Job, job.id).status == "done"
    assert client.get("/claims/%s/progress" % claim.id, headers=auth(client, "citizen05")).json()["finished"] is True
    assert jobs.process_job() is False  # queue empty


def test_stale_running_jobs_are_requeued(client, db, mocks):
    from datetime import timedelta

    from app.models.base import utcnow

    b = client.post("/claims", json=SPEECH, headers=auth(client, "citizen05")).json()
    job = db.execute(select(Job).where(Job.claim_id == b["claim_id"])).scalar_one()
    job.status, job.started_at = "running", utcnow() - timedelta(seconds=settings.JOB_STALE_SECONDS + 60)  # worker died mid-run
    db.commit()
    assert jobs.requeue_stale() == 1
    db.expire_all()
    assert db.get(Job, job.id).status == "queued"


def test_a_job_is_taken_by_exactly_one_worker(client, db, mocks):
    b = client.post("/claims", json=SPEECH, headers=auth(client, "citizen05")).json()
    job = db.execute(select(Job).where(Job.claim_id == b["claim_id"])).scalar_one()
    job.status = "queued"
    db.commit()
    assert jobs._take(db, job.id) is True
    assert jobs._take(db, job.id) is False  # the atomic UPDATE ... WHERE status='queued' lets only one win


def test_background_steps_keep_the_request_id_of_the_request_that_queued_them(threaded, mocks, db):
    """The worker thread has no HTTP request: the job carries the request id so a whole claim is one group in the audit log."""
    from app.models import AuditLog

    h = dict(auth(threaded, "citizen05"), **{"X-Request-ID": "claim-trace-77"})
    b = threaded.post("/claims", json=SPEECH, headers=h).json()
    wait_for(threaded, h, b["claim_id"], lambda p: p["finished"])
    rows = db.execute(select(AuditLog).where(AuditLog.request_id == "claim-trace-77").order_by(AuditLog.id)).scalars().all()
    actions = [r.action for r in rows]
    assert "case.create" in actions and "claim.create" in actions                      # written by the request thread
    assert {"ai.extract_claim", "agent.identity_lookup", "ai.decide", "agent.notify"} <= set(actions)  # written by the worker thread
    steps = db.execute(select(AuditLog).where(AuditLog.entity_id == b["case_id"], AuditLog.actor_type.in_(["ai", "agent"]))).scalars().all()
    assert steps and all(r.request_id == "claim-trace-77" for r in steps)
