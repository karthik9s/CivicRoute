import json

import pytest
from fastapi.testclient import TestClient

from app.catalog import load_flows, load_services
from app.main import app
from app.rag import redact
from ingest.chunker import html_to_sections, split_text

client = TestClient(app)


def test_health():
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["chunks"] > 50 and r["llm"].startswith("extractive")


def test_catalog_integrity():
    services = load_services()
    flows = load_flows()
    for s in services.values():
        for n in s.get("not_for", []):
            assert n["go_to"] in services, n
        assert s["official_links"] and s["steps"] and s["last_verified"]
        for link in s["official_links"]:
            assert any(d in link["url"] for d in ("incometax.gov.in", "proteantech.in", "utiitsl.com"))
    # every flow path ends in a real service
    for p in flows["problems"]:
        assert p.get("result") in services or p.get("start") in flows["questions"]
    for q in flows["questions"].values():
        for o in q["options"]:
            assert o.get("result") in services or o.get("next") in flows["questions"], o


def test_service_detail_has_form():
    r = client.get("/api/services/pan_correction").json()
    ids = [f["id"] for f in r["form"]]
    assert "change_fields" in ids and "proof_name" in ids
    assert client.get("/api/services/nope").status_code == 404


def test_flow_question():
    r = client.get("/api/flow/q_lost_1").json()
    assert len(r["options"]) == 2


@pytest.mark.parametrize("text,expected", [
    ("I lost my pan card, need a duplicate", "pan_reprint"),
    ("my name is spelled wrong on pan", "pan_correction"),
    ("change surname after marriage", "pan_correction"),
    ("my pan became inoperative", "pan_aadhaar_link"),
    ("how to link aadhaar with pan", "pan_aadhaar_link"),
    ("where is my pan application, not delivered yet", "track_status"),
    ("I have two pan cards", "surrender_duplicate_pan"),
    ("pan for my minor son", "new_pan_physical"),
    ("I never had a PAN, want one free", "instant_epan"),
    ("e-pan email not received, need pdf", "epan_download"),
    ("pan card kho gaya", "pan_reprint"),
])
def test_intent(text, expected):
    r = client.post("/api/intent", json={"text": text}).json()
    assert r["results"][0]["service_id"] == expected, r["results"]


def test_chat_extractive_with_citations():
    r = client.post("/api/chat", json={"question": "What is the fee for reprint of PAN card in India?", "service_id": "pan_reprint"}).json()
    assert r["mode"] == "extractive" and r["citations"]
    assert "50" in r["answer"]
    assert all(c["url"].startswith("https://") for c in r["citations"])


def test_chat_redacts_identifiers():
    r = client.post("/api/chat", json={"question": "my pan ABCPE1234F and aadhaar 2341 2341 2346 is not linked"}).json()
    assert r["privacy_note"] and "aadhaar" in r["privacy_note"]
    text, found = redact("call me on 9876543210, otp 123456")
    assert "9876543210" not in text and "123456" not in text and {"MOBILE", "OTP"} <= set(found)


def test_validate_rejects_aadhaar():
    r = client.post("/api/validate", json={"service_id": "pan_reprint", "values": {"aadhaar_local": "234123412346"}})
    assert r.status_code == 400


def test_validate_and_handoff():
    values = {"pan": "abcps1234f", "full_name": "ravi kumar sharma", "proof_name": "RAVI K SHARMA", "dob": "15/08/1995",
              "mobile": "9876543210", "email": "ravi@example.com", "change_fields": ["Name", "Address"]}
    r = client.post("/api/validate", json={"service_id": "pan_correction", "values": values}).json()
    assert r["fields"]["pan"]["ok"] and r["fields"]["dob"]["ok"]
    assert any("full_name" in c["fields"] for c in r["cross_checks"])
    h = client.post("/api/handoff", json={"service_id": "pan_correction", "values": values}).json()
    labels = {row["field"]: row for row in h["rows"]}
    assert labels["pan"]["value"] == "ABCPS1234F"
    assert "Last: SHARMA" in labels["full_name"]["value"]
    assert any("marriage" in c.lower() for c in h["checklist"])
    assert h["safety"]


