from __future__ import annotations

from elasticsearch import Elasticsearch

from app.config import ES_PASSWORD, ES_URL, ES_USERNAME


def get_es_client() -> Elasticsearch:
    return Elasticsearch(
        ES_URL,
        basic_auth=(ES_USERNAME, ES_PASSWORD),
        request_timeout=30,
    )
