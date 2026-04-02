from connect import connector
from indexer import INDEX_NAME


def search_books(query, size=10):
    response = connector.search(
        index=INDEX_NAME,
        query={
            "multi_match": {
                "query": query,
                "fields": ["title^3", "summary", "author^2", "genres"],
                "type": "best_fields"
            }
        },
        size=size
    )

    results = []
    for hit in response["hits"]["hits"]:
        src = hit["_source"]

        summary = src.get("summary", "")
        if len(summary) > 500:
            summary = summary[:500] + "..."

        results.append({
            "id": hit["_id"],
            "title": src.get("title", "Untitled"),
            "author": src.get("author", "Unknown"),
            "publication_date": src.get("publication_date"),
            "genres": src.get("genres", []),
            "summary": summary,
            "es_score": round(hit["_score"], 3),
            "final_score": round(hit["_score"], 3),   # same for now
            "term_bonus": 0.0,                        #  for later
            "domain_bonus": 0.0                       #  for later
        })

    return results


# TODO-add re - ranking based on user profile