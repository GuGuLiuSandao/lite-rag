from pathlib import Path

import lite_rag.config as config_module
from lite_rag.config import LiteRAGConfig


def test_config_builds_paths_from_env(monkeypatch) -> None:
    monkeypatch.setenv("LITE_RAG_STORAGE_ROOT", "/tmp/lite-rag-test-root")

    config = LiteRAGConfig.from_env()
    expected_root = Path("/tmp/lite-rag-test-root").resolve()

    assert config.storage_root == expected_root
    assert config.db_dir == expected_root / "db"
    assert config.files_dir == expected_root / "files"
    assert config.metadata_db_path == expected_root / "metadata.sqlite3"


def test_config_uses_repo_default_when_storage_root_unset(monkeypatch) -> None:
    monkeypatch.delenv("LITE_RAG_STORAGE_ROOT", raising=False)
    monkeypatch.delenv("LITE_RAG_ENABLE_RERANKER", raising=False)

    config = LiteRAGConfig.from_env()
    expected_repo_root = Path(config_module.__file__).resolve().parents[2]

    assert config.storage_root == expected_repo_root / ".lite-rag"
    assert config.metadata_db_path == config.storage_root / "metadata.sqlite3"
    assert config.enable_reranker is True


def test_config_enable_reranker_env_override(monkeypatch) -> None:
    monkeypatch.setenv("LITE_RAG_ENABLE_RERANKER", "false")

    config = LiteRAGConfig.from_env()

    assert config.enable_reranker is False
