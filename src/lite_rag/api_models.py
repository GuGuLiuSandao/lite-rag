from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field


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
    file_ids: list[Annotated[str, Field(strict=True, min_length=1, max_length=128)]] | None = Field(
        default=None, max_length=1000
    )
    mode: str | None = None
    enable_reranker: bool | None = None
    recall_top_k: int = 20
    final_top_k: int = 5


class HealthResponse(BaseModel):
    ok: bool = True
    result: dict[str, str]
