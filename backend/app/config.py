"""Runtime configuration, read from environment variables (and an optional .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"


def _load_dotenv() -> None:
    """Minimal .env loader so we don't need python-dotenv. Existing env vars win."""
    for candidate in (BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"):
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    # Vector store: "pgvector" (default when DATABASE_URL set) or "memory" (local file index).
    database_url: str = os.getenv("DATABASE_URL", "")
    vector_store: str = os.getenv("VECTOR_STORE", "auto")

    # Embeddings: a sentence-transformers model name, or "hash" for a dependency-free test embedder.
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    reranker_model: str = os.getenv("RERANKER_MODEL", "")  # e.g. BAAI/bge-reranker-base; empty = off

    # LLM: "auto" picks the first provider with a key (groq, anthropic, xai, gemini, openai); "none" = extractive only.
    llm_provider: str = os.getenv("LLM_PROVIDER", "auto")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    xai_model: str = os.getenv("XAI_MODEL", "grok-4.3")

    top_k: int = int(os.getenv("TOP_K", "6"))
    min_score: float = float(os.getenv("MIN_RETRIEVAL_SCORE", "0.0"))
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    )

    index_path: Path = DATA_DIR / "index"
    kb_dir: Path = DATA_DIR / "kb"
    raw_dir: Path = DATA_DIR / "raw"

    @property
    def use_pgvector(self) -> bool:
        if self.vector_store == "memory":
            return False
        if self.vector_store == "pgvector":
            return True
        return bool(self.database_url)


settings = Settings()
