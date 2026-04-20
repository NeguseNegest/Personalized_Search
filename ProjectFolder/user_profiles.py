from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from es_client import connector
from es_mappings import PROFILES_INDEX, PROFILES_SETTINGS
from embeddings_utils import encode_text

MAX_RECENT_QUERIES = 20


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def _canonical_key(value: str | None) -> str:
    """
    Canonical form used for matching / merging logically identical strings.

    Example:
      " George Orwell " -> "george orwell"
      "GEORGE  ORWELL"  -> "george orwell"
    """
    return _clean_text(value).casefold()


def _clean_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    if not values:
        return []

    cleaned: list[str] = []
    seen: set[str] = set()

    for raw in values:
        item = _clean_text(str(raw))
        if not item:
            continue

        key = item.casefold()
        if key in seen:
            continue

        seen.add(key)
        cleaned.append(item)

    return cleaned


def _merge_lists(old_values: list[str], new_values: list[str]) -> list[str]:
    return _clean_list((old_values or []) + (new_values or []))


def _normalize_count_map(counts: dict[str, Any] | None) -> dict[str, int]:
    """
    Merge legacy duplicate keys that differ only by case/spacing while keeping
    a readable display key for the UI.

    Example input:
      {
        "George Orwell": 2,
        "GEORGE ORWELL": 1,
        "George  Orwell": 3
      }

    Output:
      {
        "George Orwell": 6
      }
    """
    if not counts:
        return {}

    display_key_by_canonical: dict[str, str] = {}
    merged_counts: dict[str, int] = {}

    for raw_key, raw_value in counts.items():
        cleaned_key = _clean_text(str(raw_key))
        canonical = _canonical_key(cleaned_key)

        if not canonical:
            continue

        try:
            value = int(raw_value or 0)
        except (TypeError, ValueError):
            continue

        if value <= 0:
            continue

        if canonical not in display_key_by_canonical:
            display_key_by_canonical[canonical] = cleaned_key
            merged_counts[canonical] = 0

        merged_counts[canonical] += value

    return {
        display_key_by_canonical[canonical]: merged_counts[canonical]
        for canonical in display_key_by_canonical
    }


def _increment_normalized_count(counts: dict[str, int], raw_key: str) -> dict[str, int]:
    """
    Increment a count map while merging logically identical keys.

    This fixes issues like:
      "Science Fiction" vs "science fiction"
      "George Orwell" vs "GEORGE ORWELL"
    """
    normalized = _normalize_count_map(counts)

    cleaned_key = _clean_text(raw_key)
    canonical = _canonical_key(cleaned_key)

    if not canonical:
        return normalized

    for existing_key in list(normalized.keys()):
        if _canonical_key(existing_key) == canonical:
            normalized[existing_key] = int(normalized.get(existing_key, 0)) + 1
            return normalized

    normalized[cleaned_key] = 1
    return normalized


def build_explicit_profile_text(
    favorite_genres: list[str],
    favorite_authors: list[str],
    favorite_books: list[str],
    interests_text: str,
) -> str:
    parts: list[str] = []

    if favorite_genres:
        parts.append(f"Favorite genres: {', '.join(favorite_genres)}.")

    if favorite_authors:
        parts.append(f"Favorite authors: {', '.join(favorite_authors)}.")

    if favorite_books:
        parts.append(f"Books the user liked: {', '.join(favorite_books)}.")

    if interests_text:
        parts.append(f"Interests and hobbies: {interests_text}.")

    return " ".join(parts).strip()


def ensure_profiles_index() -> None:
    if not connector.indices.exists(index=PROFILES_INDEX):
        connector.indices.create(index=PROFILES_INDEX, body=PROFILES_SETTINGS)


def _default_profile(user_id: str) -> dict[str, Any]:
    now = _utc_now_iso()

    return {
        "user_id": user_id,
        "favorite_genres": [],
        "favorite_authors": [],
        "favorite_books": [],
        "interests_text": "",
        "explicit_profile_text": "",
        "clicked_doc_ids": {},
        "click_genre_counts": {},
        "click_author_counts": {},
        "recent_queries": [],
        "num_clicks": 0,
        "explicit_profile_completed": False,
        "created_at": now,
        "updated_at": now,
    }


def get_user_profile(user_id: str) -> dict[str, Any]:
    user_id = _clean_text(user_id)
    if not user_id:
        return _default_profile("")

    ensure_profiles_index()

    if connector.exists(index=PROFILES_INDEX, id=user_id):
        doc = connector.get(index=PROFILES_INDEX, id=user_id)
        src = doc.get("_source", {}) or {}

        merged = _default_profile(user_id)
        merged.update(src)
        merged["user_id"] = user_id

        # Normalize legacy maps on read so old stored data is still handled correctly.
        merged["click_genre_counts"] = _normalize_count_map(
            merged.get("click_genre_counts", {}) or {}
        )
        merged["click_author_counts"] = _normalize_count_map(
            merged.get("click_author_counts", {}) or {}
        )

        return merged

    return _default_profile(user_id)


