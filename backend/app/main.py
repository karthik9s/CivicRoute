"""CivicRoute API.

Stateless by design: nothing a user types into the wizard is stored server-side, and
Aadhaar numbers are rejected outright. Run with:  uvicorn app.main:app --reload
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import validators
from .catalog import (CHANGE_PROOF_HINTS, FIELDS, SUPPORTED_LANGS, get_service, load_flows, load_meta, load_services, localize,
                      service_form)
from .config import BACKEND_DIR, DATA_DIR, settings
from .embeddings import get_embedder
from .intent import detect_intent
from .llm import get_llm
from .rag import LANG_NAMES, answer, redact
from .security import (RATE_LIMITS, BodySizeLimitMiddleware, RateLimiter, RateLimitMiddleware,
                       SecurityHeadersMiddleware, contains_aadhaar)
from .store import get_store

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
for _noisy in ("httpx", "huggingface_hub", "sentence_transformers"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
@asynccontextmanager
async def lifespan(_app):
    await asyncio.to_thread(_warmup)  # load model + index before serving; never blocks the event loop
    yield


app = FastAPI(title="CivicRoute AI – PAN Co-pilot", version="1.0.0", docs_url=None, redoc_url=None, openapi_url=None,
              lifespan=lifespan)
# Middleware runs bottom-up: headers wrap everything, then size limit, then rate limit, then CORS.
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type"], allow_credentials=False)
app.add_middleware(RateLimitMiddleware, limiter=RateLimiter(RATE_LIMITS))
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

ServiceId = Field(..., max_length=64, pattern=r"^[a-z_]+$")


class IntentIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]  # no client-supplied "system" turns (prompt-injection vector)
    content: str = Field(..., max_length=2000)


class ChatIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=1500)
    service_id: str | None = Field(None, max_length=64, pattern=r"^[a-z_]+$")
    lang: str = Field("en", max_length=5)
    history: list[ChatTurn] = Field(default_factory=list, max_length=8)

    @field_validator("lang")
    @classmethod
    def _known_lang(cls, v: str) -> str:
        return v if v in LANG_NAMES else "en"


class ValuesIn(BaseModel):
    service_id: str = ServiceId
    values: dict[str, str | list[str]] = Field(default_factory=dict, max_length=40)

    @field_validator("values")
    @classmethod
    def _bounded(cls, v: dict) -> dict:
        for key, val in v.items():
            if len(key) > 40:
                raise ValueError("field name too long")
            items = val if isinstance(val, list) else [val]
            if len(items) > 20 or any(len(x) > 300 for x in items):
                raise ValueError(f"value for {key!r} is too long")
        return v


def _reject_sensitive(values: dict) -> None:
    """Aadhaar is checked on the user's device only. Refuse it under ANY field name, not just the Aadhaar field."""
    if any(k in validators.SENSITIVE_FIELDS for k in values) or any(
        contains_aadhaar(x) for val in values.values() for x in (val if isinstance(val, list) else [val])
    ):
        raise HTTPException(400, "Aadhaar numbers must not be sent to the server; they are checked on your device only.")


@app.get("/api/health")
def health():
    store = get_store()
    if settings.public_mode:  # don't advertise providers/models on a public site
        return {"status": "ok", "chunks": store.count()}
    llm = get_llm()
    return {"status": "ok", "store": type(store).__name__, "chunks": store.count(),
            "embedder": get_embedder().name, "llm": f"{llm.name}:{llm.model}" if llm else "extractive (no key)"}


@app.get("/api/meta")
def meta():
    return load_meta()


def _lang(lang: str | None) -> str:
    return lang if lang in SUPPORTED_LANGS else "en"


def _pick(obj: dict, key: str, lang: str):
    return obj.get(f"{key}_{lang}") or obj.get(key)


@app.get("/api/support")
def support(lang: str = "en"):
    """Official helplines (verified from the Income Tax 'Contact us' page) for the support assistant."""
    lang = _lang(lang)
    data = json.loads((DATA_DIR / "support.json").read_text(encoding="utf-8"))
    data["helplines"] = [{**h, "name": _pick(h, "name", lang), "for": _pick(h, "for", lang), "hours": _pick(h, "hours", lang)} for h in data["helplines"]]
    return data


