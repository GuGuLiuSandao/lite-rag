from __future__ import annotations

import sqlite3
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from lite_rag.api import create_app, get_store
from lite_rag.config import LiteRAGConfig
from lite_rag.metadata import SQLiteMetadataStore
from lite_rag.store import LiteRAGStore
from lite_rag.utils import chunk_text


TEXT = "0123456789" * 5


class Embedding:
    def get_sentence_embedding_dimension(self):
        return 3

    def encode(self, value):
        return [1.0, 0.0, 0.0] if isinstance(value, str) else [[1.0, 0.0, 0.0] for _ in value]


@pytest.fixture
def store(tmp_path):
    result = LiteRAGStore(LiteRAGConfig(
        storage_root=tmp_path / "data", db_dir=tmp_path / "data/db",
        files_dir=tmp_path / "data/files", metadata_db_path=tmp_path / "data/metadata.sqlite3",
        chunk_size=20, chunk_overlap=4, enable_reranker=False,
    ))
    result._embed_model = Embedding()
    return result


@pytest.fixture
def client(store):
    app = create_app()
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as result:
        yield result


def add_document(store, tmp_path, **options):
    kb = store.create_kb("project")
    path = tmp_path / "card.md"
    path.write_text(TEXT, encoding="utf-8")
    return store.add_file(kb["id"], str(path), **options)


def texts(store, file_id):
    return [item["text"] for item in store.list_file_chunks(file_id)]


@pytest.mark.parametrize("upload", [False, True])
def test_api_import_persists_caller_chunking(client, store, tmp_path, upload):
    kb = store.create_kb("project")
    if upload:
        response = client.post("/file/upload", data={
            "kb": kb["id"], "chunk_size": "12", "chunk_overlap": "2",
        }, files={"file": ("card.md", TEXT.encode(), "text/markdown")})
    else:
        path = tmp_path / "card.md"
        path.write_text(TEXT, encoding="utf-8")
        response = client.post("/file", json={
            "kb": kb["id"], "path": str(path), "chunk_size": 12, "chunk_overlap": 2,
        })
    assert response.status_code == 200, response.text
    record = response.json()["result"]
    assert (record["chunk_size"], record["chunk_overlap"], record["chunk_count"]) == (12, 2, 5)
    assert texts(store, record["id"]) == [TEXT[0:12], TEXT[10:22], TEXT[20:32], TEXT[30:42], TEXT[40:50]]
    assert client.get(f'/file/{record["id"]}').json()["result"]["chunk_size"] == 12
    assert client.get("/file").json()["result"][0]["chunk_overlap"] == 2
    reopened = LiteRAGStore(replace(store.config, chunk_size=30, chunk_overlap=6))
    assert reopened.get_file(record["id"])["chunk_size"] == 12
    assert texts(reopened, record["id"]) == texts(store, record["id"])


def test_defaults_are_saved_and_content_updates_keep_document_settings(store, tmp_path):
    record = add_document(store, tmp_path)
    assert (record["chunk_size"], record["chunk_overlap"]) == (20, 4)
    store.config.chunk_size = 30
    store.config.chunk_overlap = 6
    replacement = tmp_path / "new.md"
    replacement.write_text(TEXT + "new", encoding="utf-8")
    updated = store.update_file(record["id"], source_path=str(replacement))
    assert (updated["chunk_size"], updated["chunk_overlap"]) == (20, 4)
    assert texts(store, record["id"]) == [
        (TEXT + "new")[0:20], (TEXT + "new")[16:36],
        (TEXT + "new")[32:52], (TEXT + "new")[48:],
    ]


def test_api_can_rechunk_stored_document_without_upload(client, store, tmp_path):
    record = add_document(store, tmp_path)
    response = client.patch(f'/file/{record["id"]}', json={"chunk_size": 10, "chunk_overlap": 0})
    assert response.status_code == 200, response.text
    updated = response.json()["result"]
    assert (updated["id"], updated["source_name"], updated["chunk_count"]) == (record["id"], "card.md", 5)
    assert texts(store, record["id"]) == ["0123456789"] * 5
    assert store.get_file_content(record["id"])["content"] == TEXT
    table = store._get_chunks_table()
    rows = table.search().where(f'file_id = \'{record["id"]}\'').to_list()
    assert len(rows) == 5
    assert {item["id"] for item in rows} == {item["id"] for item in store.list_file_chunks(record["id"])}
    assert table.index_stats("text_idx").num_unindexed_rows == 0
    # A single override inherits the document's zero overlap, not the server's 4.
    response = client.patch(f'/file/{record["id"]}', json={"chunk_size": 5})
    assert response.status_code == 200
    assert response.json()["result"]["chunk_overlap"] == 0
    assert len(texts(store, record["id"])) == 10


