from pathlib import Path

import pytest

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


def test_http_config_from_env(monkeypatch) -> None:
    monkeypatch.setenv("LITE_RAG_EMBED_PROVIDER", "http")
    monkeypatch.setenv("LITE_RAG_EMBED_API_URL", "https://example.com/embeddings")
    monkeypatch.setenv("LITE_RAG_EMBED_MODEL", "custom-model")
    monkeypatch.setenv("LITE_RAG_EMBED_API_KEY", "secret")
    config = LiteRAGConfig.from_env()
    assert config.embedding_provider == "http"
    assert config.embedding_model_name == "custom-model"
    assert config.embedding_api_key == "secret"
    assert "secret" not in repr(config)


@pytest.mark.parametrize("name,value", [
    ("LITE_RAG_EMBED_PROVIDER", "unknown"),
    ("LITE_RAG_RERANK_PROVIDER", "unknown"),
    ("LITE_RAG_EMBED_PROVIDER", "http"),
    ("LITE_RAG_EMBED_BATCH_SIZE", "0"),
    ("LITE_RAG_MODEL_API_TIMEOUT", "0"),
])
def test_invalid_provider_config_is_rejected(monkeypatch, name, value) -> None:
    monkeypatch.delenv("LITE_RAG_EMBED_API_URL", raising=False)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        LiteRAGConfig.from_env()


def test_disabled_http_reranker_needs_no_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("LITE_RAG_ENABLE_RERANKER", "false")
    monkeypatch.setenv("LITE_RAG_RERANK_PROVIDER", "http")
    monkeypatch.delenv("LITE_RAG_RERANK_API_URL", raising=False)
    assert LiteRAGConfig.from_env().enable_reranker is False


def test_repo_dotenv_does_not_override_environment(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config_module, "__file__", str(tmp_path / "src/lite_rag/config.py"))
    (tmp_path / ".env").write_text(
        "LITE_RAG_EMBED_MODEL=dotenv-model\nLITE_RAG_EMBED_BATCH_SIZE=7\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LITE_RAG_EMBED_MODEL", "shell-model")
    monkeypatch.delenv("LITE_RAG_EMBED_BATCH_SIZE", raising=False)
    config_module.load_environment()
    config = LiteRAGConfig.from_env()
    assert config.embedding_model_name == "shell-model"
    assert config.embedding_batch_size == 7
