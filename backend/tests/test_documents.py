from sqlalchemy import select

from app.config import settings
from app.models import AuditLog, Document
from tests.conftest import auth

SHARP = b"\x89PNG\r\n\x1a\n" + b"1" * 400      # stub OCR: readable
TINY = b"\x89PNG\r\n\x1a\n" + b"1" * 20        # stub OCR: unreadable/blurry
SPEECH = {"transcript": "mujhe is mahine ke paisay nahi mile"}


def upload(client, data=SHARP, who="citizen05", name="id.png", **form):
    return client.post("/documents", files={"file": (name, data, "image/png")}, data=form, headers=auth(client, who))


def test_upload_reads_the_card_and_stores_the_file(client, db):
    r = upload(client)
    b = r.json()
    assert r.status_code == 200 and b["format_ok"] and b["retake_needed"] is False and b["fields"]["name"] and b["model_version"]
    doc = db.get(Document, b["document_id"])
    assert doc.owner_id == "u-citizen-5" and doc.case_id is None and (settings.UPLOAD_DIR / doc.file_path).read_bytes() == SHARP
    assert db.execute(select(AuditLog).where(AuditLog.action == "ai.read_document")).scalars().first().after["blur_score"] is not None


def test_blurry_photo_asks_for_a_retake(client):
    b = upload(client, TINY).json()
    assert b["retake_needed"] is True and b["blur_score"] > 0.5 and "retake" in b["explanation_en"].lower()


def test_only_real_images_and_sane_sizes(client, monkeypatch):
    assert upload(client, b"MZ\x90\x00 this is an exe", name="evil.png").status_code == 415
    assert upload(client, b"<html>", name="x.png").status_code == 415
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 100)
    assert upload(client, SHARP).status_code == 413


def test_helper_must_name_a_linked_citizen(client):
    assert upload(client, who="helper").status_code == 422
    assert upload(client, who="helper", citizen_id="u-citizen-11").status_code == 403
    assert upload(client, who="helper", citizen_id="u-citizen-5").status_code == 200
    assert upload(client, who="officer").status_code == 403


def test_claim_attaches_the_document(client, db, mocks):
    doc = upload(client).json()["document_id"]
    b = client.post("/claims", json=dict(SPEECH, document_id=doc), headers=auth(client, "citizen05")).json()
    assert b["status"] == "needs_more_proof" and [s["status"] for s in b["pipeline_steps"]].count("done") == 8
    assert db.get(Document, doc).case_id == b["case_id"]
    again = client.post("/claims", json=dict(SPEECH, document_id=doc), headers=auth(client, "citizen06"))
    assert again.status_code == 422  # someone else's / already used


def test_blurry_document_in_a_claim_asks_for_a_retake_not_a_human(client, mocks):
    doc = upload(client, TINY).json()["document_id"]
    b = client.post("/claims", json=dict(SPEECH, document_id=doc), headers=auth(client, "citizen05")).json()
    assert b["status"] == "needs_more_proof" and "Retake" in b["explanation_en"]
    assert any("Retake" in n for n in b["decision"]["trace"]["needs"])


def test_cannot_attach_another_citizens_document(client, mocks):
    doc = upload(client, who="citizen06").json()["document_id"]
    r = client.post("/claims", json=dict(SPEECH, document_id=doc), headers=auth(client, "citizen05"))
    assert r.status_code == 422
