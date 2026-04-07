from __future__ import annotations

import json
from pathlib import Path

import pytest

from lite_rag.config import LiteRAGConfig
from lite_rag.metadata import SQLiteMetadataStore
from lite_rag.store import LiteRAGStore


def test_metadata_store_migrates_legacy_manifest(tmp_path) -> None:
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True)
    manifest_path = storage_root / "manifest.json"

    manifest_path.write_text(
        json.dumps(
            {
                "knowledge_bases": {
                    "kb-1": {
                        "id": "kb-1",
                        "name": "产品文档",
                        "description": "",
                        "created_at": "2024-01-01T00:00:00+00:00",
                        "updated_at": "2024-01-01T00:00:00+00:00",
                    }
                },
                "files": {
                    "file-1": {
                        "id": "file-1",
                        "kb_id": "kb-1",
                        "kb_name": "产品文档",
                        "title": "demo.md",
                        "source_name": "demo.md",
                        "stored_path": str(
                            storage_root / "files" / "kb-1" / "file-1.md"
                        ),
                        "chunk_count": 2,
                        "created_at": "2024-01-01T00:00:00+00:00",
                        "updated_at": "2024-01-01T00:00:00+00:00",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    metadata = SQLiteMetadataStore(
        db_path=storage_root / "metadata.sqlite3",
        legacy_manifest_path=manifest_path,
    )

    kb = metadata.get_kb("产品文档")
    files = metadata.list_files(kb_ref="产品文档")

    assert kb["id"] == "kb-1"
    assert files[0]["id"] == "file-1"
    assert files[0]["kb_name"] == "产品文档"


def test_store_update_kb_keeps_file_kb_name_in_metadata(tmp_path) -> None:
    config = LiteRAGConfig(
        storage_root=tmp_path,
        db_dir=tmp_path / "db",
        files_dir=tmp_path / "files",
        metadata_db_path=tmp_path / "metadata.sqlite3",
        enable_reranker=False,
    )
    store = LiteRAGStore(config)
    store._get_chunks_table = lambda: (_ for _ in ()).throw(
        RuntimeError("skip lancedb")
    )

    kb = store.create_kb("旧名称")
    file_record = {
        "id": "file-1",
        "kb_id": kb["id"],
        "kb_name": kb["name"],
        "title": "demo.md",
        "source_name": "demo.md",
        "stored_path": str(config.files_dir / kb["id"] / "file-1.md"),
        "chunk_count": 1,
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
    }
    store._metadata.create_file(file_record)

    updated = store.update_kb(kb["id"], name="新名称")
    files = store.list_files(kb_ref=kb["id"])

    assert updated["name"] == "新名称"
    assert files[0]["kb_name"] == "新名称"


def test_add_file_rolls_back_copied_file_on_index_failure(tmp_path) -> None:
    config = LiteRAGConfig(
        storage_root=tmp_path,
        db_dir=tmp_path / "db",
        files_dir=tmp_path / "files",
        metadata_db_path=tmp_path / "metadata.sqlite3",
        enable_reranker=False,
    )
    store = LiteRAGStore(config)
    kb = store.create_kb("产品文档")

    source_path = tmp_path / "demo.md"
    source_path.write_text("line one\nline two\n", encoding="utf-8")

    store._delete_chunks = lambda _file_id: None

    def broken_index(_kb, _file_record, _chunks):
        raise RuntimeError("index failed")

    store._index_chunks = broken_index

    with pytest.raises(RuntimeError, match="index failed"):
        store.add_file(kb["id"], str(source_path))

    kb_dir = config.files_dir / kb["id"]
    assert list(kb_dir.iterdir()) == []
    assert store.list_files(kb_ref=kb["id"]) == []


def test_update_file_restores_previous_file_and_metadata_on_failure(tmp_path) -> None:
    config = LiteRAGConfig(
        storage_root=tmp_path,
        db_dir=tmp_path / "db",
        files_dir=tmp_path / "files",
        metadata_db_path=tmp_path / "metadata.sqlite3",
        enable_reranker=False,
    )
    store = LiteRAGStore(config)
    kb = store.create_kb("产品文档")

    stored_path = config.files_dir / kb["id"] / "file-1.md"
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    old_content = "old line one\nold line two\n"
    stored_path.write_text(old_content, encoding="utf-8")

    file_record = {
        "id": "file-1",
        "kb_id": kb["id"],
        "kb_name": kb["name"],
        "title": "demo.md",
        "source_name": "old.md",
        "stored_path": str(stored_path),
        "chunk_count": 2,
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
    }
    store._metadata.create_file(file_record)

    new_source = tmp_path / "new.md"
    new_source.write_text("new line one\nnew line two\n", encoding="utf-8")

    store._delete_chunks = lambda _file_id: None

    indexed_source_names: list[str] = []

    def fail_new_index(_kb, record, _chunks):
        indexed_source_names.append(record["source_name"])
        if record["source_name"] == "new.md":
            raise RuntimeError("new indexing failed")

    store._index_chunks = fail_new_index

    with pytest.raises(RuntimeError, match="new indexing failed"):
        store.update_file("file-1", source_path=str(new_source))

    assert stored_path.read_text(encoding="utf-8") == old_content
    persisted = store.get_file("file-1")
    assert persisted["source_name"] == "old.md"
    assert persisted["chunk_count"] == 2
    assert persisted["updated_at"] == "2024-01-01T00:00:00+00:00"
    assert indexed_source_names == ["new.md", "old.md"]

    backup_paths = list(Path(stored_path.parent).glob(f"{stored_path.name}.bak-*"))
    assert backup_paths == []


def test_get_file_content_reads_stored_text_file(tmp_path) -> None:
    config = LiteRAGConfig(
        storage_root=tmp_path,
        db_dir=tmp_path / "db",
        files_dir=tmp_path / "files",
        metadata_db_path=tmp_path / "metadata.sqlite3",
        enable_reranker=False,
    )
    store = LiteRAGStore(config)
    kb = store.create_kb("产品文档")

    stored_path = config.files_dir / kb["id"] / "file-1.md"
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    stored_path.write_text("# 标题\n\n正文内容", encoding="utf-8")

    file_record = {
        "id": "file-1",
        "kb_id": kb["id"],
        "kb_name": kb["name"],
        "title": "demo.md",
        "source_name": "demo.md",
        "stored_path": str(stored_path),
        "chunk_count": 1,
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
    }
    store._metadata.create_file(file_record)

    result = store.get_file_content("file-1")

    assert result["file"]["id"] == "file-1"
    assert result["content"] == "# 标题\n\n正文内容"


def test_metadata_store_persists_chunks_for_file(tmp_path) -> None:
    config = LiteRAGConfig(
        storage_root=tmp_path,
        db_dir=tmp_path / "db",
        files_dir=tmp_path / "files",
        metadata_db_path=tmp_path / "metadata.sqlite3",
        enable_reranker=False,
    )
    store = LiteRAGStore(config)
    kb = store.create_kb("产品文档")

    source_path = tmp_path / "demo.md"
    source_path.write_text("第一段\n\n第二段\n\n第三段", encoding="utf-8")

    store._index_chunks = lambda *_args, **_kwargs: None

    file_record = store.add_file(kb["id"], str(source_path))
    chunks = store.list_file_chunks(file_record["id"])

    assert file_record["chunk_count"] == len(chunks)
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["file_id"] == file_record["id"]
    assert chunks[0]["text"]
