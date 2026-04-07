from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class APIResponse(BaseModel):
    ok: bool = True
    result: Any


class ErrorResponse(BaseModel):
    ok: bool = False
    error: str


class CreateKBRequest(BaseModel):
    name: str
    description: str | None = None


class UpdateKBRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class AddFileRequest(BaseModel):
    kb: str
    path: str
    title: str | None = None


class UpdateFileRequest(BaseModel):
    path: str | None = None
    title: str | None = None


class SearchRequest(BaseModel):
    query: str
    kb: str | None = None
    mode: str | None = None
    enable_reranker: bool | None = None
    recall_top_k: int = 20
    final_top_k: int = 5


class HealthResponse(BaseModel):
    ok: bool = True
    result: dict[str, str]