def test_title_only_update_does_not_rechunk(store, tmp_path, monkeypatch):
    record = add_document(store, tmp_path, chunk_size=12, chunk_overlap=2)
    before = store.list_file_chunks(record["id"])
    monkeypatch.setattr(store, "_get_embed_model", lambda: pytest.fail("Title edit must not load a model"))
    updated = store.update_file(record["id"], title="renamed")
    assert updated["title"] == "renamed"
    assert (updated["chunk_size"], updated["chunk_overlap"]) == (12, 2)
    assert store.list_file_chunks(record["id"]) == before


@pytest.mark.parametrize("options", [
    {"chunk_size": 0}, {"chunk_size": -1}, {"chunk_size": True},
    {"chunk_size": 5.5}, {"chunk_size": "12"}, {"chunk_overlap": -1},
    {"chunk_overlap": True}, {"chunk_overlap": 1.5},
    {"chunk_size": 12, "chunk_overlap": 12}, {"chunk_size": 12, "chunk_overlap": 13},
    {"chunk_size": 3},
])
def test_invalid_api_chunking_leaves_document_unchanged(client, store, tmp_path, options):
    record = add_document(store, tmp_path)
    before = store.list_file_chunks(record["id"])
    response = client.patch(f'/file/{record["id"]}', json=options)
    assert response.status_code in {400, 422}, response.text
    assert store.get_file(record["id"]) == record
    assert store.list_file_chunks(record["id"]) == before
    assert store.get_file_content(record["id"])["content"] == TEXT


@pytest.mark.parametrize("options", [
    {"chunk_size": "0"}, {"chunk_size": "bad"}, {"chunk_overlap": "-1"},
    {"chunk_size": "10", "chunk_overlap": "10"},
])
def test_invalid_upload_chunking_does_not_store_document(client, store, options):
    kb = store.create_kb("project")
    response = client.post("/file/upload", data={"kb": kb["id"], **options}, files={
        "file": ("card.md", TEXT.encode(), "text/markdown"),
    })
    assert response.status_code in {400, 422}, response.text
    assert store.list_files() == []
    assert not list(store.config.files_dir.rglob("*.md"))


@pytest.mark.parametrize("failure", ["index", "metadata"])
@pytest.mark.parametrize("replace_content", [False, True])
def test_rechunk_failure_restores_original_boundaries_and_settings(store, tmp_path, monkeypatch, failure, replace_content):
    record = add_document(store, tmp_path, chunk_size=12, chunk_overlap=2)
    previous_chunks = store.list_file_chunks(record["id"])
    previous_rows = store._get_chunks_table().to_arrow().to_pylist()
    store.config.chunk_size = 30
    store.config.chunk_overlap = 6
    if failure == "index":
        original = store._index_chunks
        calls = []

        def fail_once(kb, file_record, chunks):
            original(kb, file_record, chunks)
            calls.append(file_record["chunk_size"])
            if len(calls) == 1:
                raise RuntimeError("failed after indexing")

        monkeypatch.setattr(store, "_index_chunks", fail_once)
    else:
        def fail_metadata(_record):
            raise RuntimeError("failed before metadata commit")

        monkeypatch.setattr(store._metadata, "update_file", fail_metadata)
    replacement = tmp_path / "new.md"
    replacement.write_text("new content " * 10, encoding="utf-8")
    with pytest.raises(RuntimeError, match="failed"):
        store.update_file(
            record["id"], source_path=str(replacement) if replace_content else None,
            title="new title", chunk_size=10, chunk_overlap=0,
        )
    assert store.get_file(record["id"]) == record
    assert store.get_file_content(record["id"])["content"] == TEXT
    assert texts(store, record["id"]) == [item["text"] for item in previous_chunks]
    assert {item["id"] for item in store.list_file_chunks(record["id"])} == {item["id"] for item in previous_chunks}
    assert sorted(store._get_chunks_table().to_arrow().to_pylist(), key=lambda x: x["id"]) == sorted(previous_rows, key=lambda x: x["id"])
    assert not list(store.config.files_dir.rglob("*.bak-*"))


