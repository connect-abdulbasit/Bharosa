"""idcard.parse(): OCR text lines to ID-card fields. Literal text only: no OCR engine is needed."""
import pytest

from bharosa_ai import idcard

CLEAN = [("IDENTITY CARD(FAKE)", 0.95), ("Name", 1.0), ("Muhammad Aslam", 1.0), ("Father Name", 0.96), ("Abdul Rehman", 0.99), ("Gender", 1.0),
         ("M", 0.99), ("Identity Number", 0.97), ("00000-4210100-1", 1.0), ("Date of Birth", 0.94), ("12.03.1984", 1.0)]


def test_a_clean_card_gives_every_field_and_its_score():
    fields, scores = idcard.parse(CLEAN)
    assert fields == {"name": "Muhammad Aslam", "father_name": "Abdul Rehman", "cnic": "0000042101001", "date_of_birth": "1984-03-12"}
    assert scores["name"] == 1.0 and scores["father_name"] == 0.96 and scores["cnic"] == 0.97 and scores["date_of_birth"] == 0.94  # min of label and value


def test_ocr_that_drops_spaces_and_swaps_letters_is_still_read():
    lines = [("IDENTITYCARD(FAKE)", 0.9), ("Name", 0.99), ("Muhammad Aslam", 0.98), ("FatherName", 1.0), ("AbdulRehman", 0.99), ("ldentityNumber", 0.94),
             ("00000-4210100-1", 1.0), ("DateofBirth", 0.99), ("12.03.1984", 1.0)]
    fields, _ = idcard.parse(lines)
    assert fields["father_name"] == "Abdul Rehman" and fields["cnic"] == "0000042101001" and fields["date_of_birth"] == "1984-03-12"


@pytest.mark.parametrize("raw,expected", [
    ("00000-4210100-1", "0000042101001"), ("0000042101001", "0000042101001"), ("00000 4210100 1", "0000042101001"),
    ("0000O-4210100-I", "0000042101001"), ("00000-42IO1OO-1", "0000042101001"), ("0000O-421SS00-8", "0000042155008"),  # O/0, I/1, S/5 repaired
    ("CNIC: 00000-4210100-1 holder", "0000042101001"),
])
def test_cnic_is_found_and_digit_confusions_are_repaired(raw, expected):
    assert idcard.cnic_from(raw) == expected


@pytest.mark.parametrize("raw", ["", "00000-4210100", "00000-4210100-12", "100000-4210100-1", "00000-4210100-1-5", "1234567", "ABCDEFGHIJKLM",
                                 "OOOOO-421SS00-B", "Sahara Relief Programme", "SoBoIOlSoBoSl", None])
def test_a_wrong_length_or_a_word_is_never_read_as_a_cnic(raw):
    assert idcard.cnic_from(raw or "") is None


def test_name_and_value_on_one_line():
    fields, _ = idcard.parse([("Name: Fatima Noor", 0.9), ("Father Name - Noor Muhammad", 0.8), ("Identity Number: 00000-4210100-2", 0.95)])
    assert fields == {"name": "Fatima Noor", "father_name": "Noor Muhammad", "cnic": "0000042101002"}


def test_the_cnic_is_found_even_without_its_label():
    fields, scores = idcard.parse([("Muhammad Aslam", 0.9), ("00000-4210100-1", 0.88)])
    assert fields == {"cnic": "0000042101001"} and scores["cnic"] == 0.88


def test_a_label_with_no_value_gives_nothing_not_a_guess():
    assert idcard.parse([("Name", 1.0), ("Father Name", 1.0), ("Abdul Rehman", 0.9)])[0] == {"father_name": "Abdul Rehman"}
    assert idcard.parse([("Date of Birth", 1.0)])[0] == {}
    assert idcard.parse([("Name", 1.0), ("   ", 0.5)])[0] == {}


@pytest.mark.parametrize("raw,expected", [("12.03.1984", "1984-03-12"), ("12/03/1984", "1984-03-12"), ("12-03-1984", "1984-03-12"),
                                          ("12 . 03 . 1984", "1984-03-12"), ("31.02.1984", None), ("12.03.84", None), ("birth", None)])
def test_dates_of_birth(raw, expected):
    fields, _ = idcard.parse([("Date of Birth", 1.0), (raw, 1.0)])
    assert fields.get("date_of_birth") == expected


def test_digits_and_symbols_are_not_a_name():
    assert "name" not in idcard.parse([("Name", 1.0), ("12345", 0.9)])[0]
    assert idcard.parse([("Name", 1.0), ("M. Aslam", 0.9)])[0]["name"] == "M Aslam"


def test_a_label_is_not_taken_as_the_value_of_the_previous_label():
    fields, _ = idcard.parse([("Name", 1.0), ("Father Name", 1.0), ("Gender", 1.0), ("Abdul Rehman", 0.9)])
    assert "name" not in fields and fields.get("father_name") is None  # "Gender" came after "Father Name", then a name with no label owner


@pytest.mark.parametrize("lines", [None, [], [("", 0.0)], [(None, None)], [("x" * 10000, 0.5)], [("Name", "bad")], [(123, 0.5)]])
def test_odd_input_never_raises(lines):
    fields, scores = idcard.parse(lines)  # type: ignore[arg-type]
    assert isinstance(fields, dict) and isinstance(scores, dict)


def test_deterministic():
    assert idcard.parse(CLEAN) == idcard.parse(CLEAN)
