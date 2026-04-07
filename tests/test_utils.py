from lite_rag.utils import chunk_text


def test_chunk_text_returns_non_empty_chunks() -> None:
    text = "\n\n".join([
        "第一段内容" * 40,
        "第二段内容" * 40,
        "第三段内容" * 40,
    ])

    chunks = chunk_text(text, chunk_size=120, chunk_overlap=20)

    assert chunks
    assert all(chunk.strip() for chunk in chunks)
    assert len(chunks) >= 2
