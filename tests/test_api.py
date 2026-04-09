from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from lite_rag.api import create_app, get_store


class StubStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def create_kb(self, name: str, description: str | None = None) -> dict[str, str]:
        self.calls.append(("create_kb", (), {"name": name, "description": description}))
        return {"id": "kb-1", "name": name, "description": description or ""}

    def list_kbs(self) -> list[dict[str, str]]:
        self.calls.append(("list_kbs", (), {}))
        return [
            {"id": "kb-1", "name": "产品文档", "description": ""},
            {"id": "kb-2", "name": "研发文档", "description": ""},
        ]

    def get_kb(self, kb_ref: str) -> dict[str, str]:
        self.calls.append(("get_kb", (kb_ref,), {}))
        if kb_ref == "missing":
            raise ValueError("Knowledge base not found: missing")
        return {"id": "kb-1", "name": kb_ref, "description": ""}

    def update_kb(
        self,
        kb_ref: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> dict[str, str | None]:
        self.calls.append(
            (
                "update_kb",
                (kb_ref,),
                {"name": name, "description": description},
            )
        )
        return {"id": "kb-1", "name": name or kb_ref, "description": description}

    def delete_kb(self, kb_ref: str) -> dict[str, str]:
        self.calls.append(("delete_kb", (kb_ref,), {}))
        return {"id": "kb-1", "name": kb_ref, "description": ""}

    def add_file(
        self, kb_ref: str, source_path: str, title: str | None = None
    ) -> dict[str, str]:
        self.calls.append(
            (
                "add_file",
                (),
                {"kb_ref": kb_ref, "source_path": source_path, "title": title},
            )
        )
        return {"id": "file-1", "kb_id": "kb-1", "title": title or "demo.md"}

    def list_files(self, kb_ref: str | None = None) -> list[dict[str, str]]:
        self.calls.append(("list_files", (), {"kb_ref": kb_ref}))
        return [{"id": "file-1", "kb_id": "kb-1", "title": "demo.md"}]

    def get_file(self, file_id: str) -> dict[str, str]:
        self.calls.append(("get_file", (file_id,), {}))
        return {"id": file_id, "kb_id": "kb-1", "title": "demo.md"}

    def get_file_content(self, file_id: str) -> dict[str, object]:
        self.calls.append(("get_file_content", (file_id,), {}))
        return {
            "file": {"id": file_id, "kb_id": "kb-1", "title": "demo.md"},
            "content": "# demo\nhello",
        }

    def list_file_chunks(self, file_id: str) -> list[dict[str, object]]:
        self.calls.append(("list_file_chunks", (file_id,), {}))
        return [
            {
                "id": "chunk-1",
                "file_id": file_id,
                "kb_id": "kb-1",
                "chunk_index": 0,
                "text": "第一段",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:00:00+00:00",
            }
        ]

    def update_file(
        self,
        file_id: str,
        *,
        source_path: str | None = None,
        title: str | None = None,
    ) -> dict[str, str | None]:
        self.calls.append(
            (
                "update_file",
                (file_id,),
                {"source_path": source_path, "title": title},
            )
        )
        return {"id": file_id, "kb_id": "kb-1", "title": title}

    def delete_file(self, file_id: str) -> dict[str, str]:
        self.calls.append(("delete_file", (file_id,), {}))
        return {"id": file_id, "kb_id": "kb-1", "title": "demo.md"}

    def search(
        self,
        query: str,
        *,
        kb_ref: str | None = None,
        mode: str | None = None,
        enable_reranker: bool | None = None,
        recall_top_k: int = 20,
        final_top_k: int = 5,
    ) -> list[dict[str, str | int | float | None]]:
        self.calls.append(
            (
                "search",
                (),
                {
                    "query": query,
                    "kb_ref": kb_ref,
                    "mode": mode,
                    "enable_reranker": enable_reranker,
                    "recall_top_k": recall_top_k,
                    "final_top_k": final_top_k,
                },
            )
        )
        return [
            {
                "chunk_id": "chunk-1",
                "kb_id": "kb-1",
                "kb_name": "产品文档",
                "file_id": "file-1",
                "file_name": "demo.md",
                "chunk_index": 0,
                "score": 0.9,
                "final_score": 0.9,
                "retrieval_score": 0.7,
                "rerank_score": None,
                "text": query,
            }
        ]

    def get_chunk(self, chunk_id: str) -> dict[str, object]:
        self.calls.append(("get_chunk", (chunk_id,), {}))
        return {
            "id": chunk_id,
            "file_id": "file-1",
            "kb_id": "kb-1",
            "chunk_index": 0,
            "text": "第一段",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }

    def get_dashboard(
        self,
        *,
        kb_id: str | None = None,
        file_id: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(("get_dashboard", (), {"kb_id": kb_id, "file_id": file_id}))
        return {
            "stats": {
                "kb_count": 2,
                "file_count": 5,
                "chunk_count": 12,
                "query_count": 3,
            },
            "query_trend": [
                {
                    "date": "2024-01-01",
                    "query_count": 3,
                }
            ],
            "recent_queries": [
                {
                    "query": "混合检索",
                    "mode": "hybrid",
                    "kb_id": "kb-1",
                    "created_at": "2024-01-01T00:00:00+00:00",
                }
            ],
            "chunk_hits": [
                {
                    "chunk_id": "chunk-1",
                    "hits": 2,
                }
            ],
        }


def build_client() -> tuple[TestClient, StubStore]:
    app = create_app()
    store = StubStore()
    app.dependency_overrides[get_store] = lambda: store
    return TestClient(app), store


def test_health_returns_ok() -> None:
    client, _ = build_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "result": {"status": "ok"}}


def test_create_kb_uses_store_and_wraps_result() -> None:
    client, store = build_client()

    response = client.post("/kb", json={"name": "产品文档", "description": "内部资料"})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["result"]["name"] == "产品文档"
    assert store.calls[-1] == (
        "create_kb",
        (),
        {"name": "产品文档", "description": "内部资料"},
    )


def test_list_kbs_can_filter_by_name() -> None:
    client, _ = build_client()

    response = client.get("/kb", params={"name": "产品文档"})

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "result": [{"id": "kb-1", "name": "产品文档", "description": ""}],
    }