@app.get("/api/updates")
def updates(lang: str = "en"):
    """Policy / link updates: curated dated items + pages the crawler detected as changed or unreachable."""
    lang = _lang(lang)
    tags = {
        "hi": {"Helpline": "हेल्पलाइन", "Fees": "शुल्क", "e-PAN": "e-PAN", "Aadhaar": "आधार", "Law": "कानून", "PAN 2.0": "PAN 2.0", "Changed": "बदला", "Review": "समीक्षा"},
        "te": {"Helpline": "హెల్ప్‌లైన్", "Fees": "ఫీజులు", "e-PAN": "e-PAN", "Aadhaar": "ఆధార్", "Law": "చట్టం", "PAN 2.0": "PAN 2.0", "Changed": "మారింది", "Review": "సమీక్ష"},
    }.get(lang, {})
    items = [{**u, "title": _pick(u, "title", lang), "tag": tags.get(u["tag"], u["tag"])}
             for u in json.loads((DATA_DIR / "updates.json").read_text(encoding="utf-8"))["updates"]]
    changed_t = {"en": "Official page updated – re-check before applying: {}", "hi": "आधिकारिक पेज बदला – आवेदन से पहले दोबारा जाँचें: {}",
                 "te": "అధికారిక పేజీ మారింది – దరఖాస్తుకు ముందు మళ్ళీ చూడండి: {}"}[lang]
    review_t = {"en": "Steps for “{}” are being re-verified after an official change", "hi": "आधिकारिक बदलाव के बाद “{}” के चरण दोबारा जाँचे जा रहे हैं",
                "te": "అధికారిక మార్పు తర్వాత “{}” దశలు మళ్ళీ ధృవీకరించబడుతున్నాయి"}[lang]
    report_path = DATA_DIR / "ingest_report.json"
    last_check = None
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        last_check = report.get("date")
        for url in report.get("changed_sources", []):
            items.append({"date": last_check, "tag": tags.get("Changed", "Changed"), "title": changed_t.format(url), "url": url, "auto": True})
        for card in report.get("cards_to_review", []):
            title = (get_service(card["id"], lang) or {}).get("title", card["title"])
            items.append({"date": last_check, "tag": tags.get("Review", "Review"), "title": review_t.format(title),
                          "url": f"#/service/{card['id']}", "auto": True})
    items.sort(key=lambda u: u["date"] or "", reverse=True)
    return {"updates": items, "last_checked": last_check}


@app.get("/api/problems")
def problems():
    return load_flows()["problems"]


@app.get("/api/flow/{question_id}")
def flow_question(question_id: str):
    q = load_flows()["questions"].get(question_id)
    if not q:
        raise HTTPException(404, "Unknown question")
    return {"id": question_id, **q}


@app.get("/api/services")
def services(lang: str = "en"):
    lang = _lang(lang)
    return [{k: s[k] for k in ("id", "title", "short", "icon", "category", "fees", "time")}
            for s in (localize(x, lang) for x in load_services().values())]


@app.get("/api/services/{service_id}")
def service(service_id: str, lang: str = "en"):
    lang = _lang(lang)
    svc = get_service(service_id, lang)
    if not svc:
        raise HTTPException(404, "Unknown service")
    return {**svc, "form": service_form(service_id, lang), "change_proof_hints": CHANGE_PROOF_HINTS}


@app.post("/api/intent")
def intent(body: IntentIn, lang: str = "en"):
    text, _ = redact(body.text)
    lang = _lang(lang)
    results = detect_intent(text)
    for r in results:
        r["title"] = get_service(r["service_id"], lang)["title"]
    return {"results": results}


@app.post("/api/chat")
def chat(body: ChatIn):
    if body.service_id and not get_service(body.service_id):
        raise HTTPException(404, "Unknown service")
    return answer(body.question, body.service_id, body.lang, [t.model_dump() for t in body.history])


@app.post("/api/validate")
def validate(body: ValuesIn):
    _reject_sensitive(body.values)
    if not get_service(body.service_id):
        raise HTTPException(404, "Unknown service")
    flat = {k: v for k, v in body.values.items() if isinstance(v, str)}
    ctx = {**flat, "service_id": body.service_id}
    fields = {k: validators.validate_field(k, v, ctx).as_dict() for k, v in flat.items()}
    return {"fields": fields, "cross_checks": validators.cross_checks(flat)}


