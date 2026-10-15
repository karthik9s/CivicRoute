"""Retrieval-augmented answering with citations, privacy redaction and an offline fallback."""
from __future__ import annotations

import datetime
import logging
import re
import threading
from functools import lru_cache

from .config import settings
from .embeddings import keyword_tokens
from .intent import detect_intent
from .llm import LLMError, get_llm
from .security import is_official_url, strip_unofficial_links
from .store import Hit, get_store

log = logging.getLogger(__name__)

LANG_NAMES = {"en": "English", "hi": "Hindi", "te": "Telugu", "ta": "Tamil", "kn": "Kannada", "mr": "Marathi", "bn": "Bengali"}

SYSTEM_PROMPT = """You are CivicRoute, a helpful assistant that explains Indian PAN (Permanent Account Number) services to ordinary citizens.

Rules:
- Answer ONLY using the numbered SOURCES provided. Cite them inline in exactly this format: [1] or [2][3] after each fact.
- Sources may be in English or another language; use all of them and answer in the reply language.
- If the sources don't contain the answer, say so plainly and point to the most relevant official link from the sources. Do NOT add steps, menu names, documents or advice that are not in the sources. Never guess fees, dates, form numbers or URLs.
- Use simple language. For procedures use short numbered steps. Keep answers under ~180 words unless the user asks for detail.
- Quote a fee only if the SOURCES state it on an official page. If they don't, say the exact fee is shown on the official payment page of the portal - never estimate or use third-party figures.
- You are not a government website. The user always submits, signs (OTP/e-Sign) and pays on the official portal themselves. Never ask the user for their Aadhaar number, PAN, OTP, passwords or bank details.
- Warn about common mistakes (name/DOB mismatch with proof, wrong service chosen) when relevant.
- Reply in {lang}."""


PAN_IN_TEXT = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.I)
AADHAAR_IN_TEXT = re.compile(r"\b[2-9]\d{3}\s?-?\d{4}\s?-?\d{4}\b")
MOBILE_IN_TEXT = re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)")
OTP_IN_TEXT = re.compile(r"\b(otp|password|pin)\b\D{0,12}\d{4,8}\b", re.I)


VID_IN_TEXT = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")  # Aadhaar Virtual ID (16 digits)
EMAIL_IN_TEXT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def redact(text: str) -> tuple[str, list[str]]:
    """Remove identifiers before text is sent to any LLM or logged."""
    found = []
    for rx, label in ((VID_IN_TEXT, "AADHAAR_VID"), (AADHAAR_IN_TEXT, "AADHAAR"), (PAN_IN_TEXT, "PAN"),
                      (MOBILE_IN_TEXT, "MOBILE"), (OTP_IN_TEXT, "OTP"), (EMAIL_IN_TEXT, "EMAIL")):
        if rx.search(text):
            found.append(label)
            text = rx.sub(f"[{label} REMOVED]", text)
    return text, found


@lru_cache(maxsize=1)
def _reranker():
    if not settings.reranker_model:
        return None
    try:
        from sentence_transformers import CrossEncoder

        return CrossEncoder(settings.reranker_model)
    except Exception as exc:
        log.warning("Reranker disabled: %s", exc)
        return None


def retrieve(question: str, service_id: str | None = None, k: int | None = None) -> list[Hit]:
    k = k or settings.top_k
    store = get_store()
    hits = store.search(question, k=k * 2 if _reranker() else k, service_id=service_id)
    rr = _reranker()
    if rr and hits:
        scores = rr.predict([(question, h.chunk.content) for h in hits])
        hits = [h for _, h in sorted(zip(scores, hits), key=lambda x: -x[0])][:k]
    return hits


def route_and_retrieve(question: str, service_id: str | None = None) -> tuple[list[Hit], list[dict]]:
    """Scope retrieval to the detected service when routing is confident, or when the question is in a
    non-Latin script (small multilingual embedders are weaker cross-lingually; the intent layer's
    native-language keywords pick the service, then English official content can be retrieved)."""
    intents = detect_intent(question, top_n=2)
    scope = service_id
    if not scope and intents:
        non_latin = sum(ord(c) > 0x024F for c in question) > len(question) * 0.3
        if intents[0].get("confidence") in ("high", "medium") or non_latin:
            scope = intents[0]["service_id"]
    hits = retrieve(question, scope)
    if scope and not service_id and len(hits) < 3:
        hits = retrieve(question, None)
    if scope:
        hits = _with_card_context(hits, scope)
    return hits, intents


def _with_card_context(hits: list[Hit], service_id: str, n_card: int = 2) -> list[Hit]:
    """Make sure the reviewed service card for the detected service is in context. Official pages are
    often in one language and miss the 'why' (e.g. the Hindi linking manual never says 'inoperative'),
    while the card connects the user's problem to the right procedure."""
    from .catalog import get_service

    svc = get_service(service_id)
    if not svc:
        return hits
    card_query = f"{svc['title']}. {svc['short']}"
    have = {h.chunk.id for h in hits}
    priority = {"Steps": 0, "Fees": 1}  # the actionable parts of a card
    cards = [h for h in retrieve(card_query, service_id, k=12) if h.chunk.origin == "card" and h.chunk.id not in have]
    cards.sort(key=lambda h: priority.get(h.chunk.section, 9))
    extra = cards[:n_card]
    if not extra:
        return hits
    return hits + extra