def save_explicit_profile(
    user_id: str,
    favorite_genres: list[str] | None = None,
    favorite_authors: list[str] | None = None,
    favorite_books: list[str] | None = None,
    interests_text: str | None = None,
    merge: bool = False,
) -> dict[str, Any]:
    user_id = _clean_text(user_id)
    if not user_id:
        raise ValueError("user_id is required")

    ensure_profiles_index()

    profile = get_user_profile(user_id)

    new_genres = _clean_list(favorite_genres)
    new_authors = _clean_list(favorite_authors)
    new_books = _clean_list(favorite_books)
    new_interests = _clean_text(interests_text)

    if merge:
        final_genres = _merge_lists(profile.get("favorite_genres", []), new_genres)
        final_authors = _merge_lists(profile.get("favorite_authors", []), new_authors)
        final_books = _merge_lists(profile.get("favorite_books", []), new_books)

        old_interests = _clean_text(profile.get("interests_text", ""))
        if old_interests and new_interests:
            if old_interests.casefold() == new_interests.casefold():
                final_interests = old_interests
            else:
                final_interests = f"{old_interests}. {new_interests}"
        else:
            final_interests = old_interests or new_interests
    else:
        final_genres = new_genres
        final_authors = new_authors
        final_books = new_books
        final_interests = new_interests

    explicit_profile_text = build_explicit_profile_text(
        favorite_genres=final_genres,
        favorite_authors=final_authors,
        favorite_books=final_books,
        interests_text=final_interests,
    )

    explicit_profile_vector = (
        encode_text(explicit_profile_text) if explicit_profile_text else None
    )

    updated = {
        **profile,
        "user_id": user_id,
        "favorite_genres": final_genres,
        "favorite_authors": final_authors,
        "favorite_books": final_books,
        "interests_text": final_interests,
        "explicit_profile_text": explicit_profile_text,
        "explicit_profile_completed": bool(explicit_profile_text),
        "updated_at": _utc_now_iso(),
    }

    if explicit_profile_vector is not None:
        updated["explicit_profile_vector"] = explicit_profile_vector
    else:
        updated.pop("explicit_profile_vector", None)

    connector.index(
        index=PROFILES_INDEX,
        id=user_id,
        document=updated,
        refresh="wait_for",
    )

    return updated


def update_profile_from_click(
    user_id: str,
    query: str,
    doc_id: str,
    title: str = "",
    author: str = "",
    genres: list[str] | None = None,
) -> dict[str, Any]:
    user_id = _clean_text(user_id)
    query = _clean_text(query)
    doc_id = _clean_text(doc_id)
    author = _clean_text(author)
    genres = _clean_list(genres)

    if not user_id:
        raise ValueError("user_id is required")
    if not query:
        raise ValueError("query is required")
    if not doc_id:
        raise ValueError("doc_id is required")

    ensure_profiles_index()

    profile = get_user_profile(user_id)

    clicked_doc_ids = dict(profile.get("clicked_doc_ids", {}) or {})
    click_genre_counts = _normalize_count_map(profile.get("click_genre_counts", {}) or {})
    click_author_counts = _normalize_count_map(profile.get("click_author_counts", {}) or {})
    recent_queries = list(profile.get("recent_queries", []) or [])

    clicked_doc_ids[doc_id] = int(clicked_doc_ids.get(doc_id, 0) or 0) + 1

    for genre in genres:
        click_genre_counts = _increment_normalized_count(click_genre_counts, genre)

    if author:
        click_author_counts = _increment_normalized_count(click_author_counts, author)

    recent_queries = [q for q in recent_queries if q.casefold() != query.casefold()]
    recent_queries.insert(0, query)
    recent_queries = recent_queries[:MAX_RECENT_QUERIES]

    updated = {
        **profile,
        "user_id": user_id,
        "clicked_doc_ids": clicked_doc_ids,
        "click_genre_counts": click_genre_counts,
        "click_author_counts": click_author_counts,
        "recent_queries": recent_queries,
        "num_clicks": int(profile.get("num_clicks", 0) or 0) + 1,
        "updated_at": _utc_now_iso(),
    }

    updated.pop("explicit_profile_vector", None)
    if profile.get("explicit_profile_vector"):
        updated["explicit_profile_vector"] = profile["explicit_profile_vector"]

    connector.index(
        index=PROFILES_INDEX,
        id=user_id,
        document=updated,
        refresh="wait_for",
    )

    return updated