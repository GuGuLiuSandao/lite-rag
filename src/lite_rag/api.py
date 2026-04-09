from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path
from threading import Lock

import uvicorn
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api_models import (
    APIResponse,
    AddFileRequest,
    CreateKBRequest,
    ErrorResponse,
    HealthResponse,
    SearchRequest,
    UpdateFileRequest,
    UpdateKBRequest,
)
from .config import LiteRAGConfig
from .store import LiteRAGStore


@lru_cache(maxsize=1)
def get_store() -> LiteRAGStore:
    return LiteRAGStore(LiteRAGConfig.from_env())


WRITE_LOCK = Lock()


def _ok(result: object) -> APIResponse:
    return APIResponse(result=result)


def _translate_error(exc: Exception) -> None:
    if isinstance(exc, (ValueError, FileNotFoundError)):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail=str(exc)) from exc


def create_app() -> FastAPI:
    app = FastAPI(title="lite-rag", version="0.1.0")

    raw_origins = os.getenv("LITE_RAG_API_ALLOW_ORIGINS", "*")
    allow_origins = [item.strip() for item in raw_origins.split(",") if item.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_, exc: HTTPException) -> JSONResponse:
        body = ErrorResponse(error=str(exc.detail)).model_dump()
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(result={"status": "ok"})

    @app.get("/dashboard", response_model=APIResponse)
    def get_dashboard(
        kb_id: str | None = Query(default=None),
        file_id: str | None = Query(default=None),
        store: LiteRAGStore = Depends(get_store),
    ) -> APIResponse:
        try:
            return _ok(store.get_dashboard(kb_id=kb_id, file_id=file_id))
        except Exception as exc:
            _translate_error(exc)

    @app.post("/kb", response_model=APIResponse)
    def create_kb(
        payload: CreateKBRequest, store: LiteRAGStore = Depends(get_store)
    ) -> APIResponse:
        try:
            with WRITE_LOCK:
                return _ok(
                    store.create_kb(name=payload.name, description=payload.description)
                )
        except Exception as exc:
            _translate_error(exc)

    @app.get("/kb", response_model=APIResponse)
    def list_kbs(
        name: str | None = Query(default=None),
        store: LiteRAGStore = Depends(get_store),
    ) -> APIResponse:
        try:
            items = store.list_kbs()
            if name:
                items = [item for item in items if item["name"] == name]
            return _ok(items)
        except Exception as exc:
            _translate_error(exc)

    @app.get("/kb/{kb_ref}", response_model=APIResponse)
    def get_kb(kb_ref: str, store: LiteRAGStore = Depends(get_store)) -> APIResponse:
        try:
            return _ok(store.get_kb(kb_ref))
        except Exception as exc:
            _translate_error(exc)

    @app.patch("/kb/{kb_ref}", response_model=APIResponse)
    def update_kb(
        kb_ref: str,
        payload: UpdateKBRequest,
        store: LiteRAGStore = Depends(get_store),
    ) -> APIResponse:
        try:
            with WRITE_LOCK:
                return _ok(
                    store.update_kb(
                        kb_ref,
                        name=payload.name,
                        description=payload.description,
                    )
                )
        except Exception as exc:
            _translate_error(exc)

    @app.delete("/kb/{kb_ref}", response_model=APIResponse)
    def delete_kb(kb_ref: str, store: LiteRAGStore = Depends(get_store)) -> APIResponse:
        try:
            with WRITE_LOCK:
                return _ok(store.delete_kb(kb_ref))
        except Exception as exc:
            _translate_error(exc)

    @app.post("/file", response_model=APIResponse)
    def add_file(
        payload: AddFileRequest, store: LiteRAGStore = Depends(get_store)
    ) -> APIResponse:
        try:
            with WRITE_LOCK:
                return _ok(
                    store.add_file(
                        kb_ref=payload.kb, source_path=payload.path, title=payload.title
                    )
                )
        except Exception as exc:
            _translate_error(exc)

    @app.post("/file/upload", response_model=APIResponse)
    async def upload_file(
        kb: str = Form(...),
        file: UploadFile = File(...),
        title: str | None = Form(default=None),
        store: LiteRAGStore = Depends(get_store),
    ) -> APIResponse:
        temp_path: Path | None = None
        try:
            suffix = Path(file.filename or "").suffix.lower()
            if not suffix:
                raise ValueError("Uploaded file must include a supported extension")

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_path = Path(temp_file.name)

            with WRITE_LOCK:
                return _ok(
                    store.add_file(
                        kb_ref=kb,
                        source_path=str(temp_path),
                        title=title or file.filename,
                    )
                )
        except Exception as exc:
            _translate_error(exc)
        finally:
            await file.close()
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

    @app.get("/file", response_model=APIResponse)
    def list_files(
        kb: str | None = Query(default=None),
        store: LiteRAGStore = Depends(get_store),
    ) -> APIResponse:
        try:
            return _ok(store.list_files(kb_ref=kb))
        except Exception as exc:
            _translate_error(exc)

    @app.get("/file/{file_id}", response_model=APIResponse)
    def get_file(file_id: str, store: LiteRAGStore = Depends(get_store)) -> APIResponse:
        try:
            return _ok(store.get_file(file_id))
        except Exception as exc:
            _translate_error(exc)

    @app.get("/file/{file_id}/content", response_model=APIResponse)
    def get_file_content(
        file_id: str, store: LiteRAGStore = Depends(get_store)
    ) -> APIResponse:
        try:
            return _ok(store.get_file_content(file_id))
        except Exception as exc:
            _translate_error(exc)

    @app.get("/file/{file_id}/chunks", response_model=APIResponse)
    def list_file_chunks(
        file_id: str, store: LiteRAGStore = Depends(get_store)
    ) -> APIResponse:
        try:
            return _ok(store.list_file_chunks(file_id))
        except Exception as exc:
            _translate_error(exc)

    @app.get("/chunk/{chunk_id}", response_model=APIResponse)
    def get_chunk(
        chunk_id: str, store: LiteRAGStore = Depends(get_store)
    ) -> APIResponse:
        try:
            return _ok(store.get_chunk(chunk_id))
        except Exception as exc:
            _translate_error(exc)

    @app.patch("/file/{file_id}", response_model=APIResponse)
    def update_file(
        file_id: str,
        payload: UpdateFileRequest,
        store: LiteRAGStore = Depends(get_store),
    ) -> APIResponse:
        try:
            with WRITE_LOCK:
                return _ok(
                    store.update_file(
                        file_id, source_path=payload.path, title=payload.title
                    )
                )
        except Exception as exc:
            _translate_error(exc)

    @app.delete("/file/{file_id}", response_model=APIResponse)
    def delete_file(
        file_id: str, store: LiteRAGStore = Depends(get_store)
    ) -> APIResponse:
        try:
            with WRITE_LOCK:
                return _ok(store.delete_file(file_id))
        except Exception as exc:
            _translate_error(exc)

    @app.post("/search", response_model=APIResponse)
    def search(
        payload: SearchRequest, store: LiteRAGStore = Depends(get_store)
    ) -> APIResponse:
        try:
            return _ok(
                store.search(
                    query=payload.query,
                    kb_ref=payload.kb,
                    mode=payload.mode,
                    enable_reranker=payload.enable_reranker,
                    recall_top_k=payload.recall_top_k,
                    final_top_k=payload.final_top_k,
                )
            )
        except Exception as exc:
            _translate_error(exc)

    return app


app = create_app()


def run() -> None:
    uvicorn.run("lite_rag.api:app", host="127.0.0.1", port=8000, reload=False)