_budget = {"day": None, "used": 0}
_budget_lock = threading.Lock()


def _llm_budget_ok() -> bool:
    """Shared daily cap on LLM calls (LLM_DAILY_BUDGET). Protects a free-tier key on a public site."""
    if settings.llm_daily_budget <= 0:
        return True
    today = datetime.date.today()
    with _budget_lock:
        if _budget["day"] != today:
            _budget["day"], _budget["used"] = today, 0
        if _budget["used"] >= settings.llm_daily_budget:
            return False
        _budget["used"] += 1
        return True


def build_context(hits: list[Hit]) -> str:
    parts = []
    for i, h in enumerate(hits, 1):
        c = h.chunk
        parts.append(f"[{i}] {c.title}{' - ' + c.section if c.section else ''}\nURL: {c.source_url}\n"
                     f"Last verified: {c.last_verified or 'unknown'}\n{c.content}")
    return "\n\n".join(parts)


def _sentences(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+\.)\s+", "", line).strip()
        # split on sentence ends followed by a capital letter (keeps "incl. taxes" together)
        out += [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Zऀ-ॿ])", line)]
    return [s for s in out if len(s) > 25]


QTYPE_HINTS = [
    (re.compile(r"\b(fee|fees|cost|charge|charges|price|pay|how much|kitna|amount)\b", re.I), re.compile(r"₹|\brs\.?\s?\d|\bfree\b", re.I)),
    (re.compile(r"\b(how long|time|days|when|kab)\b", re.I), re.compile(r"\b(day|days|week|minutes|immediate)\b", re.I)),
    (re.compile(r"\b(document|documents|proof|papers)\b", re.I), re.compile(r"\b(proof|certificate|aadhaar|passport|licen[cs]e)\b", re.I)),
]


def extractive_answer(question: str, hits: list[Hit]) -> str:
    q = {t for t in keyword_tokens(question) if len(t) > 2}
    wanted = [ans for qrx, ans in QTYPE_HINTS if qrx.search(question)]
    scored = []
    for i, h in enumerate(hits[:6], 1):
        for s in _sentences(h.chunk.content):
            overlap = len(q & set(keyword_tokens(s)))
            bonus = sum(2.0 for ans in wanted if ans.search(s))
            if overlap or bonus:
                scored.append((overlap + bonus - 0.15 * i, s, i))
    if not scored:
        return ""
    scored.sort(key=lambda x: -x[0])
    seen, lines = set(), []
    for _, s, i in scored:
        if s in seen:
            continue
        seen.add(s)
        lines.append(f"- {s} [{i}]")
        if len(lines) == 5:
            break
    return "Here's what the official sources say:\n" + "\n".join(lines)


def _clean_citations(answer: str, n: int) -> str:
    # Some models (e.g. gpt-oss) cite as 【3†L1-L4】 or 【3】 - normalise to [3].
    answer = re.sub(r"【(\d+)(?:†[^】]*)?】", lambda m: f"[{m.group(1)}]", answer)
    return re.sub(r"\[(\d+)\]", lambda m: m.group(0) if 1 <= int(m.group(1)) <= n else "", answer)


def answer(question: str, service_id: str | None = None, lang: str = "en", history: list[dict] | None = None) -> dict:
    clean_q, redacted = redact(question)
    hits, intents = route_and_retrieve(clean_q, service_id)

    citations = [
        {"n": i, "title": h.chunk.title, "section": h.chunk.section, "url": h.chunk.source_url, "portal": h.chunk.portal,
         "last_verified": h.chunk.last_verified, "snippet": h.chunk.content[:280], "score": round(h.score, 4)}
        for i, h in enumerate(hits, 1)
    ]
    privacy_note = (
        "For your safety I removed the " + ", ".join(redacted).lower().replace("_", " ")
        + " you typed. You never need to share these with CivicRoute — enter them only on the official portal."
    ) if redacted else None

    if not hits:
        return {"answer": "I couldn't find verified information about that yet. Try rephrasing, or pick one of the services "
                          "on the home screen.", "citations": [], "mode": "none", "privacy_note": privacy_note,
                "suggested_services": intents}

    llm = get_llm() if _llm_budget_ok() else None
    mode = "extractive"
    text = ""
    if llm:
        convo = ""
        for turn in (history or [])[-4:]:
            convo += f"{turn.get('role', 'user').upper()}: {redact(turn.get('content', ''))[0][:600]}\n"
        user_msg = (f"SOURCES:\n{build_context(hits)}\n\n"
                    + (f"EARLIER CONVERSATION:\n{convo}\n" if convo else "")
                    + f"QUESTION: {clean_q}")
        try:
            text = llm.generate(SYSTEM_PROMPT.format(lang=LANG_NAMES.get(lang, "English")), user_msg)
            mode = f"llm:{llm.name}"
        except LLMError as exc:
            log.warning("LLM failed, falling back to extractive: %s", exc)
    if not text:
        text = extractive_answer(clean_q, hits) or (
            f"The most relevant official page is “{hits[0].chunk.title}”. Open source [1] for details.")

    text, removed_links = strip_unofficial_links(_clean_citations(text, len(hits)))
    if removed_links:
        log.warning("Removed %d non-official link(s) from an answer", removed_links)
    citations = [c for c in citations if is_official_url(c["url"])]
    return {"answer": text, "citations": citations, "mode": mode,
            "privacy_note": privacy_note, "suggested_services": intents}
