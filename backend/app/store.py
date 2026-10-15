"""Vector stores with hybrid (semantic + keyword) search.

PgVectorStore  - production: PostgreSQL + pgvector (cosine) + tsvector full-text, fused with RRF.
MemoryStore    - local/dev/tests: numpy cosine + in-process BM25, persisted to data/index/.

Both return the same `Hit` objects so the rest of the app doesn't care which one is used.
"""
from __future__ import annotations

import json
import logging
import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .config import settings
from .embeddings import get_embedder, keyword_tokens, tokenize

log = logging.getLogger(__name__)
RRF_K = 60


@dataclass
class Chunk:
    id: str
    source_url: str
    title: str
    content: str
    portal: str = ""
    service_ids: list[str] = field(default_factory=list)
    section: str = ""
    content_hash: str = ""
    last_verified: str = ""
    origin: str = "kb"  # kb = curated, crawl = fetched from official site


@dataclass
class Hit:
    chunk: Chunk
    score: float
    vector_score: float = 0.0
    keyword_score: float = 0.0


def rrf_fuse(rankings: list[list[str]]) -> dict[str, float]:
    """Reciprocal Rank Fusion: robust way to merge vector + keyword rankings."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
    return scores


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = docs
        self.avgdl = (sum(len(d) for d in docs) / len(docs)) if docs else 0.0
        self.tf = [Counter(d) for d in docs]
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        out = np.zeros(len(self.docs), dtype=np.float32)
        for i, tf in enumerate(self.tf):
            dl = len(self.docs[i])
            s = 0.0
            for q in query:
                if q not in tf:
                    continue
                f = tf[q]
                s += self.idf.get(q, 0.0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1)))
            out[i] = s
        return out


class MemoryStore:
    def __init__(self, path: Path | None = None):
        self.path = path or settings.index_path
        self.chunks: list[Chunk] = []
        self.vectors = np.zeros((0, 1), dtype=np.float32)
        self.embedder_name = ""
        self._bm25: BM25 | None = None
        self.load()

    # ---- persistence -------------------------------------------------
    def load(self) -> None:
        meta = self.path / "chunks.json"
        vecs = self.path / "vectors.npy"
        if meta.exists() and vecs.exists():
            data = json.loads(meta.read_text(encoding="utf-8"))
            self.embedder_name = data.get("embedder", "")
            self.chunks = [Chunk(**c) for c in data["chunks"]]
            self.vectors = np.load(vecs)
            self._bm25 = None

    def save(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / "chunks.json").write_text(
            json.dumps({"embedder": self.embedder_name, "chunks": [asdict(c) for c in self.chunks]}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        np.save(self.path / "vectors.npy", self.vectors)

    # ---- writes ------------------------------------------------------
    def existing_hashes(self) -> dict[str, str]:
        if self.embedder_name and self.embedder_name != get_embedder().name:
            return {}  # vectors came from another model: re-embed everything
        return {c.id: c.content_hash for c in self.chunks}

    def upsert(self, chunks: list[Chunk], vectors: np.ndarray, embedder_name: str) -> None:
        if self.embedder_name and self.embedder_name != embedder_name:
            log.warning("Embedder changed (%s -> %s); rebuilding index", self.embedder_name, embedder_name)
            self.chunks, self.vectors = [], np.zeros((0, vectors.shape[1]), np.float32)
        self.embedder_name = embedder_name
        by_id = {c.id: i for i, c in enumerate(self.chunks)}
        if self.vectors.shape[0] == 0:
            self.vectors = np.zeros((0, vectors.shape[1]), np.float32)
        for chunk, vec in zip(chunks, vectors):
            if chunk.id in by_id:
                i = by_id[chunk.id]
                self.chunks[i] = chunk
                self.vectors[i] = vec
            else:
                by_id[chunk.id] = len(self.chunks)
                self.chunks.append(chunk)
                self.vectors = np.vstack([self.vectors, vec[None, :]])
        self._bm25 = None

    def delete_missing(self, keep_ids: set[str]) -> int:
        keep = [i for i, c in enumerate(self.chunks) if c.id in keep_ids]
        removed = len(self.chunks) - len(keep)
        self.chunks = [self.chunks[i] for i in keep]
        self.vectors = self.vectors[keep] if keep else np.zeros((0, self.vectors.shape[1]), np.float32)
        self._bm25 = None
        return removed

    # ---- reads -------------------------------------------------------
    def count(self) -> int:
        return len(self.chunks)

    def search(self, query: str, k: int = 6, service_id: str | None = None) -> list[Hit]:
        if not self.chunks:
            return []
        embedder = get_embedder()
        if self.embedder_name and embedder.name != self.embedder_name:
            log.warning("Index built with %s but querying with %s - re-run ingestion", self.embedder_name, embedder.name)
        if self._bm25 is None:
            self._bm25 = BM25([keyword_tokens(c.title + " " + c.content) for c in self.chunks])

        qv = embedder.embed_query(query)
        vec_scores = self.vectors @ qv if self.vectors.shape[1] == qv.shape[0] else np.zeros(len(self.chunks))
        kw_scores = self._bm25.scores(keyword_tokens(query))

        idx = np.arange(len(self.chunks))
        if service_id:
            mask = np.array([service_id in c.service_ids or not c.service_ids for c in self.chunks])
            if mask.any():
                idx = idx[mask]
        n = min(len(idx), max(k * 4, 20))
        vec_rank = [self.chunks[i].id for i in idx[np.argsort(-vec_scores[idx])][:n]]
        kw_rank = [self.chunks[i].id for i in idx[np.argsort(-kw_scores[idx])][:n] if kw_scores[i] > 0]
        fused = rrf_fuse([vec_rank, kw_rank])
        pos = {c.id: i for i, c in enumerate(self.chunks)}
        ordered = sorted(fused.items(), key=lambda x: -x[1])[:k]
        return [
            Hit(self.chunks[pos[cid]], s, float(vec_scores[pos[cid]]), float(kw_scores[pos[cid]]))
            for cid, s in ordered
        ]


SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS chunks (
    id            TEXT PRIMARY KEY,
    source_url    TEXT NOT NULL,
    title         TEXT NOT NULL,
    section       TEXT DEFAULT '',
    content       TEXT NOT NULL,
    portal        TEXT DEFAULT '',
    service_ids   TEXT[] DEFAULT '{{}}',
    content_hash  TEXT NOT NULL,
    last_verified TEXT DEFAULT '',
    origin        TEXT DEFAULT 'kb',
    embedder      TEXT NOT NULL,
    embedding     vector({dim}) NOT NULL,
    tsv           tsvector GENERATED ALWAYS AS (to_tsvector('simple', title || ' ' || content)) STORED,
    updated_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_service_idx ON chunks USING gin (service_ids);
"""


