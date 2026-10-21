from __future__ import annotations

from dataclasses import replace

import httpx
import pytest

from lite_rag.config import LiteRAGConfig
from lite_rag.providers import HTTPEmbedding, HTTPReranker
from lite_rag.store import LiteRAGStore


@pytest.fixture
def config(tmp_path):
    return LiteRAGConfig(
        storage_root=tmp_path,
        db_dir=tmp_path / "db",
        files_dir=tmp_path / "files",
        metadata_db_path=tmp_path / "metadata.sqlite3",
        embedding_provider="http",
        embedding_api_url="https://models.example/v1/embeddings",
        embedding_model_name="embedding-test",
        embedding_api_key="test-secret",
        embedding_batch_size=2,
        reranker_provider="http",
        reranker_api_url="https://models.example/v1/rerank",
        reranker_model_name="reranker-test",
    )


def install_api(monkeypatch, handler):
    def post(url, **kwargs):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            return client.post(url, **kwargs)

    monkeypatch.setattr("lite_rag.providers.httpx.post", post)


def embedding_response(request):
    import json

    payload = json.loads(request.content)
    return httpx.Response(200, json={"data": [
        {"index": index, "embedding": [float(len(text)), 1.0, 0.5]}
        for index, text in reversed(list(enumerate(payload["input"])))
    ]})


def test_embedding_batches_and_restores_input_order(config, monkeypatch):
    import json

    calls = []

    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-secret"
        payload = json.loads(request.content)
        assert payload["model"] == "embedding-test"
        calls.append(payload["input"])
        return embedding_response(request)

    install_api(monkeypatch, handler)
    model = HTTPEmbedding(config)
    assert model.encode(["a", "bb", "ccc"]) == [
        [1.0, 1.0, 0.5], [2.0, 1.0, 0.5], [3.0, 1.0, 0.5]
    ]
    assert calls == [["a", "bb"], ["ccc"]]
    assert model.get_sentence_embedding_dimension() == 3
    assert model.encode("a") == [1.0, 1.0, 0.5]


@pytest.mark.parametrize("data", [
    [],
    [{"index": 0, "embedding": [1.0]}, {"index": 0, "embedding": [1.0]}],
    [{"index": 0, "embedding": []}, {"index": 1, "embedding": [1.0]}],
    [{"index": 0, "embedding": [1.0]}, {"index": 1, "embedding": [1.0, 2.0]}],
    [{"index": 0, "embedding": [True]}, {"index": 1, "embedding": [1.0]}],
])
def test_embedding_rejects_invalid_responses(config, monkeypatch, data):
    install_api(monkeypatch, lambda _: httpx.Response(200, json={"data": data}))
    with pytest.raises(ValueError):
        HTTPEmbedding(config).encode(["a", "b"])


def test_reranker_restores_document_order(config, monkeypatch):
    import json

    def handler(request):
        assert json.loads(request.content) == {
            "model": "reranker-test", "query": "question",
            "documents": ["first", "second"], "top_n": 2,
        }
        return httpx.Response(200, json={"results": [
            {"index": 1, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.1},
        ]})

    install_api(monkeypatch, handler)
    assert HTTPReranker(config).compute_score([
        ["question", "first"], ["question", "second"]
    ]) == [0.1, 0.9]


def test_http_errors_do_not_expose_credentials_or_response_body(config, monkeypatch):
    secret_url = config.embedding_api_url + "?key=test-secret"
    config = replace(config, embedding_api_url=secret_url)
    install_api(monkeypatch, lambda _: httpx.Response(401, text="test-secret"))
    with pytest.raises(RuntimeError, match="HTTP 401") as error:
        HTTPEmbedding(config).encode("hello")
    assert "test-secret" not in str(error.value)
    assert "test-secret" not in repr(config)


def test_timeout_has_sanitized_error(config, monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("test-secret", request=request)

    install_api(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="Model API request failed") as error:
        HTTPEmbedding(config).encode("hello")
    assert "test-secret" not in str(error.value)


def test_http_store_indexes_and_searches_without_local_models(config, monkeypatch, tmp_path):
    install_api(monkeypatch, embedding_response)
    config = replace(config, enable_reranker=False)
    store = LiteRAGStore(config)
    kb = store.create_kb("test")
    source = tmp_path / "source.md"
    source.write_text("hello knowledge", encoding="utf-8")
    record = store.add_file(kb["id"], str(source))
    results = store.search("hello", mode="vector")
    assert results[0]["file_id"] == record["id"]
    assert results[0]["text"] == "hello knowledge"

    # A same-dimension model change must not silently search or mutate old data.
    changed = LiteRAGStore(replace(config, embedding_model_name="another-model"))
    with pytest.raises(ValueError, match="does not match"):
        changed.search("hello", mode="vector")
    source.write_text("replacement", encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        changed.update_file(record["id"], source_path=str(source))
    assert changed.get_file_content(record["id"])["content"] == "hello knowledge"
    assert len(changed.list_file_chunks(record["id"])) == 1

    # Full-text retrieval needs neither the old model nor a working embedding API.
    install_api(monkeypatch, lambda _: pytest.fail("FTS must not call embeddings"))
    assert changed.search("hello", mode="fts")[0]["file_id"] == record["id"]
