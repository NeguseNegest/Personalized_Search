from __future__ import annotations
import json
import sys
from pathlib import Path
from elasticsearch import helpers
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

from es_client import connector
from es_mappings import (
    BOOKS_INDEX,
    BOOKS_SETTINGS,
    LOGS_INDEX,
    LOGS_SETTINGS,
    PROFILES_INDEX,
    PROFILES_SETTINGS,
    VECTOR_DIM,
)


# Configuration
INDEX_NAME = BOOKS_INDEX # exported for search_engine.py compatibility
FILE_PATH = "ProjectFolder/Corpus/booksummaries.txt"
BATCH_SIZE = 256  # texts encoded together per batch (GPU/CPU)


#  Embedding model  (all-MiniLM-L6-v2, 384 dimensions)
print("[indexer] Loading SentenceTransformer model (all-MiniLM-L6-v2) ...")
_model = SentenceTransformer("all-MiniLM-L6-v2")
print("[indexer] Model loaded ✓")


def embed_texts(texts: list[str]) -> list[list[float]]:
    # Batch-encode a list of strings → list of 384-dim float vectors.
    vectors = _model.encode(texts, show_progress_bar=False, batch_size=BATCH_SIZE)
    return [v.tolist() for v in vectors]


def embed_single(text: str) -> list[float]:
    # Encode one string → 384-dim float vector (convenience wrapper).
    return _model.encode(text, show_progress_bar=False).tolist()

#  Parsing
def parse_line(line: str) -> dict | None:
    parts = line.rstrip("\n").split("\t", 6)
    if len(parts) != 7:
        return None

    wikipedia_id, freebase_id, title, author, pub_date, genres_raw, summary = parts

    try:
        genres = list(json.loads(genres_raw).values())
    except Exception:
        genres = []

    return {
        "wikipedia_id": wikipedia_id,
        "freebase_id": freebase_id,
        "title": title.strip(),
        "author": author.strip(),
        "publication_date": pub_date.strip() if pub_date.strip() else None,
        "genres": genres,
        "summary": summary.strip(),
    }

def _build_embed_input(doc: dict) -> str:
    # Construct the text blob used as input for the embedding model.
    # Combines title + genre names + first 512 chars of summary so the vector
    # captures topical, categorical, AND content-level semantics.
    genre_str = " ".join(doc["genres"]) if doc["genres"] else ""
    return f"{doc['title']}. {genre_str}. {doc['summary'][:512]}"

#  Bulk action generator  (batch-encodes for speed)
def _count_lines(path: str) -> int:
    with open(path, "r", encoding="utf-8") as fh:
        return sum(1 for _ in fh)


def generate_actions(file_path: str):
    #Internally buffers BATCH_SIZE documents at a time so we can call `embed_texts()` in efficient batches instead of one-by-one.
    total = _count_lines(file_path)
    buffer: list[dict] = []
    embed_inputs: list[str] = []

    def _flush(buf, texts):
        #Encode accumulated batch and yield ES actions.
        vectors = embed_texts(texts)
        for doc, vec in zip(buf, vectors):
            doc["doc_vector"] = vec
            yield {
                "_index": INDEX_NAME,
                "_id": doc["wikipedia_id"],
                "_source": doc,
            }

    with open(file_path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(
                tqdm(fh, total=total, desc="Indexing books"), start=1
        ):
            doc = parse_line(line)
            if doc is None:
                print(f"Skipping malformed line {lineno}")
                continue

            buffer.append(doc)
            embed_inputs.append(_build_embed_input(doc))

            if len(buffer) >= BATCH_SIZE:
                yield from _flush(buffer, embed_inputs)
                buffer.clear()
                embed_inputs.clear()

    # Flush remaining partial batch
    if buffer:
        yield from _flush(buffer, embed_inputs)

#  Index helpers
def _recreate_index(name: str, body: dict) -> None:
    # Delete (if exists) then create an index.
    if connector.indices.exists(index=name):
        connector.indices.delete(index=name)
        print(f"  Deleted existing index: {name}")
    connector.indices.create(index=name, body=body)
    print(f"  Created index: {name}")


if __name__ == "__main__":
    print("=" * 60)
    print("  Book Summaries Indexer  (with real semantic vectors)")
    print("=" * 60)

    # Resolve the corpus path — handle running from project root or ProjectFolder
    corpus = Path(FILE_PATH)
    if not corpus.exists():
        alt = Path(__file__).resolve().parent / "Corpus" / "booksummaries.txt"
        if alt.exists():
            FILE_PATH = str(alt)
        else:
            print(f" Corpus file not found: {FILE_PATH}")
            print(f" Also tried: {alt}")
            sys.exit(1)

    print("\n1/2  Creating indices …")
    _recreate_index(BOOKS_INDEX, BOOKS_SETTINGS)
    _recreate_index(LOGS_INDEX, LOGS_SETTINGS)
    _recreate_index(PROFILES_INDEX, PROFILES_SETTINGS)

    print(f"\n2/2  Indexing books from {FILE_PATH} …")
    try:
        success, errors = helpers.bulk(
            connector,
            generate_actions(FILE_PATH),
            chunk_size=500,
        )
    except helpers.BulkIndexError as e:
        print("\n Bulk indexing failed.  First 3 errors:")
        for err in e.errors[:3]:
            print(json.dumps(err, indent=2, ensure_ascii=False))
        sys.exit(1)

    print(f"\n Indexed {success} documents into '{BOOKS_INDEX}'.")
    if errors:
        print(f" {len(errors)} errors occurred during indexing.")
    print("Done.")
