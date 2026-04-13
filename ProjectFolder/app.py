from flask import Flask, render_template, request, jsonify
from search_engine import search_books
from user_logs import log_click, get_user_profile

app = Flask(__name__, template_folder="Website")


def build_profile_view(user_id: str) -> dict | None:
    if not user_id:
        return None

    raw = get_user_profile(user_id)
    total_interactions = sum(raw.get("clicked_doc_ids", {}).values())

    if total_interactions == 0:
        return None

    top_genres = sorted(
        raw.get("genre_counts", {}).items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]

    top_authors = sorted(
        raw.get("author_counts", {}).items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]

    return {
        "num_interactions": total_interactions,
        "top_genres": top_genres,
        "top_authors": top_authors,
        "recent_queries": raw.get("recent_queries", [])[:5],
    }


@app.route("/", methods=["GET"])
def home():
    query = request.args.get("q", "").strip()
    user_id = request.args.get("user_id", "").strip()
    personalized = request.args.get("personalized") == "1"

    results = []
    error = None
    profile = build_profile_view(user_id) if (user_id and personalized) else None

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
        error=error
    )

@app.route("/log", methods=["POST"])
def log():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "").strip()
    query = data.get("query", "").strip()
    doc_id = data.get("doc_id", "").strip()

    if not (user_id and query and doc_id):
        return jsonify({"error": "user_id, query, and doc_id are required"}), 400

    print("LOG RECEIVED:", data)

    log_click(
        user_id=user_id,
        query=query,
        doc_id=doc_id,
        title=data.get("title", ""),
        author=data.get("author", ""),
        genres=data.get("genres", []),
    )
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)