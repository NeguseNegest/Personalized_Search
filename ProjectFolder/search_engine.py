from __future__ import annotations

import math
import re

from es_client import connector
from es_mappings import BOOKS_INDEX
from user_profiles import get_user_profile
from embeddings_utils import (
    encode_text,
    weighted_average_vectors,
    cosine_similarity,
)

INDEX_NAME = BOOKS_INDEX

RETRIEVE_K = 100

EXPLICIT_GENRE_WEIGHT = 2.2
CLICK_GENRE_WEIGHT = 2.8

EXPLICIT_AUTHOR_WEIGHT = 1.8
CLICK_AUTHOR_WEIGHT = 2.2

EXPLICIT_BOOK_WEIGHT = 2.0
REPEAT_CLICK_WEIGHT = 1.6

QUERY_VECTOR_WEIGHT = 4.0
USER_VECTOR_WEIGHT = 8.0


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
    if total <= 0:
        return {}
    return {key: value / total for key, value in counts.items()}


def _truncate_summary(summary: str, max_len: int = 500) -> str:
    if not summary:
        return ""
    if len(summary) <= max_len:
        return summary
    return summary[:max_len] + "..."


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _tokenize_title(value: str) -> set[str]:
    normalized = _normalize_text(value)
    return set(re.findall(r"[a-z0-9]+", normalized))


def _profile_blend(num_clicks: int) -> tuple[float, float]:
    """
    Explicit profile should dominate at cold start.
    Click profile should dominate as evidence accumulates.

    With this formula:
      0 clicks  -> explicit=1.00, click=0.00
      5 clicks  -> explicit=0.50, click=0.50
      20 clicks -> explicit=0.20, click=0.80
    """
    num_clicks = max(0, int(num_clicks or 0))
    explicit_share = 5.0 / (num_clicks + 5.0)
    click_share = num_clicks / (num_clicks + 5.0)
    return explicit_share, click_share


def _best_book_match_score(candidate_title: str, favorite_books: list[str]) -> float:
    """
    Best fuzzy title overlap between the candidate book title
    and books the user explicitly says they liked.
    """
    candidate_norm = _normalize_text(candidate_title)
    candidate_tokens = _tokenize_title(candidate_title)

    if not candidate_norm or not favorite_books:
        return 0.0

    best = 0.0

    for book in favorite_books:
        book_norm = _normalize_text(book)
        if not book_norm:
            continue

        if candidate_norm == book_norm:
            return 1.0

        if book_norm in candidate_norm or candidate_norm in book_norm:
            best = max(best, 0.8)

        book_tokens = _tokenize_title(book)
        if candidate_tokens and book_tokens:
            overlap = len(candidate_tokens & book_tokens)
            if overlap > 0:
                dice = (2.0 * overlap) / (len(candidate_tokens) + len(book_tokens))
                best = max(best, dice)

    return min(best, 1.0)


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
        "full_summary": src.get("summary", ""),
        "es_score": round(es_score, 3),
        "final_score": round(es_score, 3),
        "genre_bonus": 0.0,
        "author_bonus": 0.0,
        "book_bonus": 0.0,
        "click_bonus": 0.0,
        "query_semantic_bonus": 0.0,
        "user_semantic_bonus": 0.0,
        "explicit_share": 0.0,
        "click_share": 0.0,
    }


def _get_click_user_vector(profile: dict) -> list[float]:
    clicked_doc_ids = profile.get("clicked_doc_ids", {}) or {}
    if not clicked_doc_ids:
        return []

    doc_ids = list(clicked_doc_ids.keys())[:30]
    resp = connector.mget(index=BOOKS_INDEX, ids=doc_ids)

    vectors = []
    weights = []

    for doc in resp["docs"]:
        if not doc.get("found"):
            continue

        src = doc.get("_source", {}) or {}
        vec = src.get("doc_vector", []) or []
        if not vec:
            continue

        doc_id = doc["_id"]
        click_count = int(clicked_doc_ids.get(doc_id, 0) or 0)
        if click_count <= 0:
            continue

        vectors.append(vec)
        weights.append(float(click_count))

    return weighted_average_vectors(vectors, weights)


def _get_combined_user_vector(profile: dict) -> tuple[list[float], float, float]:
    explicit_vector = profile.get("explicit_profile_vector", []) or []
    click_vector = _get_click_user_vector(profile)

    num_clicks = int(profile.get("num_clicks", 0) or 0)
    explicit_share, click_share = _profile_blend(num_clicks)

    vectors = []
    weights = []

    if explicit_vector:
        vectors.append(explicit_vector)
        weights.append(explicit_share)

    if click_vector:
        vectors.append(click_vector)
        weights.append(click_share)

    if not vectors:
        return [], explicit_share, click_share

    if len(vectors) == 1:
        return vectors[0], explicit_share, click_share

    return weighted_average_vectors(vectors, weights), explicit_share, click_share


