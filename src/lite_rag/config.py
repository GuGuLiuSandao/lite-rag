from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def load_environment() -> None:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


SUPPORTED_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".jsonl",
    ".csv",
    ".tsv",
    ".yaml",
    ".yml",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".htm",
    ".xml",
    ".rst",
    ".log",
}


@dataclass(slots=True)
class LiteRAGConfig:
    storage_root: Path
    db_dir: Path
    files_dir: Path
    metadata_db_path: Path
    chunks_table_name: str = "rag_chunks"
    embedding_model_name: str = "BAAI/bge-m3"
    reranker_model_name: str = "BAAI/bge-reranker-v2-m3"
    enable_reranker: bool = True
    default_mode: str = "hybrid"
    chunk_size: int = 800
    chunk_overlap: int = 120
    embedding_provider: str = "local"
    embedding_api_url: str | None = field(default=None, repr=False)
    embedding_api_key: str | None = field(default=None, repr=False)
    embedding_batch_size: int = 32
    reranker_provider: str = "local"
    reranker_api_url: str | None = field(default=None, repr=False)
    reranker_api_key: str | None = field(default=None, repr=False)
    model_api_timeout: float = 30.0

    def __post_init__(self) -> None:
        for name, provider, url, enabled in (
            ("EMBED", self.embedding_provider, self.embedding_api_url, True),
            ("RERANK", self.reranker_provider, self.reranker_api_url, self.enable_reranker),
        ):
            if provider not in {"local", "http"}:
                raise ValueError(f"LITE_RAG_{name}_PROVIDER must be local or http")
            if enabled and provider == "http" and not url:
                raise ValueError(f"LITE_RAG_{name}_API_URL is required for http")
        if self.embedding_batch_size < 1:
            raise ValueError("LITE_RAG_EMBED_BATCH_SIZE must be positive")
        if not math.isfinite(self.model_api_timeout) or self.model_api_timeout <= 0:
            raise ValueError("LITE_RAG_MODEL_API_TIMEOUT must be positive")

    @classmethod
    def from_env(cls) -> "LiteRAGConfig":
        raw_root = os.getenv("LITE_RAG_STORAGE_ROOT")
        if raw_root:
            storage_root = Path(raw_root).expanduser().resolve()
        else:
            storage_root = cls._default_storage_root()

        db_dir = storage_root / "db"
        files_dir = storage_root / "files"
        metadata_db_path = storage_root / "metadata.sqlite3"

        return cls(
            storage_root=storage_root,
            db_dir=db_dir,
            files_dir=files_dir,
            metadata_db_path=metadata_db_path,
            chunks_table_name=os.getenv("LITE_RAG_CHUNKS_TABLE", "rag_chunks"),
            embedding_model_name=os.getenv("LITE_RAG_EMBED_MODEL", "BAAI/bge-m3"),
            reranker_model_name=os.getenv(
                "LITE_RAG_RERANK_MODEL", "BAAI/bge-reranker-v2-m3"
            ),
            enable_reranker=os.getenv("LITE_RAG_ENABLE_RERANKER", "true").lower()
            in {"1", "true", "yes", "on"},
            default_mode=os.getenv("LITE_RAG_DEFAULT_MODE", "hybrid"),
            chunk_size=int(os.getenv("LITE_RAG_CHUNK_SIZE", "800")),
            chunk_overlap=int(os.getenv("LITE_RAG_CHUNK_OVERLAP", "120")),
            embedding_provider=os.getenv("LITE_RAG_EMBED_PROVIDER", "local").lower(),
            embedding_api_url=os.getenv("LITE_RAG_EMBED_API_URL"),
            embedding_api_key=os.getenv("LITE_RAG_EMBED_API_KEY"),
            embedding_batch_size=int(os.getenv("LITE_RAG_EMBED_BATCH_SIZE", "32")),
            reranker_provider=os.getenv("LITE_RAG_RERANK_PROVIDER", "local").lower(),
            reranker_api_url=os.getenv("LITE_RAG_RERANK_API_URL"),
            reranker_api_key=os.getenv("LITE_RAG_RERANK_API_KEY"),
            model_api_timeout=float(os.getenv("LITE_RAG_MODEL_API_TIMEOUT", "30")),
        )

    @staticmethod
    def _default_storage_root() -> Path:
        repo_root = Path(__file__).resolve().parents[2]
        return (repo_root / ".lite-rag").resolve()

    def ensure_dirs(self) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
