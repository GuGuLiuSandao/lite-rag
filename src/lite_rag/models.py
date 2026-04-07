from __future__ import annotations

from lancedb.pydantic import LanceModel, Vector


def build_chunk_model(dim: int) -> type[LanceModel]:
    class KnowledgeChunk(LanceModel):
        id: str
        kb_id: str
        kb_name: str
        file_id: str
        file_name: str
        chunk_index: int
        text: str
        vector: Vector(dim)

    return KnowledgeChunk
