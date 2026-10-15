"""Loads the reviewed service cards, decision-tree flows and wizard field registry."""
from __future__ import annotations

import copy
import json
from functools import lru_cache

from .config import DATA_DIR

# Wizard field registry. `portal_label` is what the field is called on the official form,
# so the hand-off cheat sheet can say "type X into the box labelled Y".
FIELDS: dict[str, dict] = {
    "pan": {"label": "PAN number", "type": "text", "placeholder": "ABCPE1234F", "portal_label": "PAN / Permanent Account Number", "upper": True},
    "full_name": {"label": "Full name (as on proof document)", "type": "text", "placeholder": "RAVI KUMAR SHARMA",
                  "portal_label": "Last Name / First Name / Middle Name", "upper": True,
                  "help": "Write it exactly as printed on your Aadhaar / proof. On the portal, split it into First, Middle and Last name."},
    "proof_name": {"label": "Name exactly as printed on your proof document", "type": "text", "upper": True,
                   "help": "Used only to warn you about mismatches — not sent anywhere."},
    "name_on_card": {"label": "Name to print on card", "type": "text", "portal_label": "Name you would like printed on the PAN card", "upper": True},
    "father_name": {"label": "Father's full name", "type": "text", "portal_label": "Father's Name (Last / First / Middle)", "upper": True,
                    "help": "Mandatory for individuals, even if married. Mother's name is optional unless father's name is not applicable."},
    "mother_name": {"label": "Mother's full name (optional)", "type": "text", "portal_label": "Mother's Name", "upper": True},
    "dob": {"label": "Date of birth", "type": "date", "portal_label": "Date of Birth / Incorporation (DD/MM/YYYY)"},
    "gender": {"label": "Gender", "type": "select", "options": ["Male", "Female", "Transgender"], "portal_label": "Gender"},
    "aadhaar_local": {"label": "Aadhaar number (checked on your device only)", "type": "aadhaar", "portal_label": "Aadhaar Number",
                      "help": "Never sent to CivicRoute's server and never saved. You'll type it yourself on the official portal."},
    "mobile": {"label": "Mobile number", "type": "tel", "placeholder": "9876543210", "portal_label": "Telephone / Mobile number"},
    "email": {"label": "Email", "type": "email", "portal_label": "Email ID"},
    "address_line1": {"label": "Flat / House no., Building", "type": "text", "portal_label": "Flat/Room/Door/Block No. + Name of Premises"},
    "address_line2": {"label": "Road / Street, Area / Locality", "type": "text", "portal_label": "Road/Street/Lane + Area/Locality/Sub-Division"},
    "city": {"label": "Town / City / District", "type": "text", "portal_label": "Town/City/District"},
    "state": {"label": "State / UT", "type": "state", "portal_label": "State / Union Territory"},
    "pincode": {"label": "PIN code", "type": "text", "placeholder": "500001", "portal_label": "PIN Code"},
    "photo": {"label": "Photograph", "type": "photo", "portal_label": "Upload Photograph",
              "spec": {"max_kb": 50, "min_kb": 4, "formats": ["jpg", "jpeg"], "width_cm": 2.5, "height_cm": 3.5, "dpi": 200},
              "help": "Recent colour passport-size photo, white background, face clearly visible. Checked on your device."},
    "signature": {"label": "Signature", "type": "photo", "portal_label": "Upload Signature",
                  "spec": {"max_kb": 50, "min_kb": 2, "formats": ["jpg", "jpeg"], "width_cm": 4.5, "height_cm": 2.0, "dpi": 200},
                  "help": "Sign on white paper with black ink, crop tightly. Checked on your device."},
    "proofs": {"label": "Which proof documents will you use?", "type": "multiselect",
               "options": ["Aadhaar", "Passport", "Voter ID", "Driving Licence", "Bank statement (≤3 months)", "Electricity bill (≤3 months)",
                           "Birth certificate", "Matriculation certificate", "Marriage certificate", "Gazette notification"],
               "portal_label": "Documents submitted as Proof of Identity / Address / DOB"},
    "change_fields": {"label": "What do you want to change?", "type": "multiselect",
                      "options": ["Name", "Father's name", "Date of birth", "Gender", "Photo", "Signature", "Address", "Mobile / Email"],
                      "portal_label": "Tick the checkbox to the left of each field being changed"},
    "other_pans": {"label": "Other PAN(s) you hold (to surrender)", "type": "text", "portal_label": "Other PANs inadvertently allotted", "upper": True},
    "ack_number": {"label": "Acknowledgement / coupon number", "type": "text", "portal_label": "Acknowledgement Number"},
}

CHANGE_PROOF_HINTS = {
    "Name": "Marriage certificate, gazette notification, or Aadhaar with the new name",
    "Father's name": "Aadhaar/passport/birth certificate showing the father's name",
    "Date of birth": "Birth certificate, matriculation certificate, passport or Aadhaar with full DOB",
    "Address": "Aadhaar, bank statement or utility bill (≤3 months) with the new address",
    "Photo": "New photograph meeting the size spec",
    "Signature": "New signature scan meeting the size spec",
}


@lru_cache(maxsize=1)
def load_services() -> dict[str, dict]:
    data = json.loads((DATA_DIR / "services.json").read_text(encoding="utf-8"))
    return {s["id"]: s for s in data["services"]}


@lru_cache(maxsize=1)
def load_meta() -> dict:
    return json.loads((DATA_DIR / "services.json").read_text(encoding="utf-8"))["_meta"]


@lru_cache(maxsize=1)
def load_flows() -> dict:
    return json.loads((DATA_DIR / "flows.json").read_text(encoding="utf-8"))


SUPPORTED_LANGS = ("en", "hi", "te")


@lru_cache(maxsize=4)
def _overlay(lang: str) -> dict:
    path = DATA_DIR / "i18n" / f"services.{lang}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"services": {}, "fields": {}}


def _set_path(obj, path: str, value: str) -> None:
    keys = [int(k) if k.isdigit() else k for k in path.split(".")]
    for k in keys[:-1]:
        obj = obj[k]
    obj[keys[-1]] = value


def localize(svc: dict, lang: str | None) -> dict:
    """Return a copy of the service card with Hindi/Telugu text where available (English is the fallback)."""
    if not svc or not lang or lang == "en" or lang not in SUPPORTED_LANGS:
        return svc
    tr = _overlay(lang)["services"].get(svc["id"], {})
    out = copy.deepcopy(svc)
    for path, text in tr.get("paths", {}).items():
        try:
            _set_path(out, path, text)
        except (KeyError, IndexError, TypeError):
            pass  # English changed since translation - keep English for that string
    for key in ("title", "short"):
        if tr.get(key):
            out[key] = tr[key]
    out["lang"] = lang
    return out


def get_service(service_id: str, lang: str | None = None) -> dict | None:
    return localize(load_services().get(service_id), lang)


def service_form(service_id: str, lang: str | None = None) -> list[dict]:
    svc = load_services().get(service_id)
    if not svc:
        return []
    ids = list(svc.get("form_fields", []))
    if "full_name" in ids and "proof_name" not in ids:
        ids.insert(ids.index("full_name") + 1, "proof_name")  # enables the name-mismatch check
    tr = _overlay(lang)["fields"] if lang in ("hi", "te") else {}
    form = []
    for f in ids:
        meta = dict(FIELDS.get(f, {"label": f, "type": "text"}))
        for key in ("label", "help"):
            if tr.get(f"{f}.{key}"):
                meta[key] = tr[f"{f}.{key}"]
        form.append({"id": f, **meta})
    return form
