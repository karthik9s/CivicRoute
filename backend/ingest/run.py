"""Ingestion pipeline: crawl official sources -> parse -> chunk -> embed -> upsert into the vector store.

    python -m ingest.run              # crawl + index (incremental: only changed chunks are re-embedded)
    python -m ingest.run --offline    # re-index from already-downloaded pages + curated KB only
    python -m ingest.run --rebuild    # drop everything and re-embed

Writes data/ingest_report.json listing sources whose content changed since the last run and the
service cards that should be re-reviewed as a result.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.catalog import load_services  # noqa: E402
from app.config import DATA_DIR, settings  # noqa: E402
from app.embeddings import get_embedder  # noqa: E402
from app.store import Chunk, get_store  # noqa: E402
from ingest.chunker import html_to_sections, make_chunks, markdown_to_sections, pdf_to_sections  # noqa: E402
from ingest.crawler import Crawler, source_id  # noqa: E402

log = logging.getLogger("ingest")
SOURCES_FILE = Path(__file__).with_name("sources.yaml")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        return yaml.safe_load(fm) or {}, body
    return {}, text


def service_card_docs() -> list[dict]:
    """Turn the reviewed service cards into KB documents so chat answers agree with the cards."""
    docs = []
    for s in load_services().values():
        lines = [f"# {s['title']}", s["short"], "", "## Who can use this"] + [f"- {e}" for e in s["eligibility"]]
        if s.get("not_for"):
            lines += ["", "## Use a different service if"] + [f"- {n['when']}: see '{load_services()[n['go_to']]['title']}'" for n in s["not_for"]]
        lines += ["", "## Documents needed"] + [f"- {d}" for d in s["documents"]]
        lines += ["", "## Fees"] + [f"- {f['label']}: {f['amount']}" + (" (confirm on the official payment page)" if f.get("verify") else "") for f in s["fees"]]
        lines += ["", "## Time taken", s["time"], "", "## Steps"]
        lines += [f"{i}. {st['title']}: {st['detail']}" + (f" Link: {st['url']}" if st.get("url") else "") for i, st in enumerate(s["steps"], 1)]
        if s.get("tips"):
            lines += ["", "## Tips"] + [f"- {t}" for t in s["tips"]]
        if s.get("common_rejections"):
            lines += ["", "## Common reasons for rejection or failure"] + [f"- {t}" for t in s["common_rejections"]]
        lines += ["", "## Official links"] + [f"- {l['label']} ({l['portal']}): {l['url']}" for l in s["official_links"]]
        docs.append({"source_id": f"card-{s['id']}", "url": s["official_links"][0]["url"], "title": s["title"],
                     "portal": s["official_links"][0]["portal"], "service_ids": [s["id"]], "last_verified": s["last_verified"],
                     "sections": markdown_to_sections("\n".join(lines)), "origin": "card"})
    return docs


def kb_docs() -> list[dict]:
    docs = []
    for path in sorted(settings.kb_dir.glob("*.md")):
        fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        docs.append({"source_id": f"kb-{path.stem}", "url": fm.get("url", ""), "title": fm.get("title", path.stem),
                     "portal": fm.get("portal", ""), "service_ids": fm.get("service_ids", []),
                     "last_verified": str(fm.get("last_verified", "")), "sections": markdown_to_sections(body), "origin": "kb"})
    return docs


def crawled_docs(sources: list[dict], manifest: dict) -> list[dict]:
    docs = []
    for s in sources:
        rec = manifest.get(s["url"])
        if not rec or not rec.get("file"):
            continue
        path = settings.raw_dir / rec["file"]
        if not path.exists():
            continue
        sections = pdf_to_sections(path.read_bytes()) if rec.get("type") == "pdf" else \
            html_to_sections(path.read_text(encoding="utf-8", errors="ignore"))
        if not sections:
            log.warning("No usable text in %s (JS-rendered page?)", s["url"])
            continue
        docs.append({"source_id": f"web-{source_id(s['url'])}", "url": s["url"], "title": s.get("title", s["url"]),
                     "portal": s.get("portal", ""), "service_ids": s.get("service_ids", []),
                     "last_verified": (rec.get("fetched_at") or "")[:10], "sections": sections, "origin": "crawl"})
    return docs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="don't fetch; use data/raw and the curated KB")
    ap.add_argument("--rebuild", action="store_true", help="re-embed everything")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for noisy in ("httpx", "huggingface_hub", "sentence_transformers", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    run_pipeline(offline=args.offline, rebuild=args.rebuild)


def run_pipeline(offline: bool = False, rebuild: bool = False, write_report: bool = True) -> dict:
    """Crawl (unless offline) -> chunk -> embed -> upsert. Returns the ingest report. Also used by the API
    on startup to fill an empty vector store (e.g. a fresh Docker volume)."""
    sources = yaml.safe_load(SOURCES_FILE.read_text(encoding="utf-8"))["sources"]
    crawler = Crawler(settings.raw_dir)
    crawl_results = [] if offline else crawler.crawl(sources)

    docs = service_card_docs() + kb_docs() + crawled_docs(sources, crawler.manifest)
    chunks: list[Chunk] = []
    for d in docs:
        for c in make_chunks(d["sections"], source_id=d["source_id"], title=d["title"]):
            chunks.append(Chunk(id=c["id"], source_url=d["url"], title=d["title"], content=c["content"], portal=d["portal"],
                                service_ids=list(d["service_ids"]), section=c["section"], content_hash=c["content_hash"],
                                last_verified=d["last_verified"], origin=d["origin"]))
    log.info("%d documents -> %d chunks", len(docs), len(chunks))

    store = get_store()
    embedder = get_embedder()
    existing = {} if rebuild else store.existing_hashes()
    todo = [c for c in chunks if existing.get(c.id) != c.content_hash]
    if rebuild and hasattr(store, "chunks"):
        store.chunks, store.vectors = [], store.vectors[:0]
    log.info("Embedding %d new/changed chunks with %s (%d unchanged)", len(todo), embedder.name, len(chunks) - len(todo))
    for i in range(0, len(todo), 64):
        batch = todo[i:i + 64]
        store.upsert(batch, embedder.embed_documents([f"{c.title}\n{c.content}" for c in batch]), embedder.name)
    removed = store.delete_missing({c.id for c in chunks})
    store.save()

    services = load_services()
    changed = [r for r in crawl_results if r.get("changed")]
    review = sorted({sid for r in changed for s in sources if s["url"] == r["url"] for sid in s.get("service_ids", [])})
    failed = [{"url": r["url"], "status": r["status"]} for r in crawl_results if r.get("status") != "ok"]
    report = {"date": date.today().isoformat(), "store": type(store).__name__, "embedder": embedder.name,
              "documents": len(docs), "chunks": len(chunks), "embedded": len(todo), "removed": removed,
              "changed_sources": [r["url"] for r in changed], "failed_sources": failed,
              "cards_to_review": [{"id": sid, "title": services[sid]["title"]} for sid in review if sid in services]}
    if write_report:  # only real runs update "last checked" - startup syncs must not fake freshness
        (DATA_DIR / "ingest_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    log.info("Done: %s", json.dumps({k: v for k, v in report.items() if k not in ("failed_sources",)}, ensure_ascii=False))
    if review:
        log.warning("Official pages changed - re-review these service cards: %s", ", ".join(review))
    return report


if __name__ == "__main__":
    main()
