from __future__ import annotations

import json
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
)
from embeddings_utils import encode_texts

INDEX_NAME = BOOKS_INDEX
FILE_PATH = "ProjectFolder/Corpus/booksummaries.txt"

EMBED_BATCH_SIZE = 32
ES_BULK_CHUNK_SIZE = 200
SUMMARY_CHAR_LIMIT = 200


def parse_line(line: str) -> dict | None:
    parts = line.rstrip("\n").split("\t", 6)
    if len(parts) != 7:
        return None

    wikipedia_id, freebase_id, title, author, pub_date, genres_raw, summary = parts

    try:
        parsed_genres = json.loads(genres_raw) if genres_raw.strip() else {}
        genres = list(parsed_genres.values())
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


def build_embedding_input(doc: dict) -> str:
    return (
      
        f"Summary: {doc['summary'][:SUMMARY_CHAR_LIMIT]}" # embed only the summary for faster idnexing 
    )

def _count_lines(path: str) -> int:
    with open(path, "r", encoding="utf-8") as fh:
        return sum(1 for _ in fh)


def _yield_encoded_actions(docs_batch: list[dict], texts_batch: list[str]):
    if not docs_batch:
        return

    vectors = encode_texts(texts_batch, batch_size=EMBED_BATCH_SIZE)

    for doc, vec in zip(docs_batch, vectors):
        doc["doc_vector"] = vec
        yield {
            "_index": INDEX_NAME,
            "_id": doc["wikipedia_id"],
            "_source": doc,
        }


def generate_actions(file_path: str):
    total = _count_lines(file_path)

    docs_batch: list[dict] = []
    texts_batch: list[str] = []

    with open(file_path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(
            tqdm(fh, total=total, desc="Preparing documents"),
            start=1,
        ):
            doc = parse_line(line)
            if doc is None:
                print(f"Skipping malformed line {lineno}")
                continue

            docs_batch.append(doc)
            texts_batch.append(build_embedding_input(doc))

            if len(docs_batch) >= EMBED_BATCH_SIZE:
                yield from _yield_encoded_actions(docs_batch, texts_batch)
                docs_batch = []
                texts_batch = []

    if docs_batch:
        yield from _yield_encoded_actions(docs_batch, texts_batch)


def _recreate_index(name: str, body: dict) -> None:
    if connector.indices.exists(index=name):
        connector.indices.delete(index=name)
        print(f"Deleted existing index: {name}")

    connector.indices.create(index=name, body=body)
    print(f"Created index: {name}")


if __name__ == "__main__":
    print("Creating indices...")
    _recreate_index(BOOKS_INDEX, BOOKS_SETTINGS)
    _recreate_index(LOGS_INDEX, LOGS_SETTINGS)
    _recreate_index(PROFILES_INDEX, PROFILES_SETTINGS)

    print(f"\nIndexing books from {FILE_PATH} ...")

    try:
        success, errors = helpers.bulk(
            connector,
            generate_actions(FILE_PATH),
            chunk_size=ES_BULK_CHUNK_SIZE,
        )
    except helpers.BulkIndexError as e:
        print("\nBulk indexing failed. First errors:")
        for err in e.errors[:3]:
            print(json.dumps(err, indent=2, ensure_ascii=False))
        raise

    print(f"\nIndexed {success} documents into '{BOOKS_INDEX}'.")
    if errors:
        print(f"{len(errors)} errors occurred during indexing.")