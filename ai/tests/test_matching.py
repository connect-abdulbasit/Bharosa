"""Real match_person(): spelling variants, no-match returns None, lookalikes, CNIC rules, ambiguity, calibration."""
import importlib
import time

import pytest

import bharosa_ai
from contracts.schemas import PersonRecord

_saved = (bharosa_ai.decide, bharosa_ai.explain)
_m = importlib.import_module("bharosa_ai.matching")
bharosa_ai.decide, bharosa_ai.explain = _saved
match_person = _m.match_person

ASLAM = PersonRecord(cnic="0000042101001", full_name="Muhammad Aslam", aliases=["Mohammad Aslam"])
FATIMA = PersonRecord(cnic="0000042101002", full_name="Fatima Noor", aliases=["Fatima Bibi", "Fatma Noor"])
ZUBAIDA = PersonRecord(cnic="0000042101003", full_name="Zubaida Khatoon", aliases=["Zubeda Khatun"])
GUL = PersonRecord(cnic="0000042101004", full_name="Gul Bano")
CANDS = [ASLAM, FATIMA, ZUBAIDA, GUL]


@pytest.mark.parametrize("spelling", ["Muhammad Aslam", "Mohammad Aslam", "Mohammed Aslam", "Muhammed Aslam", "MUHAMMAD  ASLAM",
                                      "muhammad aslam.", "Mr. Muhammad Aslam", "Aslam Muhammad", "Muhammad Aslam s/o Abdul Rehman",
                                      "Mohd Aslam"])
def test_muhammad_family_and_messy_spelling_match_with_high_confidence(spelling):
    r = match_person(spelling, None, [ASLAM])
    assert r.match_id == ASLAM.cnic and r.confidence >= 0.9 and r.model_version
    assert r.variants


def test_initial_matches_but_never_confidently():
    r = match_person("M. Aslam", None, [ASLAM])
    assert r.match_id == ASLAM.cnic and r.confidence <= 0.75


def test_spelling_only_match_stays_below_the_auto_handle_line():
    r = match_person("Aslaam", None, [PersonRecord(cnic="0000042101009", full_name="Aslam")])
    assert r.match_id == "0000042101009" and r.confidence <= 0.88


def test_urdu_script_matches_the_latin_record_as_a_spelling_variant():
    r = match_person("محمد اسلم", None, [ASLAM])
    assert r.match_id == ASLAM.cnic and 0.5 <= r.confidence <= 0.88


def test_alias_is_used_and_listed_in_variants():
    r = match_person("Fatima Bibi", None, CANDS)
    assert r.match_id == FATIMA.cnic and "Fatima Bibi" in r.variants


def test_honorific_suffix_does_not_break_the_match():
    assert match_person("Gul Bano Bibi", None, [GUL]).match_id == GUL.cnic
    assert match_person("Gul Bano", None, [PersonRecord(cnic="0000042101010", full_name="Gul Bano Bibi")]).match_id == "0000042101010"


@pytest.mark.parametrize("name", ["Totally Different", "Ahmed Raza", "Rashid Mehmood"])
def test_no_match_returns_none_with_low_confidence(name):
    r = match_person(name, None, CANDS)
    assert r.match_id is None and r.confidence <= 0.4


@pytest.mark.parametrize("name,record", [
    ("Muhammad Asim", "Muhammad Aslam"),      # lookalike first names
    ("Muhammad Aslam", "Muhammad Asif"),
    ("Fatima Bibi", "Fatima Noor"),           # first name only is not enough
    ("Zubaida Khatoon", "Zareena Khatoon"),
    ("Abdul Rehman", "Abdul Rahim"),
    ("Aslam", "Muhammad Aslam Khan"),
    ("Salma Noor", "Salman Noor"),            # one letter apart in a short name is a different person, not a typo
    ("Asim Khan", "Asif Khan"),
])
def test_lookalike_names_are_not_matched(name, record):
    r = match_person(name, None, [PersonRecord(cnic="0000042101050", full_name=record)])
    assert r.match_id is None


def test_the_right_person_wins_among_lookalikes():
    asim = PersonRecord(cnic="0000042101051", full_name="Muhammad Asim")
    r = match_person("Muhammad Aslam", None, [asim, ASLAM])
    assert r.match_id == ASLAM.cnic


def test_two_equally_good_candidates_are_ambiguous_so_nothing_is_picked():
    twin = PersonRecord(cnic="0000042101052", full_name="Muhammad Aslam")
    r = match_person("Muhammad Aslam", None, [ASLAM, twin])
    assert r.match_id is None and r.confidence <= 0.5


def test_cnic_with_dashes_and_matching_name():
    r = match_person("Mohammad Aslam", "00000-4210100-1", [ASLAM, FATIMA])
    assert r.match_id == ASLAM.cnic and r.confidence == pytest.approx(0.98)


def test_cnic_that_matches_but_with_a_different_name_is_a_conflict():
    r = match_person("Zubaida Khatoon", ASLAM.cnic, [ASLAM, ZUBAIDA])
    assert r.match_id is None and r.confidence <= 0.4


def test_cnic_found_on_nobody_is_not_a_match():
    r = match_person("Muhammad Aslam", "0000099999999", [ASLAM])
    assert r.match_id is None and r.confidence <= 0.3


