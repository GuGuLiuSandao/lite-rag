from __future__ import annotations

import math
from typing import Any

import httpx

from .config import LiteRAGConfig


class ModelAPI:
    def __init__(self, url: str | None, api_key: str | None, timeout: float) -> None:
        if not url:
            raise ValueError("Model API URL is required")
        self.url = url
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.timeout = timeout

    def post(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                self.url, json=payload, headers=self.headers, timeout=self.timeout
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Model API returned HTTP {exc.response.status_code}"
            ) from None
        except httpx.RequestError:
            raise RuntimeError(
                "Model API request failed; check endpoint and network"
            ) from None
        try:
            data = response.json()
        except ValueError:
            raise ValueError("Model API returned invalid JSON") from None
        if not isinstance(data, dict):
            raise ValueError("Model API response must be a JSON object")
        return data


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _ordered_items(data: Any, count: int) -> list[dict[str, Any]]:
    if not isinstance(data, list) or len(data) != count:
        raise ValueError("Model API must return one result per input")
    items: dict[int, dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Model API result must be an object")
        index = item.get("index")
        if type(index) is not int or not 0 <= index < count or index in items:
            raise ValueError("Model API returned invalid or duplicate result indices")
        items[index] = item
    return [items[index] for index in range(count)]


class HTTPEmbedding:
    def __init__(self, config: LiteRAGConfig) -> None:
        self.api = ModelAPI(
            config.embedding_api_url,
            config.embedding_api_key,
            config.model_api_timeout,
        )
        self.model = config.embedding_model_name
        self.batch_size = config.embedding_batch_size
        self.dimension: int | None = None

    def encode(self, value: str | list[str]) -> list[float] | list[list[float]]:
        texts = [value] if isinstance(value, str) else value
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            response = self.api.post(
                {"model": self.model, "input": batch, "encoding_format": "float"}
            )
            for item in _ordered_items(response.get("data"), len(batch)):
                vector = item.get("embedding")
                if (
                    not isinstance(vector, list)
                    or not vector
                    or not all(_finite_number(number) for number in vector)
                ):
                    raise ValueError("Model API returned an invalid embedding vector")
                if self.dimension is not None and len(vector) != self.dimension:
                    raise ValueError("Model API returned inconsistent embedding dimensions")
                self.dimension = len(vector)
                vectors.append(vector)
        return vectors[0] if isinstance(value, str) else vectors

    def get_sentence_embedding_dimension(self) -> int:
        if self.dimension is not None:
            return self.dimension
        return len(self.encode("dimension probe"))


class HTTPReranker:
    def __init__(self, config: LiteRAGConfig) -> None:
        self.api = ModelAPI(
            config.reranker_api_url,
            config.reranker_api_key,
            config.model_api_timeout,
        )
        self.model = config.reranker_model_name

    def compute_score(self, pairs: list[list[str]]) -> list[float]:
        if not pairs:
            return []
        response = self.api.post(
            {
                "model": self.model,
                "query": pairs[0][0],
                "documents": [pair[1] for pair in pairs],
                "top_n": len(pairs),
            }
        )
        items = _ordered_items(response.get("results"), len(pairs))
        scores = [item.get("relevance_score") for item in items]
        if not all(_finite_number(score) for score in scores):
            raise ValueError("Model API returned invalid rerank scores")
        return scores


def create_embedding(config: LiteRAGConfig) -> Any:
    if config.embedding_provider == "http":
        return HTTPEmbedding(config)
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise RuntimeError(
            "Local embedding dependencies are missing; install with pip install -e '.[local]'"
        ) from None
    return SentenceTransformer(config.embedding_model_name)


def create_reranker(config: LiteRAGConfig) -> Any:
    if config.reranker_provider == "http":
        return HTTPReranker(config)
    try:
        from FlagEmbedding import FlagReranker
    except ImportError:
        raise RuntimeError(
            "Local reranker dependencies are missing; install with pip install -e '.[local]'"
        ) from None
    return FlagReranker(config.reranker_model_name, use_fp16=True)
