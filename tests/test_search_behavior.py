from __future__ import annotations

from pathlib import Path

from lite_rag.config import LiteRAGConfig
from lite_rag.store import LiteRAGStore


class StubEmbedModel:
    def encode(self, value):
        if isinstance(value, str):
            return [0.1, 0.2, 0.3]
        return [[0.1, 0.2, 0.3] for _ in value]

    def get_sentence_embedding_dimension(self) -> int:
        return 3


class StubQuery:
    def __init__(self) -> None:
        self.where_value: str | None = None
        self.limit_value: int | None = None

    def vector(self, value):
        self.vector_value = value
        return self

    def text(self, value):
        self.text_value = value
        return self

    def where(self, value: str):
        self.where_value = value
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    def to_list(self):
        return [
            {
                "id": "chunk-1",
                "kb_id": "kb-1",
                "kb_name": "产品文档",
                "file_id": "file-1",
                "file_name": "demo.md",
                "chunk_index": 0,
                "text": "hard takeoff",
                "_score": 0.8,
            }
        ]


class StubTable:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple, dict]] = []
        self.query = StubQuery()

    def search(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.query


def build_store(tmp_path: Path, enable_reranker: bool = False) -> LiteRAGStore:
    config = LiteRAGConfig(
        storage_root=tmp_path,
        db_dir=tmp_path / "db",
        files_dir=tmp_path / "files",
        metadata_db_path=tmp_path / "metadata.sqlite3",
        enable_reranker=enable_reranker,
    )
    store = LiteRAGStore(config)
    kb = store.create_kb("产品文档")
    return store


def test_hybrid_search_uses_explicit_vector_and_text_builder(tmp_path) -> None:
    store = build_store(tmp_path)
    table = StubTable()
    store._get_chunks_table = lambda: table
    store._get_embed_model = lambda: StubEmbedModel()

    results = store.search(
        query="hard takeoff",
        kb_ref="产品文档",
        mode="hybrid",
        recall_top_k=5,
        final_top_k=2,
    )

    assert table.calls == [((), {"query_type": "hybrid"})]
    assert table.query.text_value == "hard takeoff"
    assert table.query.vector_value == [0.1, 0.2, 0.3]
    assert "kb_id = '" in table.query.where_value
    assert table.query.limit_value == 5
    assert results[0]["score"] == 0.8


def test_reranker_failure_falls_back_to_base_scores(tmp_path) -> None:
    store = build_store(tmp_path, enable_reranker=True)
    table = StubTable()
    store._get_chunks_table = lambda: table
    store._get_embed_model = lambda: StubEmbedModel()

    class BrokenReranker:
        def compute_score(self, pairs):
            raise RuntimeError("reranker unavailable")

    store._reranker = BrokenReranker()

    results = store.search(
        query="hard takeoff",
        kb_ref="产品文档",
        mode="vector",
        recall_top_k=5,
        final_top_k=2,
    )

    assert results[0]["score"] == 0.8
    assert store._reranker_unavailable is True


def test_reranker_scores_override_base_scores_when_available(tmp_path) -> None:
    store = build_store(tmp_path, enable_reranker=True)
    table = StubTable()
    store._get_chunks_table = lambda: table
    store._get_embed_model = lambda: StubEmbedModel()

    class WorkingReranker:
        def compute_score(self, pairs):
            return [1.23 for _ in pairs]

    store._reranker = WorkingReranker()

    results = store.search(
        query="hard takeoff",
        kb_ref="产品文档",
        mode="vector",
        recall_top_k=5,
        final_top_k=2,
    )

    assert results[0]["score"] == 1.23


def test_search_can_disable_reranker_per_request(tmp_path) -> None:
    store = build_store(tmp_path, enable_reranker=True)
    table = StubTable()
    store._get_chunks_table = lambda: table
    store._get_embed_model = lambda: StubEmbedModel()

    class WorkingReranker:
        def compute_score(self, pairs):
            return [1.23 for _ in pairs]

    store._reranker = WorkingReranker()

    results = store.search(
        query="hard takeoff",
        kb_ref="产品文档",
        mode="vector",
        enable_reranker=False,
        recall_top_k=5,
        final_top_k=2,
    )

    assert results[0]["score"] == 0.8