def _rerank_hits(hits: list[dict], profile: dict, query: str) -> list[dict]:
    click_genre_pref = _normalize_counts(profile.get("click_genre_counts", {}) or {})
    click_author_pref = _normalize_counts(profile.get("click_author_counts", {}) or {})
    clicked_doc_ids = profile.get("clicked_doc_ids", {}) or {}

    explicit_genres = {
        _normalize_text(g) for g in (profile.get("favorite_genres", []) or []) if _normalize_text(g)
    }
    explicit_authors = {
        _normalize_text(a) for a in (profile.get("favorite_authors", []) or []) if _normalize_text(a)
    }
    favorite_books = profile.get("favorite_books", []) or []

    query_vector = encode_text(query) if query.strip() else []
    combined_user_vector, explicit_share, click_share = _get_combined_user_vector(profile)

    reranked = []

    for hit in hits:
        src = hit["_source"]
        doc_id = hit["_id"]

        title = src.get("title", "Untitled")
        book_author = src.get("author", "") or ""
        book_genres = src.get("genres", []) or []
        doc_vector = src.get("doc_vector", []) or []

        bm25 = float(hit["_score"] or 0.0)

        normalized_doc_genres = [_normalize_text(g) for g in book_genres if _normalize_text(g)]
        normalized_author = _normalize_text(book_author)

        explicit_genre_matches = sum(
            1.0 for genre in normalized_doc_genres if genre in explicit_genres
        )
        click_genre_matches = sum(
            float(click_genre_pref.get(genre, 0.0)) for genre in book_genres
        )

        explicit_author_match = 1.0 if normalized_author and normalized_author in explicit_authors else 0.0
        click_author_match = float(click_author_pref.get(book_author, 0.0))

        book_match_score = _best_book_match_score(title, favorite_books)
        repeat_click_score = math.log1p(int(clicked_doc_ids.get(doc_id, 0) or 0))

        genre_bonus = (
            explicit_share * EXPLICIT_GENRE_WEIGHT * explicit_genre_matches
            + click_share * CLICK_GENRE_WEIGHT * click_genre_matches
        )

        author_bonus = (
            explicit_share * EXPLICIT_AUTHOR_WEIGHT * explicit_author_match
            + click_share * CLICK_AUTHOR_WEIGHT * click_author_match
        )

        book_bonus = explicit_share * EXPLICIT_BOOK_WEIGHT * book_match_score
        click_bonus = click_share * REPEAT_CLICK_WEIGHT * repeat_click_score

        query_semantic_bonus = QUERY_VECTOR_WEIGHT * max(
            0.0, cosine_similarity(query_vector, doc_vector)
        )

        user_semantic_bonus = USER_VECTOR_WEIGHT * max(
            0.0, cosine_similarity(combined_user_vector, doc_vector)
        )

        final_score = (
            bm25
            + genre_bonus
            + author_bonus
            + book_bonus
            + click_bonus
            + query_semantic_bonus
            + user_semantic_bonus
        )

        reranked.append({
            "id": doc_id,
            "title": title,
            "author": book_author or "Unknown",
            "publication_date": src.get("publication_date"),
            "genres": book_genres,
            "summary": _truncate_summary(src.get("summary", "")),
            "full_summary": src.get("summary", ""),
            "es_score": round(bm25, 3),
            "final_score": round(final_score, 3),
            "genre_bonus": round(genre_bonus, 3),
            "author_bonus": round(author_bonus, 3),
            "book_bonus": round(book_bonus, 3),
            "click_bonus": round(click_bonus, 3),
            "query_semantic_bonus": round(query_semantic_bonus, 3),
            "user_semantic_bonus": round(user_semantic_bonus, 3),
            "explicit_share": round(explicit_share, 3),
            "click_share": round(click_share, 3),
        })

    reranked.sort(key=lambda doc: doc["final_score"], reverse=True)
    return reranked


def search_books(query: str, size: int = 10, user_id: str = "") -> list[dict]:
    personalized = bool((user_id or "").strip())

    retrieve_size = RETRIEVE_K if personalized else size
    body = _build_baseline_query(query_str=query, size=retrieve_size)

    response = connector.search(index=INDEX_NAME, body=body)
    hits = response["hits"]["hits"]

    if not personalized:
        return [_format_baseline_hit(hit) for hit in hits[:size]]

    profile = get_user_profile(user_id)
    reranked = _rerank_hits(hits, profile, query)
    return reranked[:size]


personalized_search = search_books