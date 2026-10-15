"""Intent detection: map a free-text problem ("I lost my pan card, need new one") to services.

Score = 0.55 * keyword/phrase match + 0.45 * embedding similarity to the service profile.
Keywords catch exact phrasing (incl. Hinglish like "pan card kho gaya"); embeddings catch
paraphrases and other languages. Cheap, deterministic and explainable - no LLM call needed.
"""
from __future__ import annotations

import re
from functools import lru_cache

import numpy as np

from .catalog import load_services
from .embeddings import get_embedder, tokenize

STOP = {"i", "my", "me", "a", "an", "the", "to", "for", "of", "is", "in", "on", "and", "or", "it", "want", "need",
        "how", "do", "can", "get", "card", "pan", "please", "what", "with", "have", "am", "was", "has", "not"}

# Signals that override pure similarity (they encode decisions, not just topic).
RULES = [
    (re.compile(r"\b(two|2|multiple|double|do)\s+pan\b", re.I), "surrender_duplicate_pan", 0.6),
    (re.compile(r"\b(inoperative|deactivat|not working|blocked|link(ed|ing)?\s+(with\s+)?aadhaa?r|aadhaa?r\s+link)", re.I), "pan_aadhaar_link", 0.5),
    (re.compile(r"\b(lost|stolen|missing|damaged|torn|kho\s*gaya|duplicate|reprint)\b", re.I), "pan_reprint", 0.35),
    (re.compile(r"\b(e-?pan|pdf|soft\s*copy|download)\b", re.I), "epan_download", 0.3),
    (re.compile(r"\b(wrong|incorrect|mistake|spell\w*|typo|change[sd]?|update[sd]?|correct(ion)?|galat|marriage|married|surname|shifted|new address)\b", re.I), "pan_correction", 0.45),
    (re.compile(r"\b(track|status|where is|kab aayega|not (yet )?(received|delivered)|acknowledg)", re.I), "track_status", 0.35),
    (re.compile(r"\b(minor|child|kid|son|daughter|nri|foreign|company|firm|trust|huf|llp|(1[0-7]|[1-9])\s*(year|yr)s?\s*old)\b", re.I), "new_pan_physical", 0.6),
    (re.compile(r"\b(link|linking|linked)\b", re.I), "pan_aadhaar_link", 0.3),
    (re.compile(r"(खो\s*(गया|गई)|గుమ|పోయింది)"), "pan_reprint", 0.35),
    (re.compile(r"(लिंक|निष्क्रिय|లింక్)"), "pan_aadhaar_link", 0.4),
    (re.compile(r"\b(new|first|don'?t have|never had|apply|naya|banwana)\b", re.I), "instant_epan", 0.25),
    (re.compile(r"\b(verify|valid|genuine|check pan|forgot)\b", re.I), "verify_pan", 0.3),
]


def _profile(svc: dict) -> str:
    return " ".join([svc["title"], svc["short"], " ".join(svc.get("keywords", []))])


@lru_cache(maxsize=1)
def _profile_vectors():
    services = load_services()
    ids = list(services)
    emb = get_embedder()
    vecs = emb.embed_documents([_profile(services[i]) for i in ids])
    return ids, vecs


def keyword_score(text: str, svc: dict) -> float:
    t = text.lower()
    phrases = [k.lower() for k in svc.get("keywords", [])]
    phrase_hits = sum(1 for p in phrases if p in t)
    toks = {w for w in tokenize(text) if w not in STOP}
    vocab = {w for p in phrases + [svc["title"].lower(), svc["short"].lower()] for w in tokenize(p) if w not in STOP}
    tok_hits = len(toks & vocab)
    return min(1.0, 0.4 * phrase_hits + 0.12 * tok_hits)


def detect_intent(text: str, top_n: int = 3) -> list[dict]:
    services = load_services()
    if not text.strip():
        return []
    ids, vecs = _profile_vectors()
    qv = get_embedder().embed_query(text)
    sims = vecs @ qv
    # rescale cosine sims to 0..1 relative to the best match so models with compressed ranges still separate
    lo, hi = float(sims.min()), float(sims.max())
    sims_n = (sims - lo) / (hi - lo) if hi > lo else np.zeros_like(sims)

    boosts = {sid: 0.0 for sid in ids}
    reasons: dict[str, list[str]] = {sid: [] for sid in ids}
    for rx, sid, w in RULES:
        m = rx.search(text)
        if m and sid in boosts:
            boosts[sid] += w
            reasons[sid].append(f"mentions '{m.group(0).strip()}'")

    # "lost" + "change/wrong" => correction wins over reprint (a reprint can't change details)
    if boosts.get("pan_reprint") and boosts.get("pan_correction"):
        boosts["pan_reprint"] -= 0.2

    results = []
    for i, sid in enumerate(ids):
        kw = keyword_score(text, services[sid])
        score = 0.55 * kw + 0.45 * float(sims_n[i]) + boosts[sid]
        results.append({"service_id": sid, "title": services[sid]["title"], "score": round(score, 4),
                        "reasons": reasons[sid] or (["similar wording"] if sims_n[i] > 0.8 else [])})
    results.sort(key=lambda r: -r["score"])
    top = results[:top_n]
    # confidence = margin between best and runner-up
    if len(top) >= 2:
        margin = top[0]["score"] - top[1]["score"]
        conf = "high" if margin > 0.25 else "medium" if margin > 0.08 else "low"
    else:
        conf = "high"
    for r in top:
        r["confidence"] = conf if r is top[0] else None
    return top
