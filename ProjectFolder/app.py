from __future__ import annotations

from flask import Flask, render_template, request, jsonify, redirect, url_for

from search_engine import search_books
from user_logs import log_click
from user_profiles import (
    get_user_profile,
    save_explicit_profile,
    update_profile_from_click,
)

app = Flask(__name__, template_folder="Website")


def _split_multivalue_field(value: str) -> list[str]:
    """
    Accept comma-separated and/or newline-separated user input.
    Example:
      fantasy, horror
      mystery
    """
    if not value:
        return []

    items: list[str] = []
    seen: set[str] = set()

    normalized = value.replace("\r", "\n")
    for chunk in normalized.split("\n"):
        for piece in chunk.split(","):
            cleaned = " ".join(piece.strip().split())
            if not cleaned:
                continue

            key = cleaned.casefold()
            if key in seen:
                continue

            seen.add(key)
            items.append(cleaned)

    return items


def build_profile_view(user_id: str) -> dict | None:
    user_id = (user_id or "").strip()
    if not user_id:
        return None

    raw = get_user_profile(user_id)
    if not raw.get("user_id"):
        return None

    click_genres = sorted(
        (raw.get("click_genre_counts") or {}).items(),
        key=lambda x: x[1],
        reverse=True,
    )[:5]

    click_authors = sorted(
        (raw.get("click_author_counts") or {}).items(),
        key=lambda x: x[1],
        reverse=True,
    )[:5]

    return {
        "user_id": raw.get("user_id", ""),
        "num_clicks": int(raw.get("num_clicks", 0) or 0),
        "favorite_genres": raw.get("favorite_genres", []),
        "favorite_authors": raw.get("favorite_authors", []),
        "favorite_books": raw.get("favorite_books", []),
        "interests_text": raw.get("interests_text", ""),
        "recent_queries": raw.get("recent_queries", [])[:5],
        "top_click_genres": click_genres,
        "top_click_authors": click_authors,
        "explicit_profile_completed": bool(raw.get("explicit_profile_completed", False)),
    }


@app.route("/", methods=["GET"])
def home():
    query = request.args.get("q", "").strip()
    user_id = request.args.get("user_id", "").strip()
    personalized = request.args.get("personalized") == "1"
    profile_saved = request.args.get("profile_saved") == "1"

    results = []
    error = None
    profile = build_profile_view(user_id) if user_id else None

    effective_user_id = user_id if personalized else ""

    if query:
        try:
            results = search_books(query=query, size=50, user_id=effective_user_id)
        except Exception as e:
            error = str(e)

    return render_template(
        "index.html",
        query=query,
        user_id=user_id,
        personalized=personalized,
        results=results,
        profile=profile,
        profile_saved=profile_saved,
        error=error,
    )


@app.route("/profile", methods=["POST"])
def save_profile():
    user_id = request.form.get("user_id", "").strip()
    query = request.form.get("q", "").strip()
    personalized = request.form.get("personalized") == "1"

    if not user_id:
        return redirect(
            url_for(
                "home",
                q=query,
                personalized="1" if personalized else None,
            )
        )

    favorite_genres = _split_multivalue_field(request.form.get("favorite_genres", ""))
    favorite_authors = _split_multivalue_field(request.form.get("favorite_authors", ""))
    favorite_books = _split_multivalue_field(request.form.get("favorite_books", ""))
    interests_text = request.form.get("interests_text", "").strip()

    merge_mode = request.form.get("profile_mode", "merge") == "merge"

    save_explicit_profile(
        user_id=user_id,
        favorite_genres=favorite_genres,
        favorite_authors=favorite_authors,
        favorite_books=favorite_books,
        interests_text=interests_text,
        merge=merge_mode,
    )

    return redirect(
        url_for(
            "home",
            q=query,
            user_id=user_id,
            personalized="1" if personalized else None,
            profile_saved="1",
        )
    )


@app.route("/log", methods=["POST"])
def log():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "").strip()
    query = data.get("query", "").strip()
    doc_id = data.get("doc_id", "").strip()

    if not (user_id and query and doc_id):
        return jsonify({"error": "user_id, query, and doc_id are required"}), 400

    title = data.get("title", "")
    author = data.get("author", "")
    genres = data.get("genres", []) or []

    log_click(
        user_id=user_id,
        query=query,
        doc_id=doc_id,
        title=title,
        author=author,
        genres=genres,
    )

    update_profile_from_click(
        user_id=user_id,
        query=query,
        doc_id=doc_id,
        title=title,
        author=author,
        genres=genres,
    )

    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)