class PgVectorStore:
    def __init__(self, dsn: str | None = None):
        import psycopg
        from pgvector.psycopg import register_vector

        self.dsn = dsn or settings.database_url
        self._psycopg = psycopg
        self._register_vector = register_vector
        self.dim = get_embedder().dim
        with self._conn(register=False) as conn:
            conn.execute(SCHEMA_SQL.format(dim=self.dim))

    def _conn(self, register: bool = True):
        conn = self._psycopg.connect(self.dsn, autocommit=True, connect_timeout=3)  # fail fast if Docker is down
        if register:
            self._register_vector(conn)
        return conn

    def existing_hashes(self) -> dict[str, str]:
        with self._conn() as conn:
            # only chunks embedded by the current model count as up to date
            return dict(conn.execute("SELECT id, content_hash FROM chunks WHERE embedder = %s",
                                     (get_embedder().name,)).fetchall())

    def upsert(self, chunks: list[Chunk], vectors: np.ndarray, embedder_name: str) -> None:
        with self._conn() as conn:
            stale = conn.execute("SELECT count(*) FROM chunks WHERE embedder <> %s", (embedder_name,)).fetchone()[0]
            if stale:
                log.warning("Embedder changed; clearing %d stale chunks", stale)
                conn.execute("DELETE FROM chunks WHERE embedder <> %s", (embedder_name,))
            with conn.cursor() as cur:
                for c, v in zip(chunks, vectors):
                    cur.execute(
                        """INSERT INTO chunks (id, source_url, title, section, content, portal, service_ids,
                                               content_hash, last_verified, origin, embedder, embedding)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (id) DO UPDATE SET source_url=EXCLUDED.source_url, title=EXCLUDED.title,
                             section=EXCLUDED.section, content=EXCLUDED.content, portal=EXCLUDED.portal,
                             service_ids=EXCLUDED.service_ids, content_hash=EXCLUDED.content_hash,
                             last_verified=EXCLUDED.last_verified, origin=EXCLUDED.origin,
                             embedder=EXCLUDED.embedder, embedding=EXCLUDED.embedding, updated_at=now()""",
                        (c.id, c.source_url, c.title, c.section, c.content, c.portal, c.service_ids,
                         c.content_hash, c.last_verified, c.origin, embedder_name, v),
                    )

    def delete_missing(self, keep_ids: set[str]) -> int:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM chunks WHERE NOT (id = ANY(%s))", (list(keep_ids),))
            return cur.rowcount

    def save(self) -> None:  # writes are immediate
        pass

    def count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT count(*) FROM chunks").fetchone()[0]

    def search(self, query: str, k: int = 6, service_id: str | None = None) -> list[Hit]:
        qv = get_embedder().embed_query(query)
        n = max(k * 4, 20)
        svc_filter = "AND (%(svc)s = ANY(service_ids) OR cardinality(service_ids) = 0)" if service_id else ""
        cols = "id, source_url, title, content, portal, service_ids, section, content_hash, last_verified, origin"
        params = {"qv": qv, "q": query, "n": n, "svc": service_id}
        with self._conn() as conn:
            vec_rows = conn.execute(
                f"SELECT {cols}, 1 - (embedding <=> %(qv)s) AS s FROM chunks WHERE true {svc_filter} "
                f"ORDER BY embedding <=> %(qv)s LIMIT %(n)s", params).fetchall()
            kw_rows = conn.execute(
                f"SELECT {cols}, ts_rank(tsv, websearch_to_tsquery('simple', %(q)s)) AS s FROM chunks "
                f"WHERE tsv @@ websearch_to_tsquery('simple', %(q)s) {svc_filter} ORDER BY s DESC LIMIT %(n)s",
                params).fetchall()
            if not kw_rows:  # websearch syntax is AND-ish; fall back to OR of terms
                terms = " | ".join(t for t in tokenize(query) if len(t) > 2) or "pan"
                params["q"] = terms
                kw_rows = conn.execute(
                    f"SELECT {cols}, ts_rank(tsv, to_tsquery('simple', %(q)s)) AS s FROM chunks "
                    f"WHERE tsv @@ to_tsquery('simple', %(q)s) {svc_filter} ORDER BY s DESC LIMIT %(n)s",
                    params).fetchall()

        rows: dict[str, Chunk] = {}
        vs: dict[str, float] = {}
        ks: dict[str, float] = {}
        for r in vec_rows:
            rows[r[0]] = Chunk(*r[:10])
            vs[r[0]] = float(r[10])
        for r in kw_rows:
            rows.setdefault(r[0], Chunk(*r[:10]))
            ks[r[0]] = float(r[10])
        fused = rrf_fuse([[r[0] for r in vec_rows], [r[0] for r in kw_rows]])
        ordered = sorted(fused.items(), key=lambda x: -x[1])[:k]
        return [Hit(rows[cid], s, vs.get(cid, 0.0), ks.get(cid, 0.0)) for cid, s in ordered]


_store = None


def get_store():
    global _store
    if _store is None:
        if settings.use_pgvector:
            try:
                _store = PgVectorStore()
                log.info("Using pgvector store")
            except Exception as exc:
                if settings.vector_store == "pgvector":
                    raise
                log.warning("pgvector unavailable (%s); using local MemoryStore", exc)
                _store = MemoryStore()
        else:
            _store = MemoryStore()
    return _store


def reset_store() -> None:
    global _store
    _store = None
