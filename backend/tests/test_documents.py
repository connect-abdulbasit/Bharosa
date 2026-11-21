"""ID photos live in Postgres (documents_blob): validated, resized to <= 1280 px, re-encoded JPEG q80 (< 2 MB), served with the case's RBAC."""
import io

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import bharosa_ai
from app.config import settings
from app.models import AuditLog, Document, DocumentBlob
from contracts.ai_interface import DocumentReading
from tests.conftest import auth, make_image

SPEECH = {"transcript": "mujhe is mahine ke paisay nahi mile"}


def upload(client, data=None, who="citizen05", name="id.jpg", ctype="image/jpeg", **form):
    data = data if data is not None else make_image(800, 600, "JPEG")
    return client.post("/documents", files={"file": (name, data, ctype)}, data=form, headers=auth(client, who))


def blurry(monkeypatch):
    monkeypatch.setattr(bharosa_ai, "read_document", lambda b: DocumentReading(fields={}, blur_score=0.9, format_ok=True, confidence=0.3, model_version="t"))


# ----------------------------------------------------------------------------- storage + resize
def test_photo_is_resized_and_stored_in_the_database(client, db):
    big = make_image(2400, 1800, "JPEG")  # like a phone camera
    r = upload(client, big)
    b = r.json()
    assert r.status_code == 200 and b["format_ok"] and b["retake_needed"] is False and b["image_url"] == "/documents/%s/image" % b["document_id"]
    blob = db.get(DocumentBlob, b["document_id"])
    stored = Image.open(io.BytesIO(blob.content))
    assert stored.format == "JPEG" and (blob.width, blob.height) == (1280, 960) and stored.size == (1280, 960)
    assert blob.size_bytes == len(blob.content) <= settings.MAX_DOCUMENT_BYTES and blob.content_type == "image/jpeg"
    assert len(blob.content) < len(big)
    doc = db.get(Document, b["document_id"])
    assert doc.owner_id == "u-citizen-5" and doc.case_id is None and doc.file_path is None  # no disk copy by default
    up = db.execute(select(AuditLog).where(AuditLog.action == "document.upload")).scalar_one()
    assert up.after["bytes_in"] == len(big) and up.after["bytes_stored"] == len(blob.content) and up.after["size"] == "1280x960"


def test_small_images_are_never_upscaled_and_png_becomes_jpeg(client, db):
    b = upload(client, make_image(400, 300, "PNG"), name="id.png", ctype="image/png").json()
    blob = db.get(DocumentBlob, b["document_id"])
    assert (blob.width, blob.height) == (400, 300) and blob.content[:3] == b"\xff\xd8\xff"


def test_exif_is_applied_then_removed(client, db):
    from PIL import Image as I

    exif = I.Exif()
    exif[0x010F] = "FakeCam"        # camera make
    exif[0x0112] = 6                # rotated 90 degrees
    b = upload(client, make_image(1000, 500, "JPEG", exif=exif.tobytes())).json()
    stored = Image.open(io.BytesIO(db.get(DocumentBlob, b["document_id"]).content))
    assert stored.size == (500, 1000)                 # the rotation was applied
    assert len(stored.getexif()) == 0 and b"FakeCam" not in db.get(DocumentBlob, b["document_id"]).content  # location/camera data is gone


def test_transparent_png_is_flattened(client, db):
    img = Image.new("RGBA", (200, 100), (255, 0, 0, 0))
    out = io.BytesIO()
    img.save(out, "PNG")
    assert upload(client, out.getvalue(), name="a.png", ctype="image/png").status_code == 200


def test_stored_size_cap_is_enforced_by_resizing_harder_then_rejecting(client, db, monkeypatch):
    monkeypatch.setattr(settings, "MAX_DOCUMENT_BYTES", 40_000)
    b = upload(client, make_image(1600, 1200, "JPEG")).json()
    assert db.get(DocumentBlob, b["document_id"]).size_bytes <= 40_000  # it shrank until it fit
    monkeypatch.setattr(settings, "MAX_DOCUMENT_BYTES", 300)  # impossible
    r = upload(client, make_image(800, 600, "JPEG"))
    assert r.status_code == 413 and "too large even after shrinking" in r.json()["message"]


def test_database_refuses_blobs_over_2mb(db):
    doc = Document(owner_id="u-citizen-5", kind="id_card")
    db.add(doc)
    db.flush()
    db.add(DocumentBlob(document_id=doc.id, content=b"x", content_type="image/jpeg", size_bytes=2 * 1024 * 1024 + 1, width=1, height=1))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_only_real_images_and_sane_sizes(client, monkeypatch):
    assert upload(client, b"MZ\x90\x00 this is an exe", name="evil.png", ctype="image/png").status_code == 415
    garbage = upload(client, b"\x89PNG\r\n\x1a\n" + b"not really a png", name="x.png", ctype="image/png")  # right magic, not an image
    assert garbage.status_code == 415 and "not a readable photo" in garbage.json()["message"]
    bomb = io.BytesIO()
    Image.new("1", (8000, 8000)).save(bomb, "PNG")  # 64 megapixels: decompression bomb
    assert upload(client, bomb.getvalue(), name="b.png", ctype="image/png").status_code == 415
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 100)
    assert upload(client).status_code == 413


