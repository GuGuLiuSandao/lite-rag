from __future__ import annotations

from datetime import datetime, timezone

import pytest
from lancedb.index import FTS

from lite_rag.config import LiteRAGConfig
from lite_rag.models import build_chunk_model
from lite_rag.store import LiteRAGStore


class Embedding:
    def get_sentence_embedding_dimension(self):
        return 3

    def encode(self, value):
        return [1.0, 0.0, 0.0] if isinstance(value, str) else [[1.0, 0.0, 0.0] for _ in value]


@pytest.fixture
def store(tmp_path):
    result = LiteRAGStore(LiteRAGConfig(
        storage_root=tmp_path, db_dir=tmp_path / "db", files_dir=tmp_path / "files",
        metadata_db_path=tmp_path / "metadata.sqlite3", enable_reranker=False,
    ))
    result._embed_model = Embedding()
    return result


def assert_covered(table):
    stats = table.index_stats("text_idx")
    assert stats.num_indexed_rows == table.count_rows()
    assert stats.num_unindexed_rows == 0


@pytest.mark.parametrize("legacy_index", [None, "simple", "icu"])
def test_existing_table_is_backfilled_without_loading_embeddings(store, legacy_index):
    kb = store.create_kb("legacy")
    table = store._db.create_table("rag_chunks", schema=build_chunk_model(3).to_arrow_schema())
    if legacy_index is not None:
        table.create_index("text", config=FTS(base_tokenizer=legacy_index))
    row = {
        "id": "chunk-1", "kb_id": kb["id"], "kb_name": kb["name"],
        "file_id": "file-1", "file_name": "legacy.md", "chunk_index": 0,
        "text": "勇者住在白石城，每年冬天举行庆典。", "vector": [1.0, 0.0, 0.0],
    }
    table.add([row])
    store._get_embed_model = lambda: pytest.fail("Backfill must reuse existing vectors")
    maintained = store._get_chunks_table()
    assert_covered(maintained)
    assert maintained.to_arrow().to_pylist() == [row]
    assert maintained.list_indices()[0].index_details["base_tokenizer"] == "icu"
    assert maintained.list_indices()[0].index_details["remove_stop_words"] is False
    assert store.search("白石城", kb_ref=kb["id"], mode="fts")[0]["chunk_id"] == "chunk-1"


def test_english_stemming_and_short_technical_terms_remain_searchable(store, tmp_path):
    kb = store.create_kb("project")
    source = tmp_path / "card.md"
    source.write_text("C++ programs are running.", encoding="utf-8")
    record = store.add_file(kb["id"], str(source))
    for query in ["C++", "C", "run"]:
        hits = store.search(query, kb_ref=kb["id"], mode="fts")
        assert hits and hits[0]["file_id"] == record["id"]


def test_import_updates_index_once_per_document_without_rebuilding(store, tmp_path, monkeypatch):
    kb = store.create_kb("project")
    table = store._get_chunks_table()
    optimize = table.optimize
    calls = []

    def update_index(**kwargs):
        calls.append(kwargs)
        return optimize(**kwargs)

    monkeypatch.setattr(table, "optimize", update_index)
    monkeypatch.setattr(table, "create_index", lambda *args, **kwargs: pytest.fail("Do not rebuild per document"))
    for name in ["alpha", "beta"]:
        source = tmp_path / f"{name}.md"
        source.write_text(f"{name} common knowledge " * 100, encoding="utf-8")
        record = store.add_file(kb["id"], str(source))
        assert record["chunk_count"] > 1
        assert_covered(table)
    assert len(calls) == 2
    for call in calls:
        cutoff = datetime.now(timezone.utc) - call["cleanup_older_than"]
        assert cutoff.year == 1970
    plan = table.search("alpha", query_type="fts").explain_plan()
    assert "MatchQuery" in plan
    assert "FlatMatchQuery" not in plan


def test_index_stays_current_after_update_delete_and_kb_rename(store, tmp_path):
    kb = store.create_kb("project")
    source = tmp_path / "card.md"
    source.write_text("勇者住在白石城，每年冬天举行庆典。", encoding="utf-8")
    record = store.add_file(kb["id"], str(source))
    table = store._get_chunks_table()
    original_versions = {item["version"] for item in table.list_versions()}
    assert_covered(table)
    for mode in ["fts", "hybrid"]:
        hits = store.search("庆典", kb_ref=kb["id"], file_ids=[record["id"]], mode=mode)
        assert hits and hits[0]["file_id"] == record["id"]

    source.write_text("术士守护月光森林，寻找远古遗迹。", encoding="utf-8")
    store.update_file(record["id"], source_path=str(source))
    assert_covered(table)
    assert store.search("庆典", kb_ref=kb["id"], mode="fts") == []
    assert store.search("遗迹", kb_ref=kb["id"], mode="fts")[0]["file_id"] == record["id"]
    store.update_kb(kb["id"], name="renamed")
    assert_covered(table)
    assert store.search("遗迹", kb_ref=kb["id"], mode="fts")[0]["kb_name"] == "renamed"
    assert original_versions <= {item["version"] for item in table.list_versions()}

    store.delete_file(record["id"])
    assert_covered(table)
    assert store.search("遗迹", kb_ref=kb["id"], mode="fts") == []
    assert table.count_rows() == 0


def test_maintenance_failure_preserves_document_and_retries(store, tmp_path, monkeypatch, caplog):
    kb = store.create_kb("project")
    table = store._get_chunks_table()
    source = tmp_path / "card.md"
    source.write_text("common knowledge alpha", encoding="utf-8")
    sync_index = store._sync_fts_index

    def fail_maintenance(_table):
        raise RuntimeError("temporary index maintenance failure")

    monkeypatch.setattr(store, "_sync_fts_index", fail_maintenance)
    record = store.add_file(kb["id"], str(source))
    source.write_text("common knowledge beta", encoding="utf-8")
    store.update_file(record["id"], source_path=str(source))
    assert store.get_file_content(record["id"])["content"] == source.read_text()
    assert len(store.list_file_chunks(record["id"])) == 1
    assert store.search("beta", kb_ref=kb["id"], mode="fts")[0]["file_id"] == record["id"]
    assert "FTS index maintenance failed" in caplog.text
    assert table.index_stats("text_idx").num_unindexed_rows == 1

    monkeypatch.setattr(store, "_sync_fts_index", sync_index)
    # The next write also indexes rows left pending by the failed maintenance.
    store.update_file(record["id"], title="updated title")
    assert_covered(table)


def test_reopening_a_current_index_does_not_rebuild_or_optimize(store, tmp_path, monkeypatch):
    kb = store.create_kb("project")
    source = tmp_path / "card.md"
    source.write_text("common knowledge", encoding="utf-8")
    store.add_file(kb["id"], str(source))
    table = store._get_chunks_table()
    store._chunks_table = None
    monkeypatch.setattr(store._db, "open_table", lambda _name: table)
    monkeypatch.setattr(table, "create_index", lambda *args, **kwargs: pytest.fail("Index is current"))
    monkeypatch.setattr(table, "optimize", lambda **kwargs: pytest.fail("No unindexed rows"))
    assert_covered(store._get_chunks_table())
