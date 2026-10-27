from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteMetadataStore:
    def __init__(self, db_path: Path, legacy_manifest_path: Path | None = None):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()
        if legacy_manifest_path is not None:
            self._migrate_manifest_if_needed(legacy_manifest_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_bases (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    kb_id TEXT NOT NULL,
                    kb_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    chunk_size INTEGER,
                    chunk_overlap INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_files_kb_id ON files(kb_id)"
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(files)")}
            for column in ("chunk_size", "chunk_overlap"):
                if column not in columns:
                    connection.execute(f"ALTER TABLE files ADD COLUMN {column} INTEGER")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    kb_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE,
                    FOREIGN KEY(kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id, chunk_index)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS search_queries (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    kb_id TEXT,
                    kb_name TEXT,
                    mode TEXT NOT NULL,
                    result_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(kb_id) REFERENCES knowledge_bases(id) ON DELETE SET NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_search_queries_created_at ON search_queries(created_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chunk_hits (
                    chunk_id TEXT PRIMARY KEY,
                    kb_id TEXT NOT NULL,
                    kb_name TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    hits INTEGER NOT NULL,
                    last_hit_at TEXT NOT NULL,
                    FOREIGN KEY(chunk_id) REFERENCES chunks(id) ON DELETE CASCADE,
                    FOREIGN KEY(kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE,
                    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunk_hits_hits ON chunk_hits(hits DESC, last_hit_at DESC)"
            )

    def _migrate_manifest_if_needed(self, manifest_path: Path) -> None:
        if not manifest_path.exists():
            return

        with self._connect() as connection:
            kb_count = connection.execute(
                "SELECT COUNT(1) FROM knowledge_bases"
            ).fetchone()[0]
            file_count = connection.execute("SELECT COUNT(1) FROM files").fetchone()[0]
            if kb_count > 0 or file_count > 0:
                return

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            knowledge_bases = manifest.get("knowledge_bases", {})
            files = manifest.get("files", {})

            for kb in knowledge_bases.values():
                connection.execute(
                    """
                    INSERT INTO knowledge_bases (id, name, description, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        kb["id"],
                        kb["name"],
                        kb.get("description", ""),
                        kb["created_at"],
                        kb["updated_at"],
                    ),
                )

            for file_record in files.values():
                connection.execute(
                    """
                    INSERT INTO files (
                        id, kb_id, kb_name, title, source_name, stored_path,
                        chunk_count, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        file_record["id"],
                        file_record["kb_id"],
                        file_record["kb_name"],
                        file_record["title"],
                        file_record["source_name"],
                        file_record["stored_path"],
                        int(file_record["chunk_count"]),
                        file_record["created_at"],
                        file_record["updated_at"],
                    ),
                )

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    def resolve_kb(self, kb_ref: str) -> tuple[str, dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_bases WHERE id = ?",
                (kb_ref,),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    "SELECT * FROM knowledge_bases WHERE name = ?",
                    (kb_ref,),
                ).fetchone()
            if row is None:
                raise ValueError(f"Knowledge base not found: {kb_ref}")

            kb = self._row_to_dict(row)
            return kb["id"], kb

    def get_kb(self, kb_ref: str) -> dict[str, Any]:
        _, kb = self.resolve_kb(kb_ref)
        return kb

    def list_kbs(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_bases ORDER BY created_at ASC"
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def create_kb(self, kb: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM knowledge_bases WHERE name = ?",
                (kb["name"],),
            ).fetchone()
            if exists:
                raise ValueError(f"Knowledge base already exists: {kb['name']}")

            connection.execute(
                """
                INSERT INTO knowledge_bases (id, name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    kb["id"],
                    kb["name"],
                    kb["description"],
                    kb["created_at"],
                    kb["updated_at"],
                ),
            )
        return kb

    def update_kb(
        self,
        kb_ref: str,
        *,
        name: str | None = None,
        description: str | None = None,
        updated_at: str,
    ) -> tuple[dict[str, Any], bool]:
        kb_id, kb = self.resolve_kb(kb_ref)
        renamed = False

        with self._connect() as connection:
            if name and name != kb["name"]:
                exists = connection.execute(
                    "SELECT 1 FROM knowledge_bases WHERE name = ? AND id != ?",
                    (name, kb_id),
                ).fetchone()
                if exists:
                    raise ValueError(f"Knowledge base already exists: {name}")
                kb["name"] = name
                renamed = True

            if description is not None:
                kb["description"] = description

            kb["updated_at"] = updated_at

            connection.execute(
                """
                UPDATE knowledge_bases
                SET name = ?, description = ?, updated_at = ?
                WHERE id = ?
                """,
                (kb["name"], kb["description"], kb["updated_at"], kb_id),
            )

            if renamed:
                connection.execute(
                    "UPDATE files SET kb_name = ? WHERE kb_id = ?",
                    (kb["name"], kb_id),
                )

        return kb, renamed

    def delete_kb(self, kb_ref: str) -> dict[str, Any]:
        kb_id, kb = self.resolve_kb(kb_ref)
        with self._connect() as connection:
            connection.execute("DELETE FROM knowledge_bases WHERE id = ?", (kb_id,))
        return kb

    def list_files(self, kb_ref: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if kb_ref is None:
                rows = connection.execute(
                    "SELECT * FROM files ORDER BY created_at ASC"
                ).fetchall()
            else:
                kb_id, _ = self.resolve_kb(kb_ref)
                rows = connection.execute(
                    "SELECT * FROM files WHERE kb_id = ? ORDER BY created_at ASC",
                    (kb_id,),
                ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_file(self, file_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM files WHERE id = ?",
                (file_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"File not found: {file_id}")
        return self._row_to_dict(row)

    def create_file(self, file_record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO files (
                    id, kb_id, kb_name, title, source_name, stored_path,
                    chunk_count, created_at, updated_at, chunk_size, chunk_overlap
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_record["id"],
                    file_record["kb_id"],
                    file_record["kb_name"],
                    file_record["title"],
                    file_record["source_name"],
                    file_record["stored_path"],
                    int(file_record["chunk_count"]),
                    file_record["created_at"],
                    file_record["updated_at"],
                    file_record.get("chunk_size"),
                    file_record.get("chunk_overlap"),
                ),
            )
        return file_record

    def update_file(self, file_record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            result = connection.execute(
                """
                UPDATE files
                SET kb_id = ?, kb_name = ?, title = ?, source_name = ?, stored_path = ?,
                    chunk_count = ?, created_at = ?, updated_at = ?,
                    chunk_size = ?, chunk_overlap = ?
                WHERE id = ?
                """,
                (
                    file_record["kb_id"],
                    file_record["kb_name"],
                    file_record["title"],
                    file_record["source_name"],
                    file_record["stored_path"],
                    int(file_record["chunk_count"]),
                    file_record["created_at"],
                    file_record["updated_at"],
                    file_record.get("chunk_size"),
                    file_record.get("chunk_overlap"),
                    file_record["id"],
                ),
            )
        if result.rowcount == 0:
            raise ValueError(f"File not found: {file_record['id']}")
        return file_record

    def delete_file(self, file_id: str) -> dict[str, Any]:
        file_record = self.get_file(file_id)
        with self._connect() as connection:
            connection.execute("DELETE FROM files WHERE id = ?", (file_id,))
        return file_record

    def create_chunks(
        self, chunk_records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not chunk_records:
            return []

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO chunks (
                    id, file_id, kb_id, chunk_index, text, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["id"],
                        item["file_id"],
                        item["kb_id"],
                        int(item["chunk_index"]),
                        item["text"],
                        item["created_at"],
                        item["updated_at"],
                    )
                    for item in chunk_records
                ],
            )
        return chunk_records

    def list_file_chunks(self, file_id: str) -> list[dict[str, Any]]:
        self.get_file(file_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM chunks WHERE file_id = ? ORDER BY chunk_index ASC",
                (file_id,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_chunk(self, chunk_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM chunks WHERE id = ?",
                (chunk_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Chunk not found: {chunk_id}")
        return self._row_to_dict(row)

    def delete_chunks_by_file(self, file_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))

    def record_query(
        self,
        query_record: dict[str, Any],
        chunk_hits: list[dict[str, Any]],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO search_queries (
                    id, query, kb_id, kb_name, mode, result_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query_record["id"],
                    query_record["query"],
                    query_record.get("kb_id"),
                    query_record.get("kb_name"),
                    query_record["mode"],
                    int(query_record["result_count"]),
                    query_record["created_at"],
                ),
            )

            if chunk_hits:
                connection.executemany(
                    """
                    INSERT INTO chunk_hits (
                        chunk_id, kb_id, kb_name, file_id, file_name, chunk_index, hits, last_hit_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chunk_id) DO UPDATE SET
                        kb_id = excluded.kb_id,
                        kb_name = excluded.kb_name,
                        file_id = excluded.file_id,
                        file_name = excluded.file_name,
                        chunk_index = excluded.chunk_index,
                        hits = chunk_hits.hits + excluded.hits,
                        last_hit_at = excluded.last_hit_at
                    """,
                    [
                        (
                            item["chunk_id"],
                            item["kb_id"],
                            item["kb_name"],
                            item["file_id"],
                            item["file_name"],
                            int(item["chunk_index"]),
                            int(item.get("hits", 1)),
                            item["last_hit_at"],
                        )
                        for item in chunk_hits
                    ],
                )

    def get_dashboard(
        self,
        *,
        recent_query_limit: int = 10,
        chunk_hit_limit: int = 8,
        kb_id: str | None = None,
        file_id: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            kb_count = connection.execute(
                "SELECT COUNT(1) FROM knowledge_bases"
            ).fetchone()[0]
            file_count = connection.execute("SELECT COUNT(1) FROM files").fetchone()[0]
            chunk_count = connection.execute("SELECT COUNT(1) FROM chunks").fetchone()[
                0
            ]
            query_count = connection.execute(
                "SELECT COUNT(1) FROM search_queries"
            ).fetchone()[0]
            total_chunk_hits = connection.execute(
                "SELECT COALESCE(SUM(hits), 0) FROM chunk_hits"
            ).fetchone()[0]
            queried_kb_count = connection.execute(
                "SELECT COUNT(DISTINCT kb_id) FROM search_queries WHERE kb_id IS NOT NULL"
            ).fetchone()[0]

            query_filters: list[str] = []
            query_params: list[Any] = []
            chunk_filters: list[str] = []
            chunk_params: list[Any] = []

            if kb_id is not None:
                query_filters.append("kb_id = ?")
                query_params.append(kb_id)
                chunk_filters.append("kb_id = ?")
                chunk_params.append(kb_id)
            if file_id is not None:
                chunk_filters.append("file_id = ?")
                chunk_params.append(file_id)

            query_where = (
                f"WHERE {' AND '.join(query_filters)}" if query_filters else ""
            )
            chunk_where = (
                f"WHERE {' AND '.join(chunk_filters)}" if chunk_filters else ""
            )

            recent_queries = connection.execute(
                f"""
                SELECT id, query, kb_id, kb_name, mode, result_count, created_at
                FROM search_queries
                {query_where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*query_params, recent_query_limit),
            ).fetchall()
            chunk_hits = connection.execute(
                f"""
                SELECT chunk_id, kb_id, kb_name, file_id, file_name, chunk_index, hits, last_hit_at
                FROM chunk_hits
                {chunk_where}
                ORDER BY hits DESC, last_hit_at DESC
                LIMIT ?
                """,
                (*chunk_params, chunk_hit_limit),
            ).fetchall()
            trend_rows = connection.execute(
                f"""
                SELECT substr(created_at, 1, 10) AS date, COUNT(1) AS query_count
                FROM search_queries
                {query_where}
                GROUP BY substr(created_at, 1, 10)
                ORDER BY date DESC
                LIMIT 7
                """,
                tuple(query_params),
            ).fetchall()

        trend_map = {row["date"]: row["query_count"] for row in trend_rows}
        ordered_dates = sorted(trend_map.keys())

        return {
            "stats": {
                "kb_count": kb_count,
                "file_count": file_count,
                "chunk_count": chunk_count,
                "query_count": query_count,
                "total_chunk_hits": total_chunk_hits,
                "queried_kb_count": queried_kb_count,
            },
            "query_trend": [
                {"date": date, "query_count": trend_map[date]} for date in ordered_dates
            ],
            "recent_queries": [self._row_to_dict(row) for row in recent_queries],
            "chunk_hits": [self._row_to_dict(row) for row in chunk_hits],
        }