def test_chunker():
    html = "<html><nav>menu</nav><main><h2>Fees</h2><p>The reprint fee is Rs 50 including taxes for India.</p>" \
           "<ul><li>Dispatch outside India costs Rs 959 including taxes.</li></ul><footer>x</footer></main></html>"
    secs = html_to_sections(html)
    assert secs[0][0] == "Fees" and "959" in secs[0][1] and "menu" not in json.dumps(secs)
    parts = split_text("Sentence number one is here. " * 100, max_chars=300, overlap=50)
    assert len(parts) > 3 and all(len(p) <= 360 for p in parts)


def test_provider_selection(monkeypatch):
    from app import llm as llm_mod
    from app.config import settings

    monkeypatch.setattr(type(settings), "llm_provider", property(lambda self: "auto"), raising=False)
    for k in ("ANTHROPIC_API_KEY", "XAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    llm_mod.get_llm.cache_clear()
    try:
        got = llm_mod.get_llm()
        assert got.name == "groq" and "api.groq.com" in str(got.client.base_url)
        monkeypatch.delenv("GROQ_API_KEY")
        monkeypatch.setenv("XAI_API_KEY", "xai_test")
        llm_mod.get_llm.cache_clear()
        got = llm_mod.get_llm()
        assert got.name == "xai" and "api.x.ai" in str(got.client.base_url)
    finally:
        llm_mod.get_llm.cache_clear()


def test_updates_and_support():
    u = client.get("/api/updates").json()
    assert u["updates"] and all(x["url"] for x in u["updates"])
    dates = [x["date"] for x in u["updates"]]
    assert dates == sorted(dates, reverse=True)  # newest first
    s = client.get("/api/support").json()
    efiling = next(h for h in s["helplines"] if h["id"] == "efiling")
    assert "1800 103 0025" in efiling["phones"]
    assert all(h["url"].startswith("https://") for h in s["helplines"])


def test_telugu_flows_present():
    flows = load_flows()
    assert all(p.get("title_te") for p in flows["problems"])
    for q in flows["questions"].values():
        assert q.get("text_te") and all(o.get("label_te") for o in q["options"])


def test_localized_services_keep_facts():
    en = {s["id"]: s for s in client.get("/api/services").json()}
    for lang in ("te", "hi"):
        loc = {s["id"]: s for s in client.get(f"/api/services?lang={lang}").json()}
        assert loc["pan_reprint"]["title"] != en["pan_reprint"]["title"]  # translated
        for sid in en:  # every rupee amount is identical in every language
            assert [f["amount"].count("₹") for f in loc[sid]["fees"]] == [f["amount"].count("₹") for f in en[sid]["fees"]]
        detail = client.get(f"/api/services/pan_reprint?lang={lang}").json()
        assert any("50" in f["amount"] for f in detail["fees"])
        assert all(l["url"].startswith("https://") for l in detail["official_links"])
    assert client.get("/api/services?lang=xx").json()[0]["title"] == list(en.values())[0]["title"]  # unknown -> English


def test_model_change_reembeds_unchanged_chunks(tmp_path):
    """Switching embedding models must re-embed everything, even chunks whose text didn't change."""
    from app.embeddings import get_embedder
    from app.store import Chunk, MemoryStore

    store = MemoryStore(tmp_path)
    chunk = Chunk(id="c1", source_url="https://www.incometax.gov.in/", title="t", content="PAN reprint fee", portal="x",
                  service_ids=[], section="s", content_hash="h1", last_verified="2026-01-01", origin="kb")
    current = get_embedder()
    store.upsert([chunk], current.embed_documents(["PAN reprint fee"]), "some-old-model")
    assert store.existing_hashes() == {}  # stale model: nothing counts as up to date
    store.upsert([chunk], current.embed_documents(["PAN reprint fee"]), current.name)
    assert store.existing_hashes() == {"c1": "h1"}
