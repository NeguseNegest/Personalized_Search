from es_client import connector
from datetime import datetime, timezone

LOGS_INDEX = "user_logs"

# Mapping for the user logs index
logs_mapping = {
    "mappings": {
        "properties": {
            "user_id":   {"type": "keyword"},
            "query":     {"type": "text"},
            "doc_id":    {"type": "keyword"},
            "title":     {"type": "text"},
            "author":    {"type": "keyword"},
            "genres":    {"type": "keyword"},
            "timestamp": {"type": "date"}
        }
    }
}

def ensure_logs_index():
    """Create the user_logs index if it doesn't exist yet."""
    if not connector.indices.exists(index=LOGS_INDEX):
        connector.indices.create(index=LOGS_INDEX, body=logs_mapping)

def log_click(user_id: str, query: str, doc_id: str,
              title: str = "", author: str = "", genres: list = None):
    """
    Store a single click event. Each click is its own document —
    this gives you a full history rather than overwriting.
    """
    ensure_logs_index()
    connector.index(
        index=LOGS_INDEX,
        document={
            "user_id":   user_id,
            "query":     query,
            "doc_id":    doc_id,
            "title":     title,
            "author":    author,
            "genres":    genres or [],
            "timestamp": datetime.now(timezone.utc).isoformat()
        },
        refresh="wait_for"
    )

def get_user_profile(user_id: str, max_clicks: int = 100) -> dict:
    """
    Return aggregated click data for a user — useful for re-ranking later.
    Returns:
      {
        "clicked_doc_ids": {"doc123": 3, "doc456": 1, ...},
        "genre_counts":    {"Fiction": 5, "Mystery": 2, ...},
        "author_counts":   {"Orwell": 3, ...},
        "recent_queries":  ["farm animals", "satire", ...]
      }
    """
    ensure_logs_index()
    response = connector.search(
        index=LOGS_INDEX,
        query={"term": {"user_id": user_id}},
        sort=[{"timestamp": {"order": "desc"}}],
        size=max_clicks
    )

    clicked_doc_ids = {}
    genre_counts    = {}
    author_counts   = {}
    recent_queries  = []

    for hit in response["hits"]["hits"]:
        src = hit["_source"]

        # Count clicks per document
        doc_id = src.get("doc_id", "")
        clicked_doc_ids[doc_id] = clicked_doc_ids.get(doc_id, 0) + 1

        # Count genre preferences
        for genre in src.get("genres", []):
            genre_counts[genre] = genre_counts.get(genre, 0) + 1

        # Count author preferences
        author = src.get("author", "")
        if author:
            author_counts[author] = author_counts.get(author, 0) + 1

        # Collect recent queries (deduplicated, preserving order)
        q = src.get("query", "")
        if q and q not in recent_queries:
            recent_queries.append(q)

    return {
        "clicked_doc_ids": clicked_doc_ids,
        "genre_counts":    genre_counts,
        "author_counts":   author_counts,
        "recent_queries":  recent_queries
    }