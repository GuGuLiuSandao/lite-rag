from __future__ import annotations

import hashlib
import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

import lancedb
from lancedb.index import FTS

from .config import LiteRAGConfig, validate_chunking
from .metadata import SQLiteMetadataStore
from .models import build_chunk_model
from .providers import create_embedding, create_reranker
from .utils import chunk_text, read_text_file, utc_now


logger = logging.getLogger(__name__)
EMBEDDING_METADATA_KEY = b"lite_rag.embedding"


class LiteRAGStore:
    def __init__(self, config: LiteRAGConfig):
        self.config = config
        self.config.ensure_dirs()
        self._db = lancedb.connect(str(self.config.db_dir))
        self._metadata = SQLiteMetadataStore(
            self.config.metadata_db_path,
            legacy_manifest_path=self.config.storage_root / "manifest.json",
        )
        self._embed_model = None
        self._reranker = None
        self._reranker_unavailable = False
        self._chunks_table = None
        self._fts_index_lock = RLock()
        self._pending_chunk_records: list[dict[str, Any]] | None = None

    def _get_embed_model(self):
        if self._embed_model is None:
            self._embed_model = create_embedding(self.config)
        return self._embed_model

    def _get_reranker(self, *, enabled: bool | None = None):
        reranker_enabled = self.config.enable_reranker if enabled is None else enabled
        if not reranker_enabled or self._reranker_unavailable:
            return None

        if self._reranker is None:
            try:
                self._reranker = create_reranker(self.config)
            except Exception as exc:
                logger.warning(
                    "Reranker unavailable; using retrieval scores (%s)",
                    type(exc).__name__,
                )
                self._reranker_unavailable = True
                return None
        return self._reranker

    def _get_chunks_table(self):
        with self._fts_index_lock:
            if self._chunks_table is not None:
                return self._chunks_table

            table_name = self.config.chunks_table_name
            if table_name in self._db.table_names():
                self._chunks_table = self._db.open_table(table_name)
            else:
                model = self._get_embed_model()
                dim = model.get_sentence_embedding_dimension()
                if dim is None:
                    raise ValueError("Embedding model dimension is unavailable")

                schema = build_chunk_model(dim).to_arrow_schema().with_metadata(
                    {EMBEDDING_METADATA_KEY: self._embedding_signature()}
                )
                self._chunks_table = self._db.create_table(table_name, schema=schema)

            self._maintain_fts_index()
            return self._chunks_table

    def _sync_fts_index(self, table) -> None:
        index = next(
            (item for item in table.list_indices()
             if item.index_type == "FTS" and item.columns == ["text"]),
            None,
        )
        details = {} if index is None else (index.index_details or {})
        if (
            index is None
            or details.get("base_tokenizer") != "icu"
            or details.get("remove_stop_words") is not False
        ):
            # ICU segments Chinese; retaining short terms also keeps C++/C searchable.
            table.create_index(
                "text", config=FTS(base_tokenizer="icu", remove_stop_words=False),
                name="text_idx" if index is None else index.name, replace=True,
            )
        elif table.index_stats(index.name).num_unindexed_rows:
            # optimize() also compacts data and prunes versions. Retain every
            # version since the Unix epoch; history cleanup is a separate task.
            retention = datetime.now(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
            table.optimize(cleanup_older_than=retention)

    def _maintain_fts_index(self) -> None:
        if self._chunks_table is None:
            return
        with self._fts_index_lock:
            try:
                self._sync_fts_index(self._chunks_table)
            except Exception:
                # Index maintenance must not roll back a successfully stored
                # document. LanceDB scans pending rows until the next retry.
                logger.warning(
                    "FTS index maintenance failed; pending rows remain searchable. "
                    "Will retry on the next document write or table reopen.",
                    exc_info=True,
                )

    def _embedding_signature(self) -> bytes:
        identity = [self.config.embedding_provider, self.config.embedding_model_name]
        if self.config.embedding_provider == "http":
            identity.append(self.config.embedding_api_url)
        return hashlib.sha256(json.dumps(identity).encode("utf-8")).hexdigest().encode()

    def _validate_embedding_index(self, table) -> None:
        signature = (table.schema.metadata or {}).get(EMBEDDING_METADATA_KEY)
        if signature is None:
            # Legacy tables were created without model metadata.
            if (
                self.config.embedding_provider == "local"
                and self.config.embedding_model_name == "BAAI/bge-m3"
            ):
                return
        elif signature == self._embedding_signature():
            return
        raise ValueError(
            "Embedding configuration does not match this index (or legacy model is unknown). "
            "Use a new LITE_RAG_STORAGE_ROOT and reimport files to rebuild embeddings."
        )

    def _validate_existing_embedding_index(self) -> None:
        if self.config.chunks_table_name in self._db.table_names():
            table = self._db.open_table(self.config.chunks_table_name)
            self._validate_embedding_index(table)

    def list_kbs(self) -> list[dict[str, Any]]:
        return self._metadata.list_kbs()

    def create_kb(self, name: str, description: str | None = None) -> dict[str, Any]:
        kb_id = str(uuid.uuid4())
        now = utc_now()
        kb = {
            "id": kb_id,
            "name": name,
            "description": description or "",
            "created_at": now,
            "updated_at": now,
        }
        kb = self._metadata.create_kb(kb)
        (self.config.files_dir / kb_id).mkdir(parents=True, exist_ok=True)
        return kb

    def get_kb(self, kb_ref: str) -> dict[str, Any]:
        return self._metadata.get_kb(kb_ref)

    def update_kb(
        self,
        kb_ref: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        kb, renamed = self._metadata.update_kb(
            kb_ref,
            name=name,
            description=description,
            updated_at=utc_now(),
        )
        if renamed:
            try:
                table = self._get_chunks_table()
                table.update(
                    where=f"kb_id = '{self._escape_sql(kb['id'])}'",
                    values={"kb_name": kb["name"]},
                )
                self._maintain_fts_index()
            except Exception:
                pass

        return kb

    def delete_kb(self, kb_ref: str) -> dict[str, Any]:
        kb_id, kb = self._metadata.resolve_kb(kb_ref)
        file_ids = [
            file_record["id"] for file_record in self._metadata.list_files(kb_ref=kb_id)
        ]
        for file_id in file_ids:
            self._delete_file_internal(file_id)

        self._metadata.delete_kb(kb_id)
        kb_dir = self.config.files_dir / kb_id
        if kb_dir.exists():
            shutil.rmtree(kb_dir)
        return kb

    def list_files(self, kb_ref: str | None = None) -> list[dict[str, Any]]:
        return self._metadata.list_files(kb_ref=kb_ref)

    def get_file(self, file_id: str) -> dict[str, Any]:
        return self._metadata.get_file(file_id)

    def _stored_file_path(self, file_record: dict[str, Any]) -> Path:
        # Resolve against the active root so existing data survives bind mounts
        # and moving the storage directory between machines.
        return (
            self.config.files_dir
            / file_record["kb_id"]
            / Path(file_record["stored_path"]).name
        )

    def get_file_content(self, file_id: str) -> dict[str, Any]:
        file_record = self._metadata.get_file(file_id)
        stored_path = self._stored_file_path(file_record)
        text = read_text_file(stored_path)
        return {
            "file": file_record,
            "content": text,
        }

    def list_file_chunks(self, file_id: str) -> list[dict[str, Any]]:
        return self._metadata.list_file_chunks(file_id)

    def get_chunk(self, chunk_id: str) -> dict[str, Any]:
        return self._metadata.get_chunk(chunk_id)

    def get_dashboard(
        self,
        *,
        kb_id: str | None = None,
        file_id: str | None = None,
    ) -> list[dict[str, Any]] | dict[str, Any]:
        return self._metadata.get_dashboard(kb_id=kb_id, file_id=file_id)

    def _resolve_chunking(
        self,
        file_record: dict[str, Any],
        chunk_size: int | None,
        chunk_overlap: int | None,
    ) -> tuple[int, int]:
        if chunk_size is None:
            chunk_size = file_record.get("chunk_size")
        if chunk_size is None:
            chunk_size = self.config.chunk_size
        if chunk_overlap is None:
            chunk_overlap = file_record.get("chunk_overlap")
        if chunk_overlap is None:
            chunk_overlap = self.config.chunk_overlap
        validate_chunking(chunk_size, chunk_overlap)
        return chunk_size, chunk_overlap

    def add_file(
        self,
        kb_ref: str,
        source_path: str,
        title: str | None = None,
        *,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> dict[str, Any]:
        chunk_size, chunk_overlap = self._resolve_chunking({}, chunk_size, chunk_overlap)
        kb_id, kb = self._metadata.resolve_kb(kb_ref)
        self._validate_existing_embedding_index()
        path = Path(source_path).expanduser().resolve()
        text = read_text_file(path)
        chunks = chunk_text(text, chunk_size, chunk_overlap)
        if not chunks:
            raise ValueError("File is empty after text extraction")

        file_id = str(uuid.uuid4())
        stored_name = f"{file_id}{path.suffix.lower()}"
        stored_path = self.config.files_dir / kb_id / stored_name
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, stored_path)

        file_record = {
            "id": file_id,
            "kb_id": kb_id,
            "kb_name": kb["name"],
            "title": title or path.name,
            "source_name": path.name,
            "stored_path": str(stored_path),
            "chunk_count": len(chunks),
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        chunk_records = self._build_chunk_records(kb, file_record, chunks)
        file_created = False
        try:
            self._pending_chunk_records = chunk_records
            self._index_chunks(kb, file_record, chunks)
            self._metadata.create_file(file_record)
            file_created = True
            self._metadata.create_chunks(chunk_records)
            self._maintain_fts_index()
            return file_record
        except Exception:
            self._delete_chunks(file_id)
            if file_created:
                try:
                    self._metadata.delete_file(file_id)
                except Exception:
                    pass
            if stored_path.exists():
                stored_path.unlink()
            raise
        finally:
            self._pending_chunk_records = None

    def update_file(
        self,
        file_id: str,
        *,
        source_path: str | None = None,
        title: str | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> dict[str, Any]:
        file_record = self._metadata.get_file(file_id)
        kb = self._metadata.get_kb(file_record["kb_id"])
        previous_record = dict(file_record)
        reindex = source_path is not None or chunk_size is not None or chunk_overlap is not None
        if reindex:
            chunk_size, chunk_overlap = self._resolve_chunking(
                file_record, chunk_size, chunk_overlap
            )
            self._validate_existing_embedding_index()

        if title is not None:
            file_record["title"] = title

        backup_path: Path | None = None
        rollback_failed = False
        previous_chunks: list[str] | None = None
        previous_chunk_records = self._metadata.list_file_chunks(file_id)

        if reindex:
            stored_path = self._stored_file_path(file_record)
            path = stored_path
            if source_path is not None:
                path = Path(source_path).expanduser().resolve()
            text = read_text_file(path)
            chunks = chunk_text(text, chunk_size, chunk_overlap)
            if not chunks:
                raise ValueError("File is empty after text extraction")

            # Keep the original vectors so rollback does not need a working model.
            table = None
            previous_index_rows = None
            scope = f"file_id = '{self._escape_sql(file_id)}'"
            if self.config.chunks_table_name in self._db.table_names():
                table = self._get_chunks_table()
                previous_index_rows = table.search().where(scope).limit(None).to_list()

            if stored_path.exists():
                # Restore the actual old chunks, even if server defaults changed.
                previous_chunks = [item["text"] for item in previous_chunk_records]
                if not previous_chunks:
                    old_size, old_overlap = self._resolve_chunking(previous_record, None, None)
                    previous_chunks = chunk_text(read_text_file(stored_path), old_size, old_overlap)
                if source_path is not None:
                    backup_path = stored_path.with_name(
                        f"{stored_path.name}.bak-{uuid.uuid4().hex}"
                    )
                    shutil.copy2(stored_path, backup_path)

            try:
                if source_path is not None:
                    shutil.copy2(path, stored_path)
                    file_record["source_name"] = path.name
                file_record["chunk_count"] = len(chunks)
                file_record["chunk_size"] = chunk_size
                file_record["chunk_overlap"] = chunk_overlap
                file_record["updated_at"] = utc_now()
                chunk_records = self._build_chunk_records(kb, file_record, chunks)
                self._delete_chunks(file_id)
                self._pending_chunk_records = chunk_records
                self._index_chunks(kb, file_record, chunks)
                self._metadata.create_chunks(chunk_records)
                self._metadata.update_file(file_record)
            except Exception:
                try:
                    if backup_path is not None and backup_path.exists():
                        shutil.copy2(backup_path, stored_path)
                    if table is not None:
                        table.delete(scope)
                        if previous_index_rows:
                            table.add(previous_index_rows)
                        self._metadata.delete_chunks_by_file(file_id)
                        self._metadata.create_chunks(previous_chunk_records)
                    elif previous_chunks:
                        self._delete_chunks(file_id)
                        restored_chunks = self._build_chunk_records(
                            kb,
                            previous_record,
                            previous_chunks,
                            previous_chunk_records,
                        )
                        self._pending_chunk_records = restored_chunks
                        self._index_chunks(kb, previous_record, previous_chunks)
                        self._metadata.create_chunks(restored_chunks)
                    self._maintain_fts_index()
                except Exception as rollback_error:
                    rollback_failed = True
                    recovery_path = backup_path or stored_path
                    logger.exception(
                        "File update rollback failed for %s; original text: %s",
                        file_id, recovery_path,
                    )
                    raise RuntimeError(
                        f"File update and rollback failed for {file_id}; "
                        f"original text: {recovery_path}"
                    ) from rollback_error

                raise
            finally:
                self._pending_chunk_records = None
                if backup_path is not None and backup_path.exists() and not rollback_failed:
                    backup_path.unlink()

        file_record["kb_name"] = kb["name"]
        if not reindex:
            file_record["updated_at"] = utc_now()
            self._metadata.update_file(file_record)
        self._maintain_fts_index()
        return file_record

    def delete_file(self, file_id: str) -> dict[str, Any]:
        return self._delete_file_internal(file_id)

    def _delete_file_internal(self, file_id: str) -> dict[str, Any]:
        file_record = self._metadata.get_file(file_id)
        self._delete_chunks(file_id)
        stored_path = self._stored_file_path(file_record)
        if stored_path.exists():
            stored_path.unlink()
        return self._metadata.delete_file(file_id)

    def _delete_chunks(self, file_id: str) -> None:
        self._metadata.delete_chunks_by_file(file_id)
        try:
            table = self._get_chunks_table()
        except Exception:
            return

        table.delete(f"file_id = '{self._escape_sql(file_id)}'")

    def _build_chunk_records(
        self,
        kb: dict[str, Any],
        file_record: dict[str, Any],
        chunks: list[str],
        previous_chunk_records: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        timestamp = file_record.get("updated_at") or utc_now()
        rows = []
        for index, chunk in enumerate(chunks):
            chunk_id = (
                previous_chunk_records[index]["id"]
                if previous_chunk_records is not None
                and index < len(previous_chunk_records)
                else str(uuid.uuid4())
            )
            rows.append(
                {
                    "id": chunk_id,
                    "kb_id": kb["id"],
                    "kb_name": kb["name"],
                    "file_id": file_record["id"],
                    "file_name": file_record["title"],
                    "chunk_index": index,
                    "text": chunk,
                    "created_at": file_record.get("created_at", timestamp),
                    "updated_at": timestamp,
                }
            )
        return rows

    def _index_chunks(
        self,
        kb: dict[str, Any],
        file_record: dict[str, Any],
        chunks: list[str],
    ) -> None:
        model = self._get_embed_model()
        table = self._get_chunks_table()
        self._validate_embedding_index(table)
        records = self._pending_chunk_records or self._build_chunk_records(
            kb, file_record, chunks
        )
        vectors = model.encode([item["text"] for item in records])

        rows = []
        for item, vector in zip(records, vectors):
            rows.append(
                {
                    "id": item["id"],
                    "kb_id": item["kb_id"],
                    "kb_name": item["kb_name"],
                    "file_id": item["file_id"],
                    "file_name": item["file_name"],
                    "chunk_index": item["chunk_index"],
                    "text": item["text"],
                    "vector": vector,
                }
            )

        table.add(rows)

    def search(
        self,
        query: str,
        *,
        kb_ref: str | None = None,
        file_ids: list[str] | None = None,
        mode: str | None = None,
        enable_reranker: bool | None = None,
        recall_top_k: int = 20,
        final_top_k: int = 5,
    ) -> list[dict[str, Any]]:
        normalized_mode = (mode or self.config.default_mode).lower()
        if normalized_mode not in {"vector", "fts", "hybrid"}:
            raise ValueError("mode must be one of: vector, fts, hybrid")

        kb_id = None
        if kb_ref is not None:
            kb_id, _ = self._metadata.resolve_kb(kb_ref)

        filters = []
        if kb_id is not None:
            filters.append(f"kb_id = '{self._escape_sql(kb_id)}'")
        if file_ids is not None:
            if (
                not isinstance(file_ids, list)
                or len(file_ids) > 1000
                or any(not isinstance(item, str) or not 1 <= len(item) <= 128 for item in file_ids)
            ):
                raise ValueError("file_ids must contain at most 1000 non-empty string IDs")
            # An explicit empty scope must never widen to the whole knowledge base.
            if not file_ids:
                return []
            quoted_ids = ", ".join(f"'{self._escape_sql(item)}'" for item in dict.fromkeys(file_ids))
            filters.append(f"file_id IN ({quoted_ids})")

        has_fts_text = any(char.isalnum() for char in query)
        if normalized_mode == "fts" and not has_fts_text:
            self._record_search(
                query=query,
                mode=normalized_mode,
                kb_id=kb_id,
                kb_name=None if kb_id is None else self._metadata.get_kb(kb_id)["name"],
                results=[],
            )
            return []

        table = self._get_chunks_table()
        query_builder = None
        retrieval_mode = normalized_mode
        if normalized_mode == "hybrid" and not has_fts_text:
            retrieval_mode = "vector"

        if retrieval_mode == "vector":
            self._validate_embedding_index(table)
            query_vector = self._get_embed_model().encode(query)
            query_builder = table.search(query_vector)
        elif normalized_mode == "fts":
            query_builder = table.search(query, query_type="fts")
        else:
            self._validate_embedding_index(table)
            query_vector = self._get_embed_model().encode(query)
            query_builder = (
                table.search(query_type="hybrid").vector(query_vector).text(query)
            )

        if filters:
            query_builder = query_builder.where(" AND ".join(filters), prefilter=True)

        results = query_builder.limit(recall_top_k).to_list()
        if not results:
            self._record_search(
                query=query,
                mode=normalized_mode,
                kb_id=kb_id,
                kb_name=None if kb_id is None else self._metadata.get_kb(kb_id)["name"],
                results=[],
            )
            return []

        retrieval_results = [
            self._normalize_result(
                item,
                final_score=self._get_retrieval_score(item, retrieval_mode),
                retrieval_score=self._get_retrieval_score(item, retrieval_mode),
                rerank_score=None,
            )
            for item in results
        ]

        reranker = self._get_reranker(enabled=enable_reranker)
        if reranker is None:
            final_results = retrieval_results[:final_top_k]
            self._record_search(
                query=query,
                mode=normalized_mode,
                kb_id=kb_id,
                kb_name=None
                if kb_id is None
                else final_results[0].get("kb_name")
                if final_results
                else self._metadata.get_kb(kb_id)["name"],
                results=final_results,
            )
            return final_results

        texts = [item["text"] for item in results]
        pairs = [[query, text] for text in texts]
        try:
            scores = reranker.compute_score(pairs)
            if isinstance(scores, float):
                scores = [scores]
        except Exception as exc:
            logger.warning(
                "Rerank failed; using retrieval scores (%s)", type(exc).__name__
            )
            # HTTP failures may be transient; retry on the next query.
            self._reranker_unavailable = self.config.reranker_provider == "local"
            self._record_search(
                query=query,
                mode=normalized_mode,
                kb_id=kb_id,
                kb_name=None if kb_id is None else self._metadata.get_kb(kb_id)["name"],
                results=retrieval_results[:final_top_k],
            )
            return retrieval_results[:final_top_k]

        rescored = []
        for item, score in zip(results, scores):
            retrieval_score = self._get_retrieval_score(item, retrieval_mode)
            rescored.append(
                self._normalize_result(
                    item,
                    final_score=score,
                    retrieval_score=retrieval_score,
                    rerank_score=score,
                )
            )

        rescored.sort(key=lambda item: item["final_score"], reverse=True)
        final_results = rescored[:final_top_k]
        self._record_search(
            query=query,
            mode=normalized_mode,
            kb_id=kb_id,
            kb_name=None
            if kb_id is None
            else final_results[0].get("kb_name")
            if final_results
            else self._metadata.get_kb(kb_id)["name"],
            results=final_results,
        )
        return final_results

    def _record_search(
        self,
        *,
        query: str,
        mode: str,
        kb_id: str | None,
        kb_name: str | None,
        results: list[dict[str, Any]],
    ) -> None:
        now = utc_now()
        try:
            self._metadata.record_query(
                {
                    "id": str(uuid.uuid4()),
                    "query": query,
                    "kb_id": kb_id,
                    "kb_name": kb_name,
                    "mode": mode,
                    "result_count": len(results),
                    "created_at": now,
                },
                [
                    {
                        "chunk_id": item["chunk_id"],
                        "kb_id": item["kb_id"],
                        "kb_name": item["kb_name"],
                        "file_id": item["file_id"],
                        "file_name": item["file_name"],
                        "chunk_index": item["chunk_index"],
                        "hits": 1,
                        "last_hit_at": now,
                    }
                    for item in results
                    if item.get("chunk_id")
                ],
            )
        except Exception:
            pass

    @staticmethod
    def _normalize_result(
        item: dict[str, Any],
        *,
        final_score: float | None,
        retrieval_score: float | None,
        rerank_score: float | None,
    ) -> dict[str, Any]:
        return {
            "chunk_id": item.get("id"),
            "kb_id": item.get("kb_id"),
            "kb_name": item.get("kb_name"),
            "file_id": item.get("file_id"),
            "file_name": item.get("file_name"),
            "chunk_index": item.get("chunk_index"),
            "score": final_score,
            "final_score": final_score,
            "retrieval_score": retrieval_score,
            "rerank_score": rerank_score,
            "text": item.get("text"),
        }

    @staticmethod
    def _get_retrieval_score(item: dict[str, Any], mode: str) -> float | None:
        if mode == "vector":
            return item.get("_distance", item.get("_score", item.get("score")))

        return item.get("_score", item.get("score", item.get("_relevance_score")))

    @staticmethod
    def _escape_sql(value: str) -> str:
        return value.replace("'", "''")
