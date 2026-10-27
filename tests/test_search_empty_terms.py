from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from lite_rag.api import create_app, get_store
from lite_rag.config import LiteRAGConfig
from lite_rag.store import LiteRAGStore


class Embedding:
    def get_sentence_embedding_dimension(self):
        return 3

    def encode(self, value):
        if isinstance(value, str):
            return [1.0, 0.0, 0.0]
        return [[1.0, 0.0, 0.0] for _ in value]


@pytest.fixture
def indexed(tmp_path):
    store = LiteRAGStore(LiteRAGConfig(
        storage_root=tmp_path, db_dir=tmp_path / "db", files_dir=tmp_path / "files",
        metadata_db_path=tmp_path / "metadata.sqlite3", enable_reranker=False,
    ))
    store._embed_model = Embedding()
    kb = store.create_kb("project")
    foreign_kb = store.create_kb("foreign")
    source = tmp_path / "sample.md"
    source.write_text("common knowledge C++ 中文", encoding="utf-8")
    store.add_file(kb["id"], str(source))
    allowed = store.add_file(kb["id"], str(source))
    foreign = store.add_file(foreign_kb["id"], str(source))
    return store, kb["id"], allowed["id"], foreign["id"]


@pytest.mark.parametrize("query", ["？", "+", "?", "!!!", "", " \n\t", "🙂"])
def test_symbol_only_fts_queries_return_empty_without_loading_models(indexed, query):
    store, kb, allowed, _ = indexed
    store._get_chunks_table = lambda: pytest.fail("No index needed for an empty query")
    store._get_embed_model = lambda: pytest.fail("No embeddings needed for an empty query")
    store._get_reranker = lambda **kwargs: pytest.fail("No reranking needed for an empty query")
    assert store.search(query, kb_ref=kb, file_ids=[allowed], mode="fts") == []


@pytest.mark.parametrize("query", [
    "？", "+", "", " \n\t", "🙂", "the", "and", "the and", "x" * 41, "汉" * 25,
])
@pytest.mark.parametrize("mode", [None, "fts", "hybrid"])
def test_empty_fts_tokens_do_not_break_retrieval(indexed, query, mode):
    store, kb, allowed, foreign = indexed
    hits = store.search(
        query, kb_ref=kb, file_ids=[allowed, foreign], mode=mode,
        recall_top_k=1, final_top_k=1,
    )
    if mode == "fts":
        assert hits == []
    else:
        assert len(hits) == 1
        assert hits[0]["file_id"] == allowed
        assert hits[0]["kb_id"] == kb
        assert math.isfinite(hits[0]["retrieval_score"])
    assert store.search(query, kb_ref=kb, file_ids=[foreign], mode=mode) == []


@pytest.mark.parametrize("query", ["？", "the"])
def test_hybrid_empty_terms_still_reranks_visible_documents(indexed, query):
    store, kb, allowed, _ = indexed
    calls = []

    class Reranker:
        def compute_score(self, pairs):
            calls.append(pairs)
            return [0.9 for _ in pairs]

    store._reranker = Reranker()
    hits = store.search(
        query, kb_ref=kb, file_ids=[allowed], mode="hybrid", enable_reranker=True,
    )
    assert calls == [[[query, "common knowledge C++ 中文"]]]
    assert len(hits) == 1
    assert hits[0]["file_id"] == allowed
    assert hits[0]["rerank_score"] == 0.9
    if query == "？":
        assert hits[0]["retrieval_score"] == pytest.approx(0.0)
    else:
        native = (
            store._get_chunks_table().search(query_type="hybrid")
            .vector([1.0, 0.0, 0.0]).text(query)
            .where(f"file_id = '{allowed}'", prefilter=True).limit(1).to_list()
        )
        assert hits[0]["retrieval_score"] == native[0]["_relevance_score"]


@pytest.mark.parametrize("query", ["？", "+", "the and", "x" * 41])
def test_native_lancedb_handles_empty_fts_terms(indexed, query):
    store, _, allowed, _ = indexed
    table = store._get_chunks_table()
    scope = f"file_id = '{allowed}'"
    # Exercise LanceDB directly so an application workaround cannot hide a regression.
    assert table.search(query, query_type="fts").where(scope, prefilter=True).to_list() == []
    hits = (
        table.search(query_type="hybrid").vector([1.0, 0.0, 0.0]).text(query)
        .where(scope, prefilter=True).limit(1).to_list()
    )
    assert len(hits) == 1
    assert hits[0]["file_id"] == allowed
    assert math.isfinite(hits[0]["_relevance_score"])


@pytest.mark.parametrize("mode", ["fts", "hybrid"])
@pytest.mark.parametrize("query", ["common？", "+ common", "C++", "中文"])
def test_punctuation_with_searchable_text_still_matches(indexed, mode, query):
    store, kb, allowed, _ = indexed
    hits = store.search(query, kb_ref=kb, file_ids=[allowed], mode=mode)
    assert len(hits) == 1
    assert hits[0]["file_id"] == allowed


@pytest.mark.parametrize("mode", ["fts", "hybrid", "vector"])
@pytest.mark.parametrize("query", ["？", "+", "", "the"])
def test_api_handles_empty_terms_with_real_lancedb(indexed, mode, query):
    store, kb, allowed, _ = indexed
    app = create_app()
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as client:
        response = client.post("/search", json={
            "query": query, "kb": kb, "file_ids": [allowed], "mode": mode,
        })
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    if mode == "fts":
        assert response.json()["result"] == []
    else:
        hits = response.json()["result"]
        assert len(hits) == 1
        assert hits[0]["file_id"] == allowed


@pytest.mark.parametrize("mode, query, error", [
    ("fts", "common", "index is unavailable"),
    ("hybrid", "common", "index is unavailable"),
    ("vector", "common", "index is unavailable"),
    ("vector", "common", "lance error: LanceError(Arrow): Invalid argument error: "
     "all columns in a record batch must have the same length"),
    ("hybrid", "+", "lance error: LanceError(Arrow): Invalid argument error: "
     "all columns in a record batch must have the same length"),
])
def test_unrelated_retrieval_errors_are_not_swallowed(indexed, mode, query, error):
    store, kb, _, _ = indexed
    table = store._get_chunks_table()

    class BrokenQuery:
        def where(self, *args, **kwargs):
            return self

        def limit(self, *args):
            return self

        def vector(self, *args):
            return self

        def text(self, *args):
            return self

        def to_list(self):
            raise RuntimeError(error)

    table.search = lambda *args, **kwargs: BrokenQuery()
    with pytest.raises(RuntimeError) as exc:
        store.search(query, kb_ref=kb, mode=mode)
    assert str(exc.value) == error