def test_blurry_photo_asks_for_a_retake(client, monkeypatch):
    blurry(monkeypatch)
    b = upload(client).json()
    assert b["retake_needed"] is True and b["blur_score"] > 0.5 and "retake" in b["explanation_en"].lower()


def test_helper_must_name_a_linked_citizen(client):
    assert upload(client, who="helper").status_code == 422
    assert upload(client, who="helper", citizen_id="u-citizen-11").status_code == 403
    assert upload(client, who="helper", citizen_id="u-citizen-5").status_code == 200
    assert upload(client, who="officer").status_code == 403


# ----------------------------------------------------------------------------- serving: RBAC like the case
def test_image_access_follows_the_case_rules(client, db):
    doc = upload(client, who="citizen05").json()["document_id"]  # belongs to u-citizen-5 (linked to the helper)
    url = "/documents/%s/image" % doc
    for who in ("citizen05", "helper", "officer", "admin", "auditor"):
        r = client.get(url, headers=auth(client, who))
        assert r.status_code == 200, who
        assert r.headers["content-type"] == "image/jpeg" and r.headers["cache-control"] == "private, no-store"
        assert r.headers["x-content-type-options"] == "nosniff" and Image.open(io.BytesIO(r.content)).format == "JPEG"
    assert client.get(url, headers=auth(client, "citizen06")).status_code == 404   # another citizen: 404, not 403/200
    assert client.get(url, headers=auth(client, "citizen")).status_code == 404
    assert client.get(url).status_code == 401
    assert client.get("/documents/nope/image", headers=auth(client, "officer")).status_code == 404
    views = db.execute(select(AuditLog).where(AuditLog.action == "document.view").order_by(AuditLog.id)).scalars().all()
    assert [v.actor_id for v in views] == ["u-citizen-5", "u-helper-1", "u-officer-1", "u-admin-1", "u-auditor-1"]  # every view is on record


def test_a_helper_cannot_see_an_unlinked_citizens_photo(client):
    # u-citizen-11 is NOT linked to the helper
    doc = client.post("/documents", files={"file": ("a.jpg", make_image(300, 200, "JPEG"), "image/jpeg")}, headers=auth(client, "citizen11")).json()["document_id"]
    assert client.get("/documents/%s/image" % doc, headers=auth(client, "helper")).status_code == 404
    assert client.get("/documents/%s/image" % doc, headers=auth(client, "officer")).status_code == 200


def test_photo_survives_a_redeploy_because_it_is_in_the_database(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "gone")
    doc = upload(client).json()["document_id"]
    assert not (tmp_path / "gone").exists()                       # nothing was written to disk
    import shutil

    shutil.rmtree(tmp_path / "gone", ignore_errors=True)         # "the free host wiped its disk"
    assert client.get("/documents/%s/image" % doc, headers=auth(client, "citizen05")).status_code == 200


def test_disk_is_only_an_optional_cache(client, db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_DISK_CACHE", True)
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "cache")
    doc = upload(client).json()["document_id"]
    cached = tmp_path / "cache" / (doc + ".jpg")
    assert cached.exists() and cached.read_bytes() == db.get(DocumentBlob, doc).content
    cached.write_bytes(b"cache is not the source of truth")  # a stale cache is only used if present...
    assert client.get("/documents/%s/image" % doc, headers=auth(client, "citizen05")).content == b"cache is not the source of truth"
    cached.unlink()
    again = client.get("/documents/%s/image" % doc, headers=auth(client, "citizen05"))  # ...and the database answers when it is gone
    assert again.status_code == 200 and again.content == db.get(DocumentBlob, doc).content


# ----------------------------------------------------------------------------- the claim pipeline reads the stored photo
def test_claim_attaches_and_reads_the_stored_photo(client, db, mocks, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "none")
    doc = upload(client).json()["document_id"]
    b = client.post("/claims", json=dict(SPEECH, document_id=doc), headers=auth(client, "citizen05")).json()
    assert b["status"] == "needs_more_proof" and [s["status"] for s in b["pipeline_steps"]].count("done") == 8
    assert db.get(Document, doc).case_id == b["case_id"]
    assert client.post("/claims", json=dict(SPEECH, document_id=doc), headers=auth(client, "citizen06")).status_code == 422  # used / not theirs


def test_blurry_document_in_a_claim_asks_for_a_retake_not_a_human(client, mocks, monkeypatch):
    doc = upload(client).json()["document_id"]
    blurry(monkeypatch)
    b = client.post("/claims", json=dict(SPEECH, document_id=doc), headers=auth(client, "citizen05")).json()
    assert b["status"] == "needs_more_proof" and "Retake" in b["explanation_en"]
    assert any("Retake" in n for n in b["decision"]["trace"]["needs"])


def test_cannot_attach_another_citizens_document(client, mocks):
    doc = upload(client, who="citizen06").json()["document_id"]
    assert client.post("/claims", json=dict(SPEECH, document_id=doc), headers=auth(client, "citizen05")).status_code == 422
