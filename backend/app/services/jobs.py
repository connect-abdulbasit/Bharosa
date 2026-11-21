"""Background jobs for the claim pipeline: a small in-process worker + a database job table.

Why a table: a queued claim must survive a restart/deploy (weak infrastructure, weak signal). Claiming a job is one
atomic `UPDATE ... WHERE status='queued'`, so several processes can run workers safely.
PIPELINE_MODE=thread (default) runs the worker thread; PIPELINE_MODE=inline runs the job inside submit() (tests).
"""
import logging
import threading
from datetime import timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.db import session_factory
from app.models import Case, Claim, Job, User
from app.models.base import utcnow
from app.services import pipeline
from app.services import rules as rule_service
from app.services.mocks_client import get_mocks_client

log = logging.getLogger("bharosa.jobs")
ACTIVE = ("queued", "running")
MAX_ATTEMPTS = 3


def enqueue(db: Session, kind: str, claim: Claim, actor_id: str) -> Job:
    """Add a job unless one is already queued/running for this claim (idempotent for retrying clients)."""
    existing = db.execute(select(Job).where(Job.claim_id == claim.id, Job.status.in_(ACTIVE))).scalars().first()
    if existing is not None:
        return existing
    job = Job(kind=kind, claim_id=claim.id, actor_id=actor_id, status="queued")
    db.add(job)
    db.flush()
    return job


def latest_status(db: Session, claim_id: str) -> Optional[str]:
    return db.execute(select(Job.status).where(Job.claim_id == claim_id).order_by(Job.created_at.desc())).scalars().first()


def _take(db: Session, job_id: str) -> bool:
    res = db.execute(update(Job).where(Job.id == job_id, Job.status == "queued")
                     .values(status="running", started_at=utcnow(), attempts=Job.attempts + 1))
    db.commit()
    return res.rowcount == 1


def _run(db: Session, job: Job) -> None:
    claim = db.get(Claim, job.claim_id)
    case = db.get(Case, claim.case_id)
    ctx = pipeline.make_ctx(db, db.get(User, job.actor_id), db.get(User, case.citizen_id), case, claim, get_mocks_client(),
                            rule_service.get_active_rule(db))
    pipeline.run(ctx)  # never raises for step problems: it pauses and hands the case to an officer


def process_job(job_id: Optional[str] = None) -> bool:
    """Run one queued job (the given one, or the oldest). Returns False when there was nothing to do."""
    with session_factory()() as db:
        if job_id is None:
            job_id = db.execute(select(Job.id).where(Job.status == "queued").order_by(Job.created_at)).scalars().first()
            if job_id is None:
                return False
        if not _take(db, job_id):
            return True  # another worker got it
        job = db.get(Job, job_id)
        try:
            _run(db, job)
            job.status, job.error = "done", None
        except Exception as exc:  # pragma: no cover - the pipeline already converts failures
            db.rollback()
            log.exception("job %s crashed", job_id)
            job = db.get(Job, job_id)
            job.status, job.error = ("queued" if job.attempts < MAX_ATTEMPTS else "failed"), str(exc)[:300]
        job.finished_at = utcnow()
        db.commit()
        return True


def requeue_stale() -> int:
    """After a crash/restart: jobs left 'running' too long go back to the queue."""
    with session_factory()() as db:
        cutoff = utcnow() - timedelta(seconds=settings.JOB_STALE_SECONDS)
        res = db.execute(update(Job).where(Job.status == "running", Job.started_at < cutoff).values(status="queued"))
        db.commit()
        return res.rowcount or 0


class Worker:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._wake = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="bharosa-pipeline-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None

    def wake(self) -> None:
        self._wake.set()

    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _loop(self) -> None:
        try:
            n = requeue_stale()
            if n:
                log.warning("re-queued %d stale jobs", n)
        except Exception:
            log.exception("could not re-queue stale jobs")
        while not self._stop.is_set():
            try:
                did = process_job()
            except Exception:
                log.exception("worker error")
                did = False
            if not did:
                self._wake.wait(settings.JOB_POLL_SECONDS)
                self._wake.clear()


worker = Worker()


def submit(job_id: str) -> None:
    """Hand a committed job to the worker (or run it now in inline mode)."""
    if settings.PIPELINE_MODE == "inline":
        process_job(job_id)
    else:
        worker.wake()
