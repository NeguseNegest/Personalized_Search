from flask import Flask, render_template, request, jsonify
from search_engine import search_books
from user_logs import log_click, get_user_profile

app = Flask(__name__,template_folder="Website")

@app.route("/", methods=["GET"])
def home():
    query = request.args.get("q", "").strip()
    user_id = request.args.get("user_id", "").strip()
    personalized = request.args.get("personalized") == "1"

    results = []
    error = None
    profile = None

    if query:
        try:
            results = search_books(query=query, size=10)
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
    query   = data.get("query", "").strip()
    doc_id  = data.get("doc_id", "").strip()

    if not (user_id and query and doc_id):
        return jsonify({"error": "user_id, query, and doc_id are required"}), 400
    
    print("LOG RECEIVED:", data)

    log_click(
        user_id=user_id,
        query=query,
        doc_id=doc_id,
        title=data.get("title", ""),
        author=data.get("author", ""),
        genres=data.get("genres", [])
    )
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True)