"""HTML/PDF/Markdown -> clean text -> heading-aware chunks."""
from __future__ import annotations

import hashlib
import io
import re

from bs4 import BeautifulSoup

NOISE_TAGS = ["script", "style", "noscript", "nav", "footer", "header", "form", "iframe", "svg", "button", "select"]
NOISE_SELECTORS = [".breadcrumb", ".navbar", ".menu", ".footer", ".header", "#header", "#footer", ".skip-link",
                   ".social", ".cookie", "[role=navigation]", ".language-switcher", ".sidebar"]


def html_to_sections(html: str) -> list[tuple[str, str]]:
    """Return [(heading, text)] from the main content of a page."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(NOISE_TAGS):
        t.decompose()
    for sel in NOISE_SELECTORS:
        for t in soup.select(sel):
            t.decompose()
    main = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.find("article") or soup.body or soup
    for li in main.find_all("li"):
        li.insert_before("\n- ")
    for tr in main.find_all("tr"):
        tr.append(" \n")
    for td in main.find_all(["td", "th"]):
        td.append(" | ")

    sections: list[tuple[str, str]] = []
    heading, buf = "", []
    for el in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "table", "div"], recursive=True):
        if el.name in ("h1", "h2", "h3", "h4"):
            if buf:
                sections.append((heading, "\n".join(buf)))
                buf = []
            heading = clean(el.get_text(" "))
            continue
        if el.name == "div" and el.find(["p", "li", "table", "div", "h1", "h2", "h3", "h4"]):
            continue  # only leaf divs carry text
        if el.find_parent(["li", "table"]) and el.name != "table":
            continue  # avoid duplicate text from nested elements
        text = clean(el.get_text(" "))
        if text and (not buf or buf[-1] != text):
            buf.append(("- " + text) if el.name == "li" else text)
    if buf:
        sections.append((heading, "\n".join(buf)))
    return [(h, t) for h, t in sections if len(t) > 40]


def pdf_to_sections(data: bytes) -> list[tuple[str, str]]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return [(f"Page {i}", clean(p.extract_text() or "")) for i, p in enumerate(reader.pages, 1) if (p.extract_text() or "").strip()]


def markdown_to_sections(md: str) -> list[tuple[str, str]]:
    sections, heading, buf = [], "", []
    for line in md.splitlines():
        m = re.match(r"^#{1,4}\s+(.*)", line)
        if m:
            if buf:
                sections.append((heading, "\n".join(buf).strip()))
                buf = []
            heading = m.group(1).strip()
        else:
            buf.append(line)
    if buf:
        sections.append((heading, "\n".join(buf).strip()))
    return [(h, t) for h, t in sections if t]


def clean(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def split_text(text: str, max_chars: int = 1100, overlap: int = 150) -> list[str]:
    """Split on paragraph/sentence boundaries into ~max_chars windows with overlap."""
    if len(text) <= max_chars:
        return [text]
    units = re.split(r"(?<=\n)|(?<=[.!?])\s+", text)
    chunks, cur = [], ""
    for u in units:
        if len(cur) + len(u) > max_chars and cur:
            chunks.append(cur.strip())
            cur = cur[-overlap:] + u
        else:
            cur += u if cur.endswith(("\n", " ")) or not cur else " " + u
    if cur.strip():
        chunks.append(cur.strip())
    return chunks


def make_chunks(sections: list[tuple[str, str]], *, source_id: str, title: str, max_chars: int = 1100) -> list[dict]:
    out = []
    for si, (heading, text) in enumerate(sections):
        for pi, piece in enumerate(split_text(text, max_chars)):
            body = (f"{heading}\n{piece}" if heading and not piece.startswith(heading) else piece).strip()
            h = hashlib.sha1(body.encode()).hexdigest()[:16]
            out.append({"id": f"{source_id}:{si}:{pi}", "section": heading, "content": body, "content_hash": h, "title": title})
    return out
