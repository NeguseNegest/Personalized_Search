from __future__ import annotations

import json
from pathlib import Path

from elasticsearch.helpers import bulk

from app.config import BASE_DIR, INDEX_NAME
from app.es_client import get_es_client


def main() -> None:
    docs_path = BASE_DIR / "data" / "demo_docs.json"
    docs = json.loads(docs_path.read_text(encoding="utf-8"))

    actions = [
        {
            "_index": INDEX_NAME,
            "_id": doc["id"],
            "_source": doc,
        }
        for doc in docs
    ]

    es = get_es_client()
    success, _ = bulk(es, actions)
    es.indices.refresh(index=INDEX_NAME)
    print(f"Indexed {success} demo documents into '{INDEX_NAME}'.")


if __name__ == "__main__":
    main()
