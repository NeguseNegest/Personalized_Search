from __future__ import annotations

from flask import Flask, render_template, request

from app.search_service import SearchService

app = Flask(__name__)
service = SearchService()


@app.route("/", methods=["GET"])
def index():
    query = request.args.get("q", "")
    user_id = request.args.get("user_id", "1001")
    personalized = request.args.get("personalized", "1") == "1"

    profile = None
    results = []
    error = None

    if query:
        try:
            if personalized:
                payload = service.rerank(query=query, user_id=user_id, size=10)
                profile = payload["profile"]
                results = payload["results"]
            else:
                raw_hits = service.retrieve(query=query, size=10)
                results = [
                    {
                        "id": h["_id"],
                        "title": h["_source"].get("title"),
                        "content": h["_source"].get("content"),
                        "url": h["_source"].get("url"),
                        "domain": h["_source"].get("domain"),
                        "topics": h["_source"].get("topics", []),
                        "es_score": round(float(h.get("_score", 0.0)), 4),
                        "term_bonus": 0.0,
                        "domain_bonus": 0.0,
                        "final_score": round(float(h.get("_score", 0.0)), 4),
                    }
                    for h in raw_hits
                ]
        except Exception as exc:  # pragma: no cover - debug-friendly error display
            error = str(exc)

    return render_template(
        "index.html",
        query=query,
        user_id=user_id,
        personalized=personalized,
        profile=profile,
        results=results,
        error=error,
    )