def test_existing_sqlite_schema_is_migrated_without_guessing_old_chunk_settings(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE files (
            id TEXT PRIMARY KEY, kb_id TEXT NOT NULL, kb_name TEXT NOT NULL,
            title TEXT NOT NULL, source_name TEXT NOT NULL, stored_path TEXT NOT NULL,
            chunk_count INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        connection.execute("INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (
            "file-1", "kb-1", "legacy", "card", "card.md", "/old/card.md", 7, "before", "before",
        ))
    metadata = SQLiteMetadataStore(path)
    original = metadata.get_file("file-1")
    assert original["chunk_count"] == 7
    assert original["chunk_size"] is None and original["chunk_overlap"] is None
    assert SQLiteMetadataStore(path).get_file("file-1") == original


@pytest.mark.parametrize("size, overlap", [(0, 0), (-1, 0), (10, -1), (10, 10), (10, 11), (True, 0)])
def test_chunking_rejects_values_that_cannot_make_progress(tmp_path, size, overlap):
    with pytest.raises(ValueError):
        chunk_text("long text", size, overlap)
    with pytest.raises(ValueError):
        LiteRAGConfig(
            storage_root=tmp_path, db_dir=tmp_path / "db", files_dir=tmp_path / "files",
            metadata_db_path=tmp_path / "metadata.sqlite3", chunk_size=size, chunk_overlap=overlap,
        )


def test_legacy_document_uses_defaults_only_when_reindexed(client, store, tmp_path):
    record = add_document(store, tmp_path)
    record["chunk_size"] = None
    record["chunk_overlap"] = None
    store._metadata.update_file(record)
    original_chunks = store.list_file_chunks(record["id"])
    store.config.chunk_size = 10
    store.config.chunk_overlap = 0
    response = client.patch(f'/file/{record["id"]}', json={
        "title": "legacy title", "chunk_size": None, "chunk_overlap": None,
    })
    assert response.status_code == 200
    assert response.json()["result"]["chunk_size"] is None
    assert store.list_file_chunks(record["id"]) == original_chunks
    path = tmp_path / "card.md"
    response = client.patch(f'/file/{record["id"]}', json={"path": str(path)})
    assert response.status_code == 200
    assert response.json()["result"]["chunk_size"] == 10
    assert response.json()["result"]["chunk_overlap"] == 0
    assert texts(store, record["id"]) == ["0123456789"] * 5


def test_cli_import_and_rechunk_pass_document_settings(store, tmp_path, monkeypatch):
    from lite_rag import cli

    monkeypatch.setattr(cli, "LiteRAGStore", lambda _config: store)
    kb = store.create_kb("project")
    path = tmp_path / "card.md"
    path.write_text(TEXT, encoding="utf-8")
    record = cli.run(cli.build_parser().parse_args([
        "file", "add", "--kb", kb["id"], "--path", str(path),
        "--chunk-size", "12", "--chunk-overlap", "2",
    ]))
    assert (record["chunk_size"], record["chunk_overlap"], record["chunk_count"]) == (12, 2, 5)
    updated = cli.run(cli.build_parser().parse_args([
        "file", "update", "--file-id", record["id"], "--chunk-size", "10", "--chunk-overlap", "0",
    ]))
    assert updated["chunk_count"] == 5
    assert texts(store, record["id"]) == ["0123456789"] * 5


def test_persistent_model_outage_restores_all_old_vectors_without_reembedding(store, tmp_path, monkeypatch):
    # More than ten chunks verifies the rollback snapshot has no implicit query limit.
    record = add_document(store, tmp_path, chunk_size=3, chunk_overlap=0)
    assert record["chunk_count"] > 10
    foreign_kb = store.create_kb("other-project")
    store.add_file(foreign_kb["id"], str(tmp_path / "card.md"))
    before_chunks = store.list_file_chunks(record["id"])
    table = store._get_chunks_table()
    before_rows = sorted(table.to_arrow().to_pylist(), key=lambda item: item["id"])
    calls = []

    def unavailable_model(texts):
        calls.append(texts)
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(store._embed_model, "encode", unavailable_model)
    with pytest.raises(RuntimeError, match="model unavailable"):
        store.update_file(record["id"], chunk_size=10, chunk_overlap=0)
    assert len(calls) == 1
    assert store.get_file(record["id"]) == record
    assert store.list_file_chunks(record["id"]) == before_chunks
    assert sorted(table.to_arrow().to_pylist(), key=lambda item: item["id"]) == before_rows
    assert table.index_stats("text_idx").num_unindexed_rows == 0


def test_rollback_storage_failure_is_reported_and_keeps_text_backup(store, tmp_path, monkeypatch, caplog):
    record = add_document(store, tmp_path)
    replacement = tmp_path / "replacement.md"
    replacement.write_text("replacement text", encoding="utf-8")

    def fail_index(*_args):
        raise RuntimeError("model unavailable")

    def fail_restore(*_args, **_kwargs):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(store, "_index_chunks", fail_index)
    monkeypatch.setattr(store._get_chunks_table(), "add", fail_restore)
    with pytest.raises(RuntimeError, match="update and rollback failed"):
        store.update_file(record["id"], source_path=str(replacement), chunk_size=10, chunk_overlap=0)
    backups = list(store.config.files_dir.rglob("*.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == TEXT
    assert str(backups[0]) in caplog.text
    assert store.get_file(record["id"]) == record
