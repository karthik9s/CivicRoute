import os
import sys
from pathlib import Path

# Fast, offline, deterministic test configuration - must be set before importing the app.
os.environ["EMBEDDING_MODEL"] = "hash"
os.environ["VECTOR_STORE"] = "memory"
os.environ["LLM_PROVIDER"] = "none"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from app import store as store_mod  # noqa: E402
from app.embeddings import get_embedder  # noqa: E402
from app.store import Chunk, MemoryStore  # noqa: E402
from ingest.chunker import make_chunks  # noqa: E402
from ingest.run import kb_docs, service_card_docs  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def test_index(tmp_path_factory):
    """Index the service cards + curated KB (no network) into a temp MemoryStore."""
    st = MemoryStore(path=tmp_path_factory.mktemp("index"))
    emb = get_embedder()
    chunks = []
    for d in service_card_docs() + kb_docs():
        for c in make_chunks(d["sections"], source_id=d["source_id"], title=d["title"]):
            chunks.append(Chunk(id=c["id"], source_url=d["url"], title=d["title"], content=c["content"], portal=d["portal"],
                                service_ids=d["service_ids"], section=c["section"], content_hash=c["content_hash"],
                                last_verified=d["last_verified"], origin=d["origin"]))
    st.upsert(chunks, emb.embed_documents([c.title + "\n" + c.content for c in chunks]), emb.name)
    store_mod._store = st
    yield st
    store_mod._store = None
