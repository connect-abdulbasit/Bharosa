from tests.conftest import UNLINKED, auth


def test_citizen_cannot_see_another_citizens_case(client):
    h = auth(client, "citizen")  # u-citizen-1 owns case-0004 only
    assert client.get("/cases/case-0001", headers=h).status_code == 404   # citizen-2's
    assert client.get("/cases/case-0005", headers=h).status_code == 404   # unlinked citizen's
    ids = {c["id"] for c in client.get("/cases", headers=h).json()["items"]}
    assert ids == {"case-0004"}


def test_citizen_cannot_act_on_another_citizens_case(client):
    h = auth(client, "citizen")
    assert client.post("/cases/case-0001/escalate", json={"reason": "x"}, headers=h).status_code == 403  # role
    assert client.get("/cases/case-0001", headers=h).status_code == 404


def test_citizen_cannot_create_case_for_someone_else(client):
    h = auth(client, "citizen")
    r = client.post("/cases", json={"claim_type": "missing", "amount_claimed_pkr": 1, "citizen_id": "u-citizen-2"}, headers=h)
    assert r.status_code == 403


def test_helper_sees_linked_but_not_unlinked(client):
    h = auth(client, "helper")
    ids = {c["id"] for c in client.get("/cases", headers=h).json()["items"]}
    assert ids == {"case-0001", "case-0002", "case-0003", "case-0004"}
    assert "case-0005" not in ids
    assert client.get("/cases/case-0005", headers=h).status_code == 404
    assert client.get("/cases/case-0001", headers=h).status_code == 200


def test_helper_cannot_create_or_escalate_for_unlinked(client):
    h = auth(client, "helper")
    r = client.post("/cases", json={"claim_type": "missing", "amount_claimed_pkr": 1, "citizen_id": UNLINKED}, headers=h)
    assert r.status_code == 403
    assert client.post("/cases/case-0005/escalate", json={"reason": "x"}, headers=h).status_code == 404
    assert client.get("/consent", params={"citizen_id": UNLINKED}, headers=h).status_code == 403
    assert client.post("/claims", json={"on_behalf_of": UNLINKED}, headers=h).status_code == 403


def test_helper_needs_citizen_id_to_create(client):
    h = auth(client, "helper")
    assert client.post("/cases", json={"claim_type": "missing", "amount_claimed_pkr": 1}, headers=h).status_code == 422


def test_helper_families_only_linked(client):
    items = client.get("/helper/families", headers=auth(client, "helper")).json()["items"]
    assert len(items) == 10 and all(i["family_id"].startswith("fam-") for i in items)
    assert "Rashid Mehmood" not in {i["head_name"] for i in items}


def test_officer_sees_all(client):
    assert client.get("/cases", headers=auth(client, "officer")).json()["total"] == 5


def test_queue_sorted_by_risk_then_confidence(client):
    items = client.get("/queue", headers=auth(client, "officer")).json()["items"]
    keys = [(-i["risk_score"], i["confidence"]) for i in items]
    assert keys == sorted(keys) and len(items) == 2
