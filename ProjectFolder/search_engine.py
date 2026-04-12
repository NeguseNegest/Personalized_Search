"""
Scoring formula :
    final_score = α · BM25(_score)
                + β · (1 + cosineSimilarity(doc_vector, interest_vector))
                + γ · genre_overlap_ratio

where:
    α = 1.0   — weight for lexical (BM25) relevance
    β = 5.0   — weight for semantic similarity between book and user interest
    γ = 3.0   — weight for genre preference overlap

Notes:
  - cosineSimilarity in ES returns [-1, 1].  Adding 1 → [0, 2], range [0, 2β].
  - genre_overlap_ratio ∈ [0, 1], contributing up to γ extra points.
  - If the user has no interest_vector (all zeros), only BM25 + genre bonus apply.
  - For anonymous / new users (no profile), falls back to pure BM25.

Compatibility:
  `search_books(query, size, user_id)` returns the same dict structure
  that `app.py` already consumes — the frontend needs zero changes.
"""
from __future__ import annotations
from es_client import connector
from es_mappings import BOOKS_INDEX, PROFILES_INDEX, VECTOR_DIM

INDEX_NAME = BOOKS_INDEX

# Weights (α, β, γ)
ALPHA = 1.0   # BM25 weight
BETA = 5.0    # semantic-vector weight
GAMMA = 3.0   # genre-preference weight


# Helper: fetch user profile

def _get_user_profile(user_id: str) -> dict | None:
    # Try the pre-computed user_profiles index first.
    if not user_id:
        return None
    try:
        resp = connector.get(index=PROFILES_INDEX, id=user_id)
        return resp["_source"]
    except Exception:
        return None


def _get_user_profile_from_logs(user_id: str) -> dict | None:
    # Fallback: aggregate preferred genres on-the-fly from user_logs.
    # Does NOT produce an interest_vector (that requires book vectors +
    # the embedding model), but still enables genre-based personalization.
    if not user_id:
        return None
    try:
        resp = connector.search(
            index="user_logs",
            query={"term": {"user_id": user_id}},
            size=0,
            aggs={
                "top_genres": {
                    "terms": {"field": "genres", "size": 20}
                }
            },
        )
        buckets = resp["aggregations"]["top_genres"]["buckets"]
        if not buckets:
            return None
        preferred = [b["key"] for b in buckets]
        return {
            "preferred_genres": preferred,
            "interest_vector": [0.0] * VECTOR_DIM,
        }
    except Exception:
        return None


# Query builders
def _build_personalized_query(
    query_str: str,
    interest_vector: list[float],
    preferred_genres: list[str],
    size: int,
) -> dict:
    # Construct a `script_score` query combining BM25 + vector + genre.
    # The Painless script checks whether the user vector is non-trivial before
    # calling cosineSimilarity, avoiding NaN from a zero-magnitude vector.
    script_source = """
        // ── BM25 component ──────────────────────────────────────────
        double bm25 = params.alpha * _score;

        // ── Semantic similarity component ───────────────────────────
        // Only compute cosine similarity if the user actually has a
        // real interest vector (skip if all-zeros to avoid NaN).
        double vecSim = 0.0;
        if (params.has_vec && doc.containsKey('doc_vector') && doc['doc_vector'].size() > 0) {
            vecSim = params.beta * (1.0 + cosineSimilarity(params.qvec, 'doc_vector'));
        }

        // ── Genre overlap component ─────────────────────────────────
        double genreBonus = 0.0;
        if (params.pgenres.length > 0 && doc.containsKey('genres.keyword') && doc['genres.keyword'].size() > 0) {
            int overlap = 0;
            for (String g : doc['genres.keyword']) {
                if (params.pgenres.contains(g)) {
                    overlap++;
                }
            }
            genreBonus = params.gamma * ((double) overlap / params.pgenres.length);
        }
        
        return bm25 + vecSim + genreBonus;
    """

    # Detect whether the interest_vector is meaningful (not all zeros)
    has_vec = any(v != 0.0 for v in interest_vector)

    return {
        "size": size,
        "query": {
            "script_score": {
                "query": {
                    "multi_match": {
                        "query": query_str,
                        "fields": ["title^3", "author^2", "summary", "genres"],
                        "type": "best_fields",
                    }
                },
                "script": {
                    "source": script_source,
                    "params": {
                        "alpha": ALPHA,
                        "beta": BETA,
                        "gamma": GAMMA,
                        "qvec": interest_vector,
                        "pgenres": preferred_genres,
                        "has_vec": has_vec,  # boolean flag for the script
                    },
                },
            }
        },
    }


def _build_baseline_query(query_str: str, size: int) -> dict:
    # Plain BM25 multi_match — used for anonymous users.
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


# Public API
def search_books(query: str, size: int = 10, user_id: str = "") -> list[dict]:
    """
    Search books with optional personalized re-ranking.
    Parameters
    ----------
    query    : the user's search string
    size     : number of results to return
    user_id  : if provided, triggers personalized scoring

    Returns
    -------
    List of result dicts with keys compatible with app.py / index.html:
        id, title, author, publication_date, genres, summary,
        es_score, final_score, term_bonus, domain_bonus
    """
    # Step 1: attempt to load user profile
    profile = _get_user_profile(user_id)
    if profile is None:
        profile = _get_user_profile_from_logs(user_id)

    personalized = False
    interest_vector = [0.0] * VECTOR_DIM
    preferred_genres = []

    if profile is not None:
        interest_vector = profile.get("interest_vector", [0.0] * VECTOR_DIM)
        preferred_genres = profile.get("preferred_genres", [])
        has_vector = any(v != 0.0 for v in interest_vector)
        if has_vector or preferred_genres:
            personalized = True

    # Step 2: run the appropriate query
    if personalized:
        body = _build_personalized_query(
            query_str=query,
            interest_vector=interest_vector,
            preferred_genres=preferred_genres,
            size=size,
        )
    else:
        body = _build_baseline_query(query_str=query, size=size)

    response = connector.search(index=INDEX_NAME, body=body)

    # Step 3: format results (same structure app.py expects)
    results = []
    for hit in response["hits"]["hits"]:
        src = hit["_source"]
        summary = src.get("summary", "")
        if len(summary) > 500:
            summary = summary[:500] + "..."

        # Estimate the genre bonus for display purposes
        domain_bonus = 0.0
        if personalized and preferred_genres:
            book_genres = set(src.get("genres", []))
            overlap = len(book_genres & set(preferred_genres))
            if overlap > 0:
                domain_bonus = round(
                    GAMMA * overlap / len(preferred_genres), 3
                )

        results.append({
            "id": hit["_id"],
            "title": src.get("title", "Untitled"),
            "author": src.get("author", "Unknown"),
            "publication_date": src.get("publication_date"),
            "genres": src.get("genres", []),
            "summary": summary,
            "es_score": round(hit["_score"], 3),
            "final_score": round(hit["_score"], 3),
            "term_bonus": 0.0,
            "domain_bonus": domain_bonus,
        })

    return results


# Convenience alias
personalized_search = search_books