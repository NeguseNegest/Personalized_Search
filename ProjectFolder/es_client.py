from __future__ import annotations
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from elasticsearch import Elasticsearch

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / "elastic-start-local" / ".env"
load_dotenv(ENV_PATH)

ES_URL = os.getenv("ES_LOCAL_URL", "http://localhost:9200")
ES_USERNAME = os.getenv("ES_LOCAL_USERNAME", "elastic")
ES_PASSWORD = os.getenv("ES_LOCAL_PASSWORD", "")
ES_API_KEY = os.getenv("ES_LOCAL_API_KEY", "")


def _build_client() -> Elasticsearch:
    if ES_API_KEY:
        client = Elasticsearch(ES_URL, api_key=ES_API_KEY, request_timeout=30)
    elif ES_PASSWORD:
        client = Elasticsearch(
            ES_URL,
            basic_auth=(ES_USERNAME, ES_PASSWORD),
            request_timeout=30,
        )
    else:
        client = Elasticsearch(ES_URL, request_timeout=30)
    return client


def _test_connection(client: Elasticsearch) -> None:
    try:
        info = client.info()
        print(
            f"[es_client] Connected to Elasticsearch "
            f"v{info['version']['number']} "
            f"cluster '{info['cluster_name']}'"
        )
    except Exception as exc:
        print(f"[es_client] Cannot reach Elasticsearch at {ES_URL}: {exc}")
        sys.exit(1)

connector: Elasticsearch = _build_client()
_test_connection(connector)
