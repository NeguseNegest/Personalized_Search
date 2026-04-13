from __future__ import annotations

from datetime import datetime, timezone

from es_client import connector
from es_mappings import LOGS_INDEX, LOGS_SETTINGS


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_logs_index() -> None:
    if not connector.indices.exists(index=LOGS_INDEX):
        connector.indices.create(index=LOGS_INDEX, body=LOGS_SETTINGS)


def log_click(
    user_id: str,
    query: str,
    doc_id: str,
    title: str = "",
    author: str = "",
    genres: list[str] | None = None,
) -> None:
    ensure_logs_index()

    connector.index(
        index=LOGS_INDEX,
        document={
            "user_id": user_id.strip(),
            "query": query.strip(),
            "doc_id": doc_id.strip(),
            "title": (title or "").strip(),
            "author": (author or "").strip(),
            "genres": genres or [],
            "timestamp": _utc_now_iso(),
        },
        refresh="wait_for",
    )