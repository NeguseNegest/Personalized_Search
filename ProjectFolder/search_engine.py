from __future__ import annotations
import math

from es_client import connector
from es_mappings import BOOKS_INDEX
from user_logs import get_user_profile
from embeddings_utils import (
    encode_text,
    weighted_average_vectors,
    cosine_similarity,
)

INDEX_NAME = BOOKS_INDEX

RETRIEVE_K = 50

GENRE_WEIGHT = 2.0
AUTHOR_WEIGHT = 1.5
CLICK_WEIGHT = 2.5
QUERY_VECTOR_WEIGHT = 1.5
USER_VECTOR_WEIGHT = 2.0


def _build_baseline_query(query_str: str, size: int) -> dict:
    return {
        "size": size,
        "query": {
            "multi_match": {
                "query": query_str,
                "fields": ["title^3", "author^2", "summary", "genres"],
                "type": "best_fields",
            }
        },
    }


def _normalize_counts(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values())
    if total == 0:
        return {}
    return {key: value / total for key, value in counts.items()}


def _truncate_summary(summary: str, max_len: int = 500) -> str:
    if not summary:
        return ""
    if len(summary) <= max_len:
        return summary
    return summary[:max_len] + "..."


def _format_baseline_hit(hit: dict) -> dict:
    src = hit["_source"]
    es_score = float(hit["_score"] or 0.0)

    return {
        "id": hit["_id"],
        "title": src.get("title", "Untitled"),
        "author": src.get("author", "Unknown"),
        "publication_date": src.get("publication_date"),
        "genres": src.get("genres", []),
        "summary": _truncate_summary(src.get("summary", "")),
        "es_score": round(es_score, 3),
        "final_score": round(es_score, 3),
        "genre_bonus": 0.0,
        "author_bonus": 0.0,
        "click_bonus": 0.0,
        "query_semantic_bonus": 0.0,
        "user_semantic_bonus": 0.0,
    }


def _get_user_vector(profile: dict) -> list[float]:
    clicked_doc_ids = profile.get("clicked_doc_ids", {})
    if not clicked_doc_ids:
        return []

    doc_ids = list(clicked_doc_ids.keys())[:20]
    resp = connector.mget(index=BOOKS_INDEX, ids=doc_ids)

    vectors = []
    weights = []

    for doc in resp["docs"]:
        if not doc.get("found"):
            continue

        src = doc.get("_source", {})
        vec = src.get("doc_vector", [])
        if not vec:
            continue

        doc_id = doc["_id"]
        click_count = clicked_doc_ids.get(doc_id, 0)

        if click_count > 0:
            vectors.append(vec)
            weights.append(float(click_count))

    return weighted_average_vectors(vectors, weights)


def _rerank_hits(hits: list[dict], profile: dict, query: str) -> list[dict]:
    genre_pref = _normalize_counts(profile.get("genre_counts", {}))
    author_pref = _normalize_counts(profile.get("author_counts", {}))
    clicked_doc_ids = profile.get("clicked_doc_ids", {})

    use_query_semantics = len(query.split()) >= 3
    query_vector = encode_text(query) if use_query_semantics else []

    user_vector = _get_user_vector(profile)

    reranked = []

    for hit in hits:
        src = hit["_source"]
        doc_id = hit["_id"]
        bm25 = float(hit["_score"] or 0.0)

        book_genres = src.get("genres", []) or []
        book_author = src.get("author", "") or ""
        doc_vector = src.get("doc_vector", []) or []

        raw_genre_bonus = sum(genre_pref.get(genre, 0.0) for genre in book_genres)
        raw_author_bonus = author_pref.get(book_author, 0.0)
        raw_click_bonus = math.log1p(clicked_doc_ids.get(doc_id, 0))

        genre_bonus = GENRE_WEIGHT * raw_genre_bonus
        author_bonus = AUTHOR_WEIGHT * raw_author_bonus
        click_bonus = CLICK_WEIGHT * raw_click_bonus

        query_semantic_bonus = QUERY_VECTOR_WEIGHT * max(0.0, cosine_similarity(query_vector, doc_vector))
        user_semantic_bonus = USER_VECTOR_WEIGHT * max(0.0, cosine_similarity(user_vector, doc_vector))

        final_score = (
            bm25
            + genre_bonus
            + author_bonus
            + click_bonus
            + query_semantic_bonus
            + user_semantic_bonus
        )

        reranked.append({
            "id": doc_id,
            "title": src.get("title", "Untitled"),
            "author": book_author or "Unknown",
            "publication_date": src.get("publication_date"),
            "genres": book_genres,
            "summary": _truncate_summary(src.get("summary", "")),
            "es_score": round(bm25, 3),
            "final_score": round(final_score, 3),
            "genre_bonus": round(genre_bonus, 3),
            "author_bonus": round(author_bonus, 3),
            "click_bonus": round(click_bonus, 3),
            "query_semantic_bonus": round(query_semantic_bonus, 3),
            "user_semantic_bonus": round(user_semantic_bonus, 3),
        })

    reranked.sort(key=lambda doc: doc["final_score"], reverse=True)
    return reranked


def search_books(query: str, size: int = 10, user_id: str = "") -> list[dict]:
    personalized = bool(user_id)

    retrieve_size = RETRIEVE_K if personalized else size
    body = _build_baseline_query(query_str=query, size=retrieve_size)

    response = connector.search(index=INDEX_NAME, body=body)
    hits = response["hits"]["hits"]

    if not personalized:
        return [_format_baseline_hit(hit) for hit in hits[:size]]

    profile = get_user_profile(user_id)
    if profile is None:
        profile = {
            "clicked_doc_ids": {},
            "genre_counts": {},
            "author_counts": {},
            "recent_queries": [],
        }

    reranked = _rerank_hits(hits, profile, query)
    return reranked[:size]


personalized_search = search_books