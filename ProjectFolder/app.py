from flask import Flask, render_template, request
from search_engine import search_books

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

if __name__ == "__main__":
    app.run(debug=True)