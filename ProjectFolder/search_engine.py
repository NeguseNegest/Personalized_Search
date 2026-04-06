from __future__ import annotations
from es_client import connector
from es_mappings import BOOKS_INDEX, PROFILES_INDEX, VECTOR_DIM

INDEX_NAME = BOOKS_INDEX

ALPHA = 1.0   # BM25 weight
BETA = 5.0    # semantic-vector weight
GAMMA = 3.0   # genre-preference weight



def _get_user_profile(user_id: str) -> dict | None:
    if not user_id:
        return None
    try:
        resp = connector.get(index=PROFILES_INDEX, id=user_id)
        return resp["_source"]
    except Exception:
        return None


def _get_user_profile_from_logs(user_id: str) -> dict | None:
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


def _build_personalized_query(
    query_str: str,
    interest_vector: list[float],
    preferred_genres: list[str],
    size: int,
) -> dict:
    script_source = """
        // --- BM25 component (α · _score) ---
        double bm25 = params.alpha * _score;

        // --- Semantic similarity component ---
        double vecSim = 0.0;
        if (doc['doc_vector'].size() > 0) {
            // cosineSimilarity returns [-1, 1]; +1 shifts to [0, 2]
            vecSim = params.beta * (1.0 + cosineSimilarity(params.qvec, 'doc_vector'));
        }

        // --- Genre overlap component ---
        double genreBonus = 0.0;
        if (params.pgenres.length > 0) {
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
                    },
                },
            }
        },
    }


def _build_baseline_query(query_str: str, size: int) -> dict:
    """Plain BM25 multi_match — used for anonymous users."""
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



def search_books(query: str, size: int = 10, user_id: str = "") -> list[dict]:
    # load user profile
    profile = _get_user_profile(user_id)
    if profile is None:
        profile = _get_user_profile_from_logs(user_id)

    personalized = False
    if profile is not None:
        interest_vector = profile.get("interest_vector", [0.0] * VECTOR_DIM)
        preferred_genres = profile.get("preferred_genres", [])

        has_vector = any(v != 0.0 for v in interest_vector)
        if has_vector or preferred_genres:
            personalized = True

    # run the appropriate query
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

    # format results
    results = []
    for hit in response["hits"]["hits"]:
        src = hit["_source"]
        summary = src.get("summary", "")
        if len(summary) > 500:
            summary = summary[:500] + "..."

        term_bonus = 0.0
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
            "term_bonus": term_bonus,
            "domain_bonus": domain_bonus,
        })

    return results


personalized_search = search_books
