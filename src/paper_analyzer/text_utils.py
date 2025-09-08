from typing import List


def chunk_text(text: str, max_chars: int = 4000, overlap: int = 200) -> List[str]:
    """Chunk text by characters with slight overlap to preserve context."""
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + max_chars)
        chunk = text[start:end]
        chunks.append(chunk)
        if end == n:
            break
        start = end - overlap
        if start < 0:
            start = 0
    return chunks

