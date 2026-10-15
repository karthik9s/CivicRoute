"""Machine-translate the reviewed service cards and form labels into Hindi / Telugu.

    python -m ingest.translate            # all languages, only what is missing
    python -m ingest.translate --force    # re-translate everything except hand-written title/short

Safety: English (data/services.json) stays authoritative. Every translated string must keep exactly the
same numbers, ₹ amounts, URLs and key Latin terms (PAN, Aadhaar, OTP, Protean...) as the English; if not,
that string is rejected and the English is kept. Output: data/i18n/services.<lang>.json (overlay files).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.catalog import FIELDS, load_services  # noqa: E402
from app.config import DATA_DIR  # noqa: E402
from app.llm import LLMError, get_llm  # noqa: E402

log = logging.getLogger("translate")
LANGS = {"hi": "Hindi", "te": "Telugu"}
KEEP_RX = re.compile(r"https?://\S+|₹\s?[\d,.]+|\d[\d,.:/–-]*|\b(?:PAN|e-PAN|Aadhaar|OTP|ITD|NSDL|Protean|UTIITSL|NRI|HUF|PDF|DOB|e-Sign|ITR|AO)\b")

SYSTEM = ("You translate Indian government-service help text from English into {lang} for ordinary citizens. "
          "Use simple, natural {lang}. Keep these EXACTLY as in the source: all numbers, dates, ₹ amounts, URLs, and the terms "
          "PAN, e-PAN, Aadhaar, OTP, ITD, NSDL, Protean, UTIITSL, NRI, HUF, PDF, e-Sign, ITR, AO. Keep text inside quotes "
          "like 'Reprint of PAN Card' or “Other Receipts (500)” in English (they are labels on the official website). "
          "Return ONLY a JSON object with the same keys as the input and translated string values. No commentary.")


def translatable(svc: dict) -> dict[str, str]:
    """Flatten the human-facing strings of a service card into path -> text."""
    out = {}
    for i, v in enumerate(svc.get("eligibility", [])): out[f"eligibility.{i}"] = v
    for i, n in enumerate(svc.get("not_for", [])): out[f"not_for.{i}.when"] = n["when"]
    for i, v in enumerate(svc.get("documents", [])): out[f"documents.{i}"] = v
    for i, f in enumerate(svc.get("fees", [])):
        out[f"fees.{i}.label"] = f["label"]
        out[f"fees.{i}.amount"] = f["amount"]
        if f.get("note"): out[f"fees.{i}.note"] = f["note"]
    out["time"] = svc["time"]
    for i, st in enumerate(svc.get("steps", [])):
        out[f"steps.{i}.title"] = st["title"]
        out[f"steps.{i}.detail"] = st["detail"]
    for i, v in enumerate(svc.get("tips", [])): out[f"tips.{i}"] = v
    for i, v in enumerate(svc.get("common_rejections", [])): out[f"common_rejections.{i}"] = v
    for i, l in enumerate(svc.get("official_links", [])): out[f"official_links.{i}.label"] = l["label"]
    return out


def keeps_facts(src: str, dst: str) -> bool:
    need = sorted(m.group(0).rstrip(".,") for m in KEEP_RX.finditer(src))
    have = sorted(m.group(0).rstrip(".,") for m in KEEP_RX.finditer(dst))
    return all(have.count(x) >= need.count(x) for x in set(need)) and len(dst.strip()) > 0


def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


CHUNK = 6  # strings per request - Indic scripts use many tokens, and free tiers cap tokens per minute


def _call(llm, lang: str, items: dict[str, str]) -> dict:
    for attempt in range(6):
        try:
            return parse_json(llm.generate(SYSTEM.format(lang=LANGS[lang]), json.dumps(items, ensure_ascii=False, indent=1)))
        except LLMError as e:
            wait = 20 * (attempt + 1)
            log.warning("LLM busy (%s) - retrying in %ss", str(e)[:60], wait)
            time.sleep(wait)
        except (ValueError, json.JSONDecodeError):
            log.warning("Unparseable reply - retrying")
    return {}


def translate_batch(llm, lang: str, items: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    if not items:
        return {}, []
    got = {}
    keys = list(items)
    for i in range(0, len(keys), CHUNK):
        part = {k: items[k] for k in keys[i:i + CHUNK]}
        got.update(_call(llm, lang, part))
    ok, rejected = {}, []
    for k, src in items.items():
        dst = got.get(k)
        if isinstance(dst, str) and keeps_facts(src, dst):
            ok[k] = dst
        else:
            rejected.append(k)
    return ok, rejected


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", nargs="*", default=list(LANGS))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for noisy in ("httpx", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    llm = get_llm()
    if not llm:
        sys.exit("No LLM configured - set GROQ_API_KEY (or another provider) in backend/.env")

    services = load_services()
    for lang in args.lang:
        path = DATA_DIR / "i18n" / f"services.{lang}.json"
        overlay = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"services": {}, "fields": {}}
        total_ok = total_bad = 0
        for sid, svc in services.items():
            cur = overlay["services"].setdefault(sid, {})
            have = cur.get("paths", {})
            todo = {k: v for k, v in translatable(svc).items() if args.force or k not in have}
            if not todo:
                continue
            ok, bad = translate_batch(llm, lang, todo)
            have.update(ok)
            cur["paths"] = have
            total_ok += len(ok); total_bad += len(bad)
            log.info("%s %-26s translated %d, kept English %d %s", lang, sid, len(ok), len(bad), bad[:3] if bad else "")
            path.write_text(json.dumps(overlay, ensure_ascii=False, indent=1), encoding="utf-8")
        # form field labels / help
        fields_todo = {}
        for fid, meta in FIELDS.items():
            for key in ("label", "help"):
                if meta.get(key) and (args.force or f"{fid}.{key}" not in overlay["fields"]):
                    fields_todo[f"{fid}.{key}"] = meta[key]
        if fields_todo:
            ok, bad = translate_batch(llm, lang, fields_todo)
            overlay["fields"].update(ok)
            total_ok += len(ok); total_bad += len(bad)
            log.info("%s form fields: translated %d, kept English %d", lang, len(ok), len(bad))
        overlay["_machine_translated"] = True
        path.write_text(json.dumps(overlay, ensure_ascii=False, indent=1), encoding="utf-8")
        log.info("%s done: %d strings translated, %d kept in English (failed fact check)", lang, total_ok, total_bad)


if __name__ == "__main__":
    main()
