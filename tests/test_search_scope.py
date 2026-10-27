from __future__ import annotations

import pytest

from lite_rag.config import LiteRAGConfig
from lite_rag.store import LiteRAGStore


class Embedding:
    def get_sentence_embedding_dimension(self):
        return 3

    def encode(self, value):
        def vector(text):
            if "allowed-b" in text:
                return [0.8, 0.2, 0.0]
            if "allowed" in text:
                return [0.9, 0.1, 0.0]
            return [1.0, 0.0, 0.0]

        return vector(value) if isinstance(value, str) else [vector(text) for text in value]


@pytest.fixture
def indexed(tmp_path):
    store = LiteRAGStore(LiteRAGConfig(
        storage_root=tmp_path, db_dir=tmp_path / "db", files_dir=tmp_path / "files",
        metadata_db_path=tmp_path / "metadata.sqlite3", enable_reranker=False,
    ))
    store._embed_model = Embedding()
    project = store.create_kb("project")
    other = store.create_kb("other-project")
    files = {}
    for name, kb in [("secret", project), ("allowed-a", project), ("allowed-b", project), ("foreign", other)]:
        source = tmp_path / f"{name}.md"
        source.write_text(f"common knowledge {name}", encoding="utf-8")
        files[name] = store.add_file(kb["id"], str(source))["id"]
    return store, project["id"], files


@pytest.mark.parametrize("mode", ["vector", "fts", "hybrid"])
def test_document_scope_is_applied_before_top_k(indexed, mode):
    store, kb, files = indexed
    allowed = [files["allowed-a"], files["allowed-b"]]
    hits = store.search("common", kb_ref=kb, file_ids=allowed, mode=mode, recall_top_k=1, final_top_k=1)
    assert len(hits) == 1
    assert hits[0]["file_id"] in allowed
    assert hits[0]["kb_id"] == kb


@pytest.mark.parametrize("mode", ["vector", "fts", "hybrid"])
def test_kb_and_document_scope_are_intersected(indexed, mode):
    store, kb, files = indexed
    assert store.search("common", kb_ref=kb, file_ids=[files["foreign"]], mode=mode) == []
    assert store.search("common", kb_ref=kb, file_ids=["missing"], mode=mode) == []


def test_empty_scope_does_not_load_models_or_indexes(tmp_path):
    store = LiteRAGStore(LiteRAGConfig(
        storage_root=tmp_path, db_dir=tmp_path / "db", files_dir=tmp_path / "files",
        metadata_db_path=tmp_path / "metadata.sqlite3",
    ))
    store._get_chunks_table = lambda: pytest.fail("Empty scope must not open an index")
    assert store.search("question", file_ids=[]) == []


def test_omitted_scope_preserves_existing_behavior(indexed):
    store, kb, files = indexed
    hits = store.search("common", kb_ref=kb, mode="vector", recall_top_k=1, final_top_k=1)
    assert hits[0]["file_id"] == files["secret"]


def test_scope_values_are_escaped(indexed):
    store, kb, _ = indexed
    assert store.search("common", kb_ref=kb, file_ids=["x') OR true --"], mode="fts") == []


@pytest.mark.parametrize("mode", ["vector", "fts", "hybrid"])
def test_visible_documents_are_reranked_in_one_pool(indexed, mode):
    store, kb, files = indexed
    calls = []

    class Reranker:
        def compute_score(self, pairs):
            calls.append(pairs)
            assert len(pairs) == 2
            assert all("allowed" in text for _, text in pairs)
            return [0.99 if "allowed-b" in text else 0.1 for _, text in pairs]

    store._reranker = Reranker()
    hits = store.search(
        "common", kb_ref=kb, file_ids=[files["allowed-a"], files["allowed-b"]],
        mode=mode, recall_top_k=10, final_top_k=1, enable_reranker=True,
    )
    assert len(calls) == 1
    assert len(hits) == 1 and hits[0]["file_id"] == files["allowed-b"]