SAFETY = {
    "en": ["Only use the official links above — check the address bar shows incometax.gov.in, proteantech.in or utiitsl.com.",
           "Pay only on the portal's own payment page. CivicRoute never collects payments.",
           "Never share OTPs with anyone, including CivicRoute."],
    "hi": ["केवल ऊपर दिए आधिकारिक लिंक इस्तेमाल करें — एड्रेस बार में incometax.gov.in, proteantech.in या utiitsl.com देखें।",
           "भुगतान केवल पोर्टल के अपने भुगतान पेज पर करें। CivicRoute कभी भुगतान नहीं लेता।",
           "OTP किसी के साथ साझा न करें, CivicRoute के साथ भी नहीं।"],
    "te": ["పైన ఉన్న అధికారిక లింకులు మాత్రమే వాడండి — అడ్రస్ బార్‌లో incometax.gov.in, proteantech.in లేదా utiitsl.com ఉందో చూడండి.",
           "పోర్టల్ స్వంత చెల్లింపు పేజీలో మాత్రమే చెల్లించండి. CivicRoute ఎప్పుడూ చెల్లింపులు తీసుకోదు.",
           "OTP లను ఎవరితోనూ పంచుకోకండి, CivicRoute తో కూడా."],
}


@app.post("/api/handoff")
def handoff(body: ValuesIn, lang: str = "en"):
    """Build the 'cheat sheet' the user follows on the official portal. Nothing is stored.
    Instructions are localized; portal field labels stay in English because that is what the official form shows."""
    _reject_sensitive(body.values)
    lang = _lang(lang)
    svc = get_service(body.service_id, lang)
    if not svc:
        raise HTTPException(404, "Unknown service")
    rows = []
    for fid in svc.get("form_fields", []):
        meta = FIELDS.get(fid, {})
        val = body.values.get(fid)
        if fid == "aadhaar_local":
            val = "Type your Aadhaar yourself on the portal"
        elif fid in ("photo", "signature"):
            val = "Upload the file you checked in step 4"
        if isinstance(val, list):
            val = ", ".join(val)
        if fid == "dob" and isinstance(val, str) and (d := validators.parse_date(val)):
            val = d.strftime("%d/%m/%Y")  # portals expect DD/MM/YYYY
        if val:
            if meta.get("upper") and isinstance(val, str):
                val = val.upper()
            if fid == "full_name" and isinstance(val, str):
                parts = val.split()
                if len(parts) >= 2:
                    val = f"{val}  →  Last: {parts[-1]} | First: {parts[0]}" + (f" | Middle: {' '.join(parts[1:-1])}" if len(parts) > 2 else "")
            rows.append({"field": fid, "portal_label": meta.get("portal_label", fid), "value": val})

    checklist = list(svc.get("documents", []))
    for ch in body.values.get("change_fields", []) or []:
        if ch in CHANGE_PROOF_HINTS:
            checklist.append(f"Proof for {ch.lower()} change: {CHANGE_PROOF_HINTS[ch]}")
    flat = {k: v for k, v in body.values.items() if isinstance(v, str)}
    return {
        "service_id": svc["id"], "title": svc["title"], "rows": rows, "checklist": checklist,
        "official_links": svc["official_links"], "steps": svc["steps"], "fees": svc["fees"],
        "warnings": validators.cross_checks(flat),
        "safety": SAFETY[lang],
    }


# Serve the built frontend (frontend/dist) when present, for single-process deployment.
DIST = BACKEND_DIR.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        if path and f.is_file() and DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")


def _warmup() -> None:
    """Load the embedding model, index and intent vectors up-front so the first user request is fast."""
    try:
        # Sync the active store (pgvector or local) with the downloaded official pages + curated KB.
        # Incremental: only new/changed chunks are embedded, so this is fast unless the store is empty.
        from ingest.run import run_pipeline

        if get_store().count() == 0:
            logging.getLogger(__name__).warning("Vector store is empty - building the index now (one-time, ~1 min)")
        run_pipeline(offline=True, write_report=False)
        detect_intent("warm up")
    except Exception as exc:  # never block startup
        logging.getLogger(__name__).warning("Warm-up failed: %s", exc)
