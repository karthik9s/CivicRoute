"""Regression tests for bugs found in a live walkthrough (2026-11-11)."""
from fastapi.testclient import TestClient

from app import validators
from app.intent import detect_intent
from app.main import app
from app.rag import redact

client = TestClient(app)


def test_english_do_is_not_hindi_two():
    # "how do PAN..." used to add the "two PANs" boost meant for Hinglish "do pan card hai"
    top = detect_intent("how do pan card reprint work")
    assert top[0]["service_id"] == "pan_reprint"
    assert "surrender_duplicate_pan" not in [r["service_id"] for r in top[:2]] or top[1]["score"] < top[0]["score"] - 0.3
    assert detect_intent("mere paas do pan card hai")[0]["service_id"] == "surrender_duplicate_pan"


def test_family_word_does_not_outvote_the_problem():
    top = detect_intent("my son lost his PAN card")
    assert top[0]["service_id"] == "pan_reprint" and top[0]["score"] - top[1]["score"] > 0.25
    assert detect_intent("apply PAN for my 10 year old son")[0]["service_id"] == "new_pan_physical"


def test_off_topic_gets_no_recommendation():
    for q in ("what is the weather today", "asdfgh"):
        assert detect_intent(q)[0]["confidence"] == "none", q
    assert detect_intent("I lost my PAN card")[0]["confidence"] != "none"


def test_handoff_shows_values_the_portal_accepts():
    vals = {"pan": "abcpk 1234f", "full_name": "Priya Sharma", "mobile": "+91 98765 43210", "email": " Priya@Gmail.com ",
            "pincode": "500 081", "change_fields": ["Address"]}
    rows = {r["field"]: r["value"] for r in client.post("/api/handoff", json={"service_id": "pan_correction", "values": vals}).json()["rows"]}
    assert rows["pan"] == "ABCPK1234F" and rows["mobile"] == "9876543210" and rows["pincode"] == "500081"
    assert rows["email"] == "priya@gmail.com"


def test_pin_with_space_accepted():
    assert validators.validate_pincode("500 081").ok


def test_no_surname_warning_on_name_change():
    vals = {"pan": "ABCPK1234F", "full_name": "Priya Sharma", "change_fields": ["Name"]}
    r = client.post("/api/validate", json={"service_id": "pan_correction", "values": vals}).json()
    assert r["fields"]["pan"]["level"] == "info" and not any("5th character" in c["message"] for c in r["cross_checks"])
    vals["change_fields"] = ["Address"]  # not changing the name: the warning is still useful
    r = client.post("/api/validate", json={"service_id": "pan_correction", "values": vals}).json()
    assert r["fields"]["pan"]["level"] == "warning"


def test_upi_reference_is_not_called_aadhaar():
    text, found = redact("I paid by UPI, UTR 412345678901, but status is not updated")
    assert "412345678901" in text and "AADHAAR" not in found
    # a checksum-valid number is still treated as Aadhaar, whatever word precedes it
    assert "AADHAAR" in redact("UTR 2345 6789 0125")[1]
    assert "AADHAAR" in redact("my number is 412345678901")[1]


def test_chat_follow_up_uses_selected_service():
    r = client.post("/api/chat", json={"question": "how much does it cost?", "service_id": "pan_reprint", "lang": "en"}).json()
    assert r["citations"]
    assert any("reprint" in (c["title"] + c["url"]).lower() for c in r["citations"])


def test_card_steps_and_fees_always_in_context():
    # The ₹1,000 Aadhaar-linking fee went missing: a search for the card ranked its Fees/Steps below other chunks.
    from app.rag import route_and_retrieve

    for q, sid in (("My PAN is inoperative, what should I do?", "pan_aadhaar_link"), ("I lost my PAN card", "pan_reprint")):
        hits, _ = route_and_retrieve(q, sid)
        sections = {h.chunk.section for h in hits if h.chunk.origin == "card"}
        assert {"Steps", "Fees"} <= sections, (q, sections)
        assert len({h.chunk.id for h in hits}) == len(hits)  # no duplicates
    hits, _ = route_and_retrieve("My PAN is inoperative, what should I do?", "pan_aadhaar_link")
    assert any("1,000" in h.chunk.content for h in hits)


def test_dotenv_inline_comments_are_not_values():
    from app.config import _parse_value

    assert _parse_value("auto            # auto | groq | none") == "auto"
    assert _parse_value("   # optional, e.g. BAAI/bge-reranker-base") == ""
    assert _parse_value("intfloat/multilingual-e5-small   # or \"hash\" for tests") == "intfloat/multilingual-e5-small"
    assert _parse_value("gsk_abc#123") == "gsk_abc#123"            # '#' inside a value is kept
    assert _parse_value("'pass # word'  # note") == "pass # word"   # quoted values are literal
    assert _parse_value('""') == ""


def test_unknown_api_path_is_404_json():
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
