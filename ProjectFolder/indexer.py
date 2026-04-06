from __future__ import annotations
import json
from pathlib import Path
from elasticsearch import helpers
from tqdm import tqdm

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

INDEX_NAME = BOOKS_INDEX
FILE_PATH = "ProjectFolder/Corpus/booksummaries.txt"
USE_EMBEDDINGS = False

_model = None

def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> list[float]:
    if not USE_EMBEDDINGS:
        return [0.01] * VECTOR_DIM
    model = _get_model()
    return model.encode(text, show_progress_bar=False).tolist()



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


def _count_lines(path: str) -> int:
    with open(path, "r", encoding="utf-8") as fh:
        return sum(1 for _ in fh)


def generate_actions(file_path: str):
    total = _count_lines(file_path)
    with open(file_path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(
            tqdm(fh, total=total, desc="Preparing documents"), start=1
        ):
            doc = parse_line(line)
            if doc is None:
                print(f"⚠  Skipping malformed line {lineno}")
                continue

            embed_input = f"{doc['title']}. {' '.join(doc['genres'])}. {doc['summary'][:512]}"
            doc["doc_vector"] = embed_text(embed_input)

            yield {
                "_index": INDEX_NAME,
                "_id": doc["wikipedia_id"],
                "_source": doc,
            }

def _recreate_index(name: str, body: dict) -> None:
    """Delete (if exists) and create an index."""
    if connector.indices.exists(index=name):
        connector.indices.delete(index=name)
        print(f"  Deleted existing index: {name}")
    connector.indices.create(index=name, body=body)
    print(f"  Created index: {name}")

if __name__ == "__main__":
    print("Creating indices …")
    _recreate_index(BOOKS_INDEX, BOOKS_SETTINGS)
    _recreate_index(LOGS_INDEX, LOGS_SETTINGS)
    _recreate_index(PROFILES_INDEX, PROFILES_SETTINGS)

    print(f"\nIndexing books from {FILE_PATH} …")

    try:
        success, errors = helpers.bulk(
            connector,
            generate_actions(FILE_PATH),
            chunk_size=500,
        )
    except helpers.BulkIndexError as e:
        print("\n Fail, Reasons：")
        import json

        for err in e.errors[:2]:
            print(json.dumps(err, indent=2, ensure_ascii=False))
        exit(1)

    print(f"\n✅  Indexed {success} documents into '{BOOKS_INDEX}'.")
    if errors:
        print(f"⚠  {len(errors)} errors occurred during indexing.")
