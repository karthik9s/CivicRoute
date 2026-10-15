from datetime import date

from app import validators as v


def test_pan_valid_and_holder_type():
    r = v.validate_pan("abcpe1234f")
    assert r.ok and r.normalized == "ABCPE1234F" and "Individual" in r.message


def test_pan_bad_format_and_holder():
    assert not v.validate_pan("ABCPE12345").ok
    assert not v.validate_pan("ABCPEI234F").ok  # letter I instead of digit 1
    assert not v.validate_pan("ABCXE1234F").ok  # X is not a holder type


def test_pan_surname_initial_warning():
    r = v.validate_pan("ABCPE1234F", full_name="Ravi Kumar Sharma")
    assert r.ok and r.level == "warning"
    assert v.validate_pan("ABCPS1234F", full_name="Ravi Kumar Sharma").level == "info"


def test_aadhaar_verhoeff():
    assert v.verhoeff_valid("234123412346")  # valid checksum test number
    assert not v.verhoeff_valid("234123412347")
    assert not v.validate_aadhaar("123412341234").ok  # cannot start with 1
    r = v.validate_aadhaar("2341 2341 2346")
    assert r.ok and r.normalized == "XXXX XXXX 2346"


def test_names():
    assert not v.validate_name("Mr Ravi Sharma").ok
    assert not v.validate_name("Ravi123").ok
    assert v.validate_name("R. K. Sharma").level == "warning"
    assert v.validate_name("ravi kumar sharma").normalized == "RAVI KUMAR SHARMA"


def test_name_mismatch_warning():
    assert v.compare_names("RAVI KUMAR SHARMA", "RAVI KUMAR SHARMA").message == "Names match exactly."
    assert v.compare_names("SHARMA RAVI KUMAR", "RAVI KUMAR SHARMA").level == "warning"
    assert "differs" in v.compare_names("RAVI SHARMA", "RAVI KUMAR SHARMA").message


def test_dob():
    today = date(2026, 10, 14)
    assert v.validate_dob("15/08/1995", today=today).ok
    assert v.validate_dob("1995-08-15", today=today).normalized == "15/08/1995"
    assert not v.validate_dob("15/08/2030", today=today).ok
    assert not v.validate_dob("15/08/2015", "instant_epan", today=today).ok  # minor
    assert v.validate_dob("01/01/1990", today=today).level == "warning"


def test_contact_fields():
    assert v.validate_mobile("+91 98765 43210").normalized == "9876543210"
    assert not v.validate_mobile("5876543210").ok
    assert v.validate_email("A@B.co").ok and not v.validate_email("a@b").ok
    assert v.validate_pincode("500001").ok and not v.validate_pincode("050001").ok


def test_aadhaar_never_validated_server_side():
    r = v.validate_field("aadhaar_local", "234123412346")
    assert not r.ok and "never sent" in r.message


def test_cross_checks():
    out = v.cross_checks({"full_name": "RAVI KUMAR SHARMA", "proof_name": "RAVI K SHARMA", "name_on_card": "RAVI SINGH"})
    fields = {f for o in out for f in o["fields"]}
    assert {"full_name", "name_on_card"} <= fields
