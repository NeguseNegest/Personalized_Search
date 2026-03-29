from __future__ import annotations

from app.config import INDEX_NAME
from app.es_client import get_es_client


def main() -> None:
    es = get_es_client()

    if es.indices.exists(index=INDEX_NAME):
        print(f"Index '{INDEX_NAME}' already exists.")
        return

    mapping = {
        "mappings": {
            "properties": {
                "title": {"type": "text"},
                "content": {"type": "text"},
                "topics": {"type": "keyword"},
                "domain": {"type": "keyword"},
                "url": {"type": "keyword"},
            }
        }
    }

    es.indices.create(index=INDEX_NAME, **mapping)
    print(f"Created index '{INDEX_NAME}'.")


if __name__ == "__main__":
    main()
