"""Field validators for the application-prep wizard.

These catch the mistakes that most often get PAN applications rejected *before* the user
reaches the official portal. Aadhaar is deliberately validated in the browser only (see
frontend/src/lib/validate.js); the API refuses to receive it. The Python Verhoeff check
here exists for tests and parity.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from difflib import SequenceMatcher

PAN_RE = re.compile(r"^[A-Z]{3}[ABCEFGHLJPT][A-Z][0-9]{4}[A-Z]$")
PAN_HOLDER_TYPES = {
    "P": "Individual", "C": "Company", "H": "HUF", "F": "Firm / LLP", "A": "Association of Persons",
    "T": "Trust", "B": "Body of Individuals", "L": "Local Authority", "J": "Artificial Juridical Person",
    "G": "Government", "E": "Limited Liability Partnership",
}
MOBILE_RE = re.compile(r"^[6-9]\d{9}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
PIN_RE = re.compile(r"^[1-9][0-9]{5}$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]*$")
ACK_PROTEAN_RE = re.compile(r"^\d{15}$")

# Verhoeff tables (Aadhaar check digit)
_D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],
      [4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],
      [8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
_P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],
      [9,4,5,3,1,2,7,6,0,8],[4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]


@dataclass
class Result:
    ok: bool
    message: str = ""
    level: str = "error"  # error | warning | info
    normalized: str | None = None

    def as_dict(self) -> dict:
        return {"ok": self.ok, "message": self.message, "level": self.level, "normalized": self.normalized}


def verhoeff_valid(num: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(num)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def validate_pan(value: str, full_name: str | None = None) -> Result:
    v = (value or "").strip().upper().replace(" ", "")
    if not v:
        return Result(False, "PAN is required.")
    if len(v) != 10:
        return Result(False, "PAN must be exactly 10 characters (e.g. ABCPE1234F).", normalized=v)
    if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", v):
        return Result(False, "PAN format is 5 letters, 4 digits, 1 letter (e.g. ABCPE1234F). Check for O vs 0 or I vs 1.", normalized=v)
    if not PAN_RE.match(v):
        return Result(False, f"4th character '{v[3]}' is not a valid PAN holder type.", normalized=v)
    holder = PAN_HOLDER_TYPES.get(v[3], "Unknown")
    if full_name:
        surname_initial = _surname(full_name)[:1].upper()
        if v[3] == "P" and surname_initial and v[4] != surname_initial:
            return Result(True, f"Valid format ({holder}). Note: 5th character '{v[4]}' usually matches your surname's first letter "
                                f"('{surname_initial}'). Double-check the PAN.", "warning", v)
    return Result(True, f"Valid format — holder type: {holder}.", "info", v)


def _surname(name: str) -> str:
    parts = name.strip().split()
    return parts[-1] if parts else ""


def validate_aadhaar(value: str) -> Result:
    v = re.sub(r"\s|-", "", value or "")
    if not re.fullmatch(r"[2-9]\d{11}", v):
        return Result(False, "Aadhaar must be 12 digits and cannot start with 0 or 1.")
    if not verhoeff_valid(v):
        return Result(False, "This Aadhaar number fails the checksum — check for a typo.")
    return Result(True, "Looks valid.", "info", "XXXX XXXX " + v[-4:])


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def validate_name(value: str, label: str = "Name") -> Result:
    v = " ".join(_strip_accents(value or "").split())
    if not v:
        return Result(False, f"{label} is required.")
    if not NAME_RE.match(v):
        return Result(False, f"{label} can contain only English letters, spaces, dot, apostrophe and hyphen.")
    if len(v) > 75:
        return Result(False, f"{label} is too long (max 75 characters on PAN forms).")
    if re.search(r"\b(mr|mrs|ms|miss|dr|shri|smt|kumari)\b\.?", v, re.I):
        return Result(False, f"Remove titles like Mr/Mrs/Shri/Smt from {label.lower()} — select title separately on the form.")
    if len(v.replace(".", "").split()) == 1 or re.search(r"\b[A-Za-z]\.", v):
        return Result(True, f"Write {label.lower()} in full exactly as on your proof document; avoid initials if the proof has the full name.", "warning", v.upper())
    return Result(True, "OK", "info", v.upper())


def name_similarity(a: str, b: str) -> float:
    norm = lambda s: " ".join(sorted(_strip_accents(s).upper().replace(".", " ").split()))
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def compare_names(form_name: str, proof_name: str) -> Result:
    """Warn when the name typed on the form differs from the name on the proof (top rejection reason)."""
    if not form_name or not proof_name:
        return Result(True, "", "info")
    if form_name.strip().upper() == proof_name.strip().upper():
        return Result(True, "Names match exactly.", "info")
    score = name_similarity(form_name, proof_name)
    if score >= 0.97:
        return Result(True, "Same words but different order/spacing — use the exact order printed on your proof.", "warning")
    return Result(True, f"Name differs from your proof document ({score:.0%} similar). PAN applications are rejected for "
                        "mismatches — use the name exactly as on the proof, or submit a supporting document "
                        "(gazette notification / marriage certificate).", "warning")


def parse_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime((value or "").strip(), fmt).date()
        except ValueError:
            continue
    return None


def validate_dob(value: str, service_id: str | None = None, today: date | None = None) -> Result:
    d = parse_date(value)
    today = today or date.today()
    if not d:
        return Result(False, "Enter date of birth as DD/MM/YYYY.")
    if d > today:
        return Result(False, "Date of birth can't be in the future.")
    if d.year < 1900:
        return Result(False, "Please check the year.")
    age = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    if service_id == "instant_epan" and age < 18:
        return Result(False, "Instant e-PAN is not available for minors — apply through the form-based route with a parent as representative.")
    if d.day == 1 and d.month == 1:
        return Result(True, "1 January is often a placeholder date. Make sure it matches your DOB proof exactly.", "warning", d.strftime("%d/%m/%Y"))
    return Result(True, f"OK (age {age}).", "info", d.strftime("%d/%m/%Y"))


def validate_mobile(value: str) -> Result:
    v = re.sub(r"[\s-]", "", value or "")
    v = re.sub(r"^(\+91|91|0)(?=\d{10}$)", "", v)
    if not MOBILE_RE.match(v):
        return Result(False, "Enter a 10-digit Indian mobile number starting with 6–9.")
    return Result(True, "OTPs will be sent here — keep this phone with you while applying.", "info", v)


def validate_email(value: str) -> Result:
    v = (value or "").strip()
    if not EMAIL_RE.match(v):
        return Result(False, "Enter a valid email address — your e-PAN is sent here.")
    return Result(True, "e-PAN PDF will be emailed here.", "info", v.lower())


def validate_pincode(value: str) -> Result:
    v = (value or "").strip()
    if not PIN_RE.match(v):
        return Result(False, "PIN code must be 6 digits and can't start with 0.")
    return Result(True, "OK", "info", v)


def validate_ack(value: str) -> Result:
    v = re.sub(r"\s", "", value or "")
    if ACK_PROTEAN_RE.match(v):
        return Result(True, "Looks like a Protean (NSDL) acknowledgement number.", "info", v)
    if re.fullmatch(r"[A-Za-z0-9]{6,20}", v):
        return Result(True, "Saved. If this is a UTIITSL coupon number, use the UTIITSL tracker.", "info", v.upper())
    return Result(False, "Enter your acknowledgement / coupon number (letters and digits only).")


def validate_required(value: str, label: str = "This field") -> Result:
    return Result(bool((value or "").strip()), "" if (value or "").strip() else f"{label} is required.", "error" if not (value or "").strip() else "info", (value or "").strip())


VALIDATORS = {
    "pan": lambda v, ctx: validate_pan(v, ctx.get("full_name")),
    "full_name": lambda v, ctx: validate_name(v, "Full name"),
    "name_on_card": lambda v, ctx: validate_name(v, "Name on card"),
    "father_name": lambda v, ctx: validate_name(v, "Father's name"),
    "mother_name": lambda v, ctx: validate_name(v, "Mother's name") if (v or "").strip() else Result(True, "Optional", "info"),
    "dob": lambda v, ctx: validate_dob(v, ctx.get("service_id")),
    "mobile": lambda v, ctx: validate_mobile(v),
    "email": lambda v, ctx: validate_email(v),
    "pincode": lambda v, ctx: validate_pincode(v),
    "ack_number": lambda v, ctx: validate_ack(v),
    "address_line1": lambda v, ctx: validate_required(v, "Address line 1"),
    "city": lambda v, ctx: validate_required(v, "City / District"),
    "state": lambda v, ctx: validate_required(v, "State"),
}

SENSITIVE_FIELDS = {"aadhaar", "aadhaar_local"}


def validate_field(field: str, value: str, ctx: dict | None = None) -> Result:
    ctx = ctx or {}
    if field in SENSITIVE_FIELDS:
        return Result(False, "Aadhaar is validated on your device only and is never sent to the server.")
    fn = VALIDATORS.get(field)
    if not fn:
        return Result(True, "", "info", value)
    return fn(value, ctx)


def cross_checks(values: dict) -> list[dict]:
    """Checks spanning several fields. Returns warnings to show on the review screen."""
    out = []
    if values.get("full_name") and values.get("proof_name"):
        r = compare_names(values["full_name"], values["proof_name"])
        if r.level == "warning":
            out.append({"fields": ["full_name"], **r.as_dict()})
    if values.get("full_name") and values.get("name_on_card"):
        a, b = values["full_name"].upper().split(), values["name_on_card"].upper().split()
        if not set(b) <= set(a + [w[0] for w in a]):
            out.append({"fields": ["name_on_card"], "ok": True, "level": "warning",
                        "message": "Name on card should be derived from your full name (same words or initials).", "normalized": None})
    if values.get("pan") and values.get("full_name"):
        r = validate_pan(values["pan"], values["full_name"])
        if r.level == "warning":
            out.append({"fields": ["pan"], **r.as_dict()})
    return out
