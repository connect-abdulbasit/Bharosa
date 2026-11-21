"""find_duplicates(): one ID on two different people, or one person with two IDs. Not a contract function (see its docstring)."""
import time

import pytest

from bharosa_ai.duplicates import MAX_RECORDS, MODEL_VERSION, DuplicateFinding, find_duplicates
from contracts.schemas import PersonRecord

ASLAM = PersonRecord(cnic="0000042101001", full_name="Muhammad Aslam", date_of_birth="1984-03-12")


def test_the_same_cnic_on_two_different_names_is_one_id_two_people():
    out = find_duplicates([ASLAM, PersonRecord(cnic="00000-4210100-1", full_name="Fatima Noor")])  # dashes do not hide it
    assert len(out) == 1
    f = out[0]
    assert isinstance(f, DuplicateFinding) and f.kind == "same_cnic_different_name" and f.confidence == 0.9
    assert f.cnics == ["0000042101001"] and f.names == ["Muhammad Aslam", "Fatima Noor"] and f.model_version == MODEL_VERSION
    assert "one ID, two people" in f.reason


def test_a_spelling_variant_on_the_same_cnic_is_not_a_finding():
    assert find_duplicates([ASLAM, PersonRecord(cnic=ASLAM.cnic, full_name="Mohammad Aslam")]) == []
    assert find_duplicates([ASLAM, PersonRecord(cnic=ASLAM.cnic, full_name="Aslam Muhammad")]) == []


def test_the_same_name_and_date_of_birth_with_different_cnics_is_one_person_two_ids():
    other = PersonRecord(cnic="0000042101002", full_name="Mohammad Aslam", date_of_birth="12.03.1984")
    out = find_duplicates([ASLAM, other])
    assert len(out) == 1 and out[0].kind == "same_name_and_dob_different_cnic" and out[0].confidence == 0.85
    assert out[0].cnics == [ASLAM.cnic, other.cnic] and "one person, two IDs" in out[0].reason


@pytest.mark.parametrize("other", [
    PersonRecord(cnic="0000042101002", full_name="Muhammad Aslam", date_of_birth="1990-07-01"),   # same name, different date of birth
    PersonRecord(cnic="0000042101002", full_name="Muhammad Aslam"),                                # no date of birth to compare
    PersonRecord(cnic="0000042101002", full_name="Fatima Noor", date_of_birth="1984-03-12"),      # same date of birth, different person
    PersonRecord(cnic="0000042101002", full_name="Muhammad Asim", date_of_birth="1984-03-12"),    # look-alike name is not the same person
])
def test_different_people_are_not_duplicates(other):
    assert find_duplicates([ASLAM, other]) == []


def test_every_pair_in_a_group_is_reported_once_in_a_stable_order():
    a, b, c = (PersonRecord(cnic="0000042101001", full_name=n) for n in ("Muhammad Aslam", "Fatima Noor", "Gul Bano"))
    out = find_duplicates([a, b, c])
    assert len(out) == 3 and [f.names for f in out] == [["Muhammad Aslam", "Fatima Noor"], ["Muhammad Aslam", "Gul Bano"], ["Fatima Noor", "Gul Bano"]]
    assert [f.model_dump() for f in out] == [f.model_dump() for f in find_duplicates([a, b, c])]  # deterministic


@pytest.mark.parametrize("records", [[], None, [ASLAM], [PersonRecord(cnic="123", full_name="Short Cnic")] * 2])
def test_nothing_to_compare_gives_nothing(records):
    assert find_duplicates(records) == []


def test_findings_are_json_safe_and_bounded():
    out = find_duplicates([ASLAM, PersonRecord(cnic=ASLAM.cnic, full_name="Fatima Noor")])
    assert "model_version" in out[0].model_dump_json()
    big = [PersonRecord(cnic="00000%08d" % i, full_name="Person %d" % i) for i in range(MAX_RECORDS + 500)]
    start = time.time()
    assert find_duplicates(big) == [] and time.time() - start < 10
