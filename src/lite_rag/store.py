from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

import lancedb

from .config import LiteRAGConfig
from .metadata import SQLiteMetadataStore
from .models import build_chunk_model
from .utils import chunk_text, read_text_file, utc_now


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
        self._pending_chunk_records: list[dict[str, Any]] | None = None

    def _get_embed_model(self):
        if self._embed_model is None:
            from sentence_transformers import SentenceTransformer

            self._embed_model = SentenceTransformer(self.config.embedding_model_name)
        return self._embed_model

    def _get_reranker(self, *, enabled: bool | None = None):
        reranker_enabled = self.config.enable_reranker if enabled is None else enabled
        if not reranker_enabled or self._reranker_unavailable:
            return None

        if self._reranker is None:
            try:
                from FlagEmbedding import FlagReranker

                self._reranker = FlagReranker(
                    self.config.reranker_model_name,
                    use_fp16=True,
                )
            except Exception:
                self._reranker_unavailable = True
                return None
        return self._reranker

    def _get_chunks_table(self):
        if self._chunks_table is not None:
            return self._chunks_table

        existing_tables = set(self._db.table_names())
        table_name = self.config.chunks_table_name
        if table_name in existing_tables:
            self._chunks_table = self._db.open_table(table_name)
            return self._chunks_table

        model = self._get_embed_model()
        dim = model.get_sentence_embedding_dimension()
        if dim is None:
            raise ValueError("Embedding model dimension is unavailable")

        schema = build_chunk_model(dim)
        self._chunks_table = self._db.create_table(table_name, schema=schema)
        self._chunks_table.create_fts_index("text", replace=True)
        return self._chunks_table

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

    def get_file_content(self, file_id: str) -> dict[str, Any]:
        file_record = self._metadata.get_file(file_id)
        stored_path = Path(file_record["stored_path"]).expanduser().resolve()
        text = read_text_file(stored_path)
        return {
            "file": file_record,
            "content": text,
        }

    def list_file_chunks(self, file_id: str) -> list[dict[str, Any]]:
        return self._metadata.list_file_chunks(file_id)

    def add_file(
        self, kb_ref: str, source_path: str, title: str | None = None
    ) -> dict[str, Any]:
        kb_id, kb = self._metadata.resolve_kb(kb_ref)
        path = Path(source_path).expanduser().resolve()
        text = read_text_file(path)
        chunks = chunk_text(text, self.config.chunk_size, self.config.chunk_overlap)
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
    ) -> dict[str, Any]:
        file_record = self._metadata.get_file(file_id)
        kb = self._metadata.get_kb(file_record["kb_id"])

        if title is not None:
            file_record["title"] = title

        previous_record = dict(file_record)
        backup_path: Path | None = None
        previous_chunks: list[str] | None = None
        previous_chunk_records = self._metadata.list_file_chunks(file_id)

        if source_path is not None:
            path = Path(source_path).expanduser().resolve()
            text = read_text_file(path)
            chunks = chunk_text(text, self.config.chunk_size, self.config.chunk_overlap)
            if not chunks:
                raise ValueError("File is empty after text extraction")

            stored_path = Path(file_record["stored_path"])
            if stored_path.exists():
                previous_text = read_text_file(stored_path)
                previous_chunks = chunk_text(
                    previous_text,
                    self.config.chunk_size,
                    self.config.chunk_overlap,
                )
                backup_path = stored_path.with_name(
                    f"{stored_path.name}.bak-{uuid.uuid4().hex}"
                )
                shutil.copy2(stored_path, backup_path)

            try:
                shutil.copy2(path, stored_path)
                file_record["source_name"] = path.name
                file_record["chunk_count"] = len(chunks)
                file_record["updated_at"] = utc_now()
                chunk_records = self._build_chunk_records(kb, file_record, chunks)
                self._delete_chunks(file_id)
                self._pending_chunk_records = chunk_records
                self._index_chunks(kb, file_record, chunks)
                self._metadata.create_chunks(chunk_records)
            except Exception:
                if backup_path is not None and backup_path.exists():
                    shutil.copy2(backup_path, stored_path)

                if previous_chunks:
                    try:
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
                    except Exception:
                        pass

                raise
            finally:
                self._pending_chunk_records = None
                if backup_path is not None and backup_path.exists():
                    backup_path.unlink()

        file_record["kb_name"] = kb["name"]
        if source_path is None:
            file_record["updated_at"] = utc_now()
        return self._metadata.update_file(file_record)

    def delete_file(self, file_id: str) -> dict[str, Any]:
        return self._delete_file_internal(file_id)

    def _delete_file_internal(self, file_id: str) -> dict[str, Any]:
        file_record = self._metadata.get_file(file_id)
        self._delete_chunks(file_id)
        stored_path = Path(file_record["stored_path"])
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

        table = self._get_chunks_table()
        query_builder = None

        if normalized_mode == "vector":
            query_vector = self._get_embed_model().encode(query)
            query_builder = table.search(query_vector)
        elif normalized_mode == "fts":
            query_builder = table.search(query, query_type="fts")
        else:
            query_vector = self._get_embed_model().encode(query)
            query_builder = (
                table.search(query_type="hybrid").vector(query_vector).text(query)
            )

        if kb_id is not None:
            query_builder = query_builder.where(f"kb_id = '{self._escape_sql(kb_id)}'")

        results = query_builder.limit(recall_top_k).to_list()
        if not results:
            return []

        reranker = self._get_reranker(enabled=enable_reranker)
        if reranker is None:
            return [
                self._normalize_result(item, score=item.get("_score"))
                for item in results[:final_top_k]
            ]

        texts = [item["text"] for item in results]
        pairs = [[query, text] for text in texts]
        try:
            scores = reranker.compute_score(pairs)
            if isinstance(scores, float):
                scores = [scores]
        except Exception:
            self._reranker_unavailable = True
            return [
                self._normalize_result(item, score=item.get("_score"))
                for item in results[:final_top_k]
            ]

        rescored = []
        for item, score in zip(results, scores):
            rescored.append(self._normalize_result(item, score=score))

        rescored.sort(key=lambda item: item["score"], reverse=True)
        return rescored[:final_top_k]

    @staticmethod
    def _normalize_result(item: dict[str, Any], score: float | None) -> dict[str, Any]:
        return {
            "chunk_id": item.get("id"),
            "kb_id": item.get("kb_id"),
            "kb_name": item.get("kb_name"),
            "file_id": item.get("file_id"),
            "file_name": item.get("file_name"),
            "chunk_index": item.get("chunk_index"),
            "score": score,
            "text": item.get("text"),
        }

    @staticmethod
    def _escape_sql(value: str) -> str:
        return value.replace("'", "''")