def test_malformed_cnic_is_not_trusted():
    r = match_person("Muhammad Aslam", "12345", [ASLAM])
    assert r.match_id == ASLAM.cnic and r.confidence <= 0.7


@pytest.mark.parametrize("name", ["", "   ", "!!!", "123"])
def test_empty_or_nameless_input(name):
    r = match_person(name, None, CANDS)
    assert r.match_id is None and r.confidence == 0.0 and r.score == 0.0


def test_no_candidates():
    assert match_person("Muhammad Aslam", None, []).match_id is None


def test_huge_input_is_bounded_and_does_not_raise():
    start = time.time()
    r = match_person("muhammad " * 2000, None, CANDS)
    assert r.confidence <= 1.0 and time.time() - start < 2


HAMAD = PersonRecord(cnic="0000042101060", full_name="Hamad Khan", father_name="Abdul Rehman", date_of_birth="1984-03-12")
WITH_DOB = PersonRecord(cnic="0000042101061", full_name="Muhammad Aslam", father_name="Abdul Rehman", date_of_birth="1984-03-12")


@pytest.mark.parametrize("raw", ["12.03.1984", "12/03/1984", "12-03-1984", "1984-03-12", "1984/03/12", " 1984-03-12 "])
def test_dates_of_birth_are_read_in_the_usual_formats(raw):
    assert _m._dob(raw) == "1984-03-12"


@pytest.mark.parametrize("raw", ["", None, "31.02.1984", "12.03.84", "not a date", "1984-13-01", "12.03"])
def test_a_missing_or_impossible_date_of_birth_is_ignored(raw):
    assert _m._dob(raw) is None


def test_father_name_and_date_of_birth_corroborate_a_spelling_only_match():
    plain = match_person("Hamid Khan", None, [HAMAD])
    one = match_person("Hamid Khan", None, [HAMAD], father_name="Abdul Rehman")
    both = match_person("Hamid Khan", None, [HAMAD], father_name="Abdul Rehman", date_of_birth="12/03/1984")
    assert plain.match_id == one.match_id == both.match_id == HAMAD.cnic
    assert plain.confidence == 0.88 < one.confidence <= 0.93 and one.confidence <= both.confidence <= 0.95   # the spelling-only cap is lifted, never to 0.9+


def test_a_date_of_birth_or_father_name_that_disagrees_caps_the_confidence_even_for_an_exact_name():
    assert match_person("Muhammad Aslam", None, [WITH_DOB]).confidence == 0.97
    assert match_person("Muhammad Aslam", None, [WITH_DOB], date_of_birth="01.01.1990").confidence == 0.5
    assert match_person("Muhammad Aslam", None, [WITH_DOB], father_name="Gulzar Ahmed").confidence == 0.5
    agree = match_person("Muhammad Aslam", None, [WITH_DOB], father_name="Abdul Rehman", date_of_birth="12-03-1984")
    assert agree.confidence == 0.97 and agree.match_id == WITH_DOB.cnic


def test_extras_tell_two_equally_good_candidates_apart():
    a = PersonRecord(cnic="0000042101062", full_name="Muhammad Aslam", date_of_birth="1984-03-12")
    b = PersonRecord(cnic="0000042101063", full_name="Muhammad Aslam", date_of_birth="1990-07-01")
    assert match_person("Muhammad Aslam", None, [a, b]).match_id is None                              # ambiguous without them
    assert match_person("Muhammad Aslam", None, [a, b], date_of_birth="12.03.1984").match_id == a.cnic
    assert match_person("Muhammad Aslam", None, [a, b], date_of_birth="01.07.1990").match_id == b.cnic
    assert match_person("Muhammad Aslam", None, [a, b], date_of_birth="05.05.1970").match_id is None  # fits neither: still ambiguous


def test_a_card_cnic_with_a_contradicting_date_of_birth_is_an_identity_conflict():
    r = match_person("Muhammad Aslam", WITH_DOB.cnic, [WITH_DOB], date_of_birth="01.01.1990")
    assert r.match_id is None and r.confidence == 0.35
    assert match_person("Muhammad Aslam", WITH_DOB.cnic, [WITH_DOB], date_of_birth="12.03.1984").confidence == pytest.approx(0.98)


def test_extras_are_ignored_when_the_record_has_none_and_when_they_are_not_given():
    bare = PersonRecord(cnic="0000042101064", full_name="Hamad Khan")
    assert match_person("Hamid Khan", None, [bare], father_name="Abdul Rehman", date_of_birth="12.03.1984") == match_person("Hamid Khan", None, [bare])
    assert match_person("Mohammad Aslam", None, CANDS) == match_person("Mohammad Aslam", None, CANDS, father_name=None, date_of_birth=None)


def test_calibration_is_monotonic_and_in_range():
    values = [_m._calibrate(i / 100) for i in range(0, 101)]
    assert values == sorted(values) and 0.0 <= values[0] and values[-1] <= 1.0


def test_deterministic():
    a = match_person("Mohammad Aslam", None, CANDS)
    assert a.model_dump() == match_person("Mohammad Aslam", None, CANDS).model_dump()
