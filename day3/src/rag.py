from pathlib import Path

import chromadb

# Look for policies.md in the folder of this file, and one folder up
_HERE = Path(__file__).resolve().parent
_CANDIDATES = [_HERE / "policies.md", _HERE.parent / "policies.md"]

_collection = None


def _find_policies_file() -> Path:
    for p in _CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError("policies.md not found. Put it in the day2 folder.")


def _split_into_chunks(text: str) -> list[str]:
    """One chunk per '## ' section."""
    chunks = []
    for part in text.split("\n## ")[1:]:
        chunks.append(part.strip())
    return chunks


def build_index() -> None:
    """Build the vector store once. Call it at agent start."""
    global _collection
    if _collection is not None:
        return

    text = _find_policies_file().read_text(encoding="utf-8")
    chunks = _split_into_chunks(text)

    client = chromadb.Client()  # in memory
    _collection = client.create_collection("policies")
    _collection.add(
        documents=chunks,
        ids=[f"p{i}" for i in range(len(chunks))],
    )
    print(f"RAG index ready: {len(chunks)} chunks")


def search(query: str, k: int = 3) -> list[str]:
    build_index()
    result = _collection.query(query_texts=[query], n_results=k)
    return result["documents"][0]