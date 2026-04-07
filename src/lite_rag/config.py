from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
        )

    @staticmethod
    def _default_storage_root() -> Path:
        repo_root = Path(__file__).resolve().parents[2]
        return (repo_root / ".lite-rag").resolve()

    def ensure_dirs(self) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