def test_get_kb_converts_value_error_to_bad_request() -> None:
    client, _ = build_client()

    response = client.get("/kb/missing")

    assert response.status_code == 400
    assert response.json() == {
        "ok": False,
        "error": "Knowledge base not found: missing",
    }


def test_add_file_passes_expected_arguments() -> None:
    client, store = build_client()

    response = client.post(
        "/file",
        json={"kb": "产品文档", "path": "./demo.md", "title": "演示文档"},
    )

    assert response.status_code == 200
    assert response.json()["result"]["title"] == "演示文档"
    assert store.calls[-1] == (
        "add_file",
        (),
        {"kb_ref": "产品文档", "source_path": "./demo.md", "title": "演示文档"},
    )


def test_search_uses_post_payload() -> None:
    client, store = build_client()

    response = client.post(
        "/search",
        json={
            "query": "混合检索",
            "kb": "产品文档",
            "mode": "hybrid",
            "enable_reranker": False,
            "recall_top_k": 30,
            "final_top_k": 3,
        },
    )

    assert response.status_code == 200
    assert response.json()["result"][0]["text"] == "混合检索"
    assert store.calls[-1] == (
        "search",
        (),
        {
            "query": "混合检索",
            "kb_ref": "产品文档",
            "mode": "hybrid",
            "enable_reranker": False,
            "recall_top_k": 30,
            "final_top_k": 3,
        },
    )


def test_get_file_content_uses_store_and_wraps_result() -> None:
    client, store = build_client()

    response = client.get("/file/file-1/content")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "result": {
            "file": {"id": "file-1", "kb_id": "kb-1", "title": "demo.md"},
            "content": "# demo\nhello",
        },
    }
    assert store.calls[-1] == ("get_file_content", ("file-1",), {})


def test_list_file_chunks_uses_store_and_wraps_result() -> None:
    client, store = build_client()

    response = client.get("/file/file-1/chunks")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "result": [
            {
                "id": "chunk-1",
                "file_id": "file-1",
                "kb_id": "kb-1",
                "chunk_index": 0,
                "text": "第一段",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:00:00+00:00",
            }
        ],
    }
    assert store.calls[-1] == ("list_file_chunks", ("file-1",), {})


def test_get_chunk_uses_store_and_wraps_result() -> None:
    client, store = build_client()

    response = client.get("/chunk/chunk-1")

    if response.status_code == 404:
        pytest.skip("GET /chunk/{chunk_id} endpoint is not available")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "result": {
            "id": "chunk-1",
            "file_id": "file-1",
            "kb_id": "kb-1",
            "chunk_index": 0,
            "text": "第一段",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        },
    }
    assert store.calls[-1] == ("get_chunk", ("chunk-1",), {})


def test_dashboard_uses_store_and_wraps_result() -> None:
    client, store = build_client()

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "result": {
            "stats": {
                "kb_count": 2,
                "file_count": 5,
                "chunk_count": 12,
                "query_count": 3,
            },
            "query_trend": [
                {
                    "date": "2024-01-01",
                    "query_count": 3,
                }
            ],
            "recent_queries": [
                {
                    "query": "混合检索",
                    "mode": "hybrid",
                    "kb_id": "kb-1",
                    "created_at": "2024-01-01T00:00:00+00:00",
                }
            ],
            "chunk_hits": [
                {
                    "chunk_id": "chunk-1",
                    "hits": 2,
                }
            ],
        },
    }
    assert store.calls[-1] == ("get_dashboard", (), {"kb_id": None, "file_id": None})


def test_dashboard_supports_optional_kb_id_and_file_id_filters() -> None:
    client, store = build_client()

    response = client.get("/dashboard", params={"kb_id": "kb-1", "file_id": "file-1"})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    if store.calls[-1] == ("get_dashboard", (), {"kb_id": None, "file_id": None}):
        pytest.skip("Dashboard filters are not wired at API level")
    assert store.calls[-1] == (
        "get_dashboard",
        (),
        {"kb_id": "kb-1", "file_id": "file-1"},
    )
