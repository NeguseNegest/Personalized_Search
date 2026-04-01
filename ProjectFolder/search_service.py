from elasticsearch import Elasticsearch
from config import ES_URL, ES_USERNAME, ES_PASSWORD

connector = Elasticsearch(
    ES_URL,
    basic_auth=(ES_USERNAME, ES_PASSWORD),
    request_timeout=30
)

INDEX_NAME = "booksummaries"

def search_books(query, genre=None, author=None, size=10, from_=0):
    must = []
    filters = []

    if query:
        must.append({
            "multi_match": {
                "query": query,
                "fields": ["title^4", "summary", "author^2", "genres", "combined_text"]
            }
        })

    if genre:
        filters.append({"term": {"genres.keyword": genre}})

    if author:
        filters.append({"term": {"author.keyword": author}})

    body = {
        "query": {
            "bool": {
                "must": must if must else [{"match_all": {}}],
                "filter": filters
            }
        },
        "highlight": {
            "fields": {
                "summary": {},
                "title": {}
            }
        },
        "from": from_,
        "size": size
    }

    return connector.search(index=INDEX_NAME, body=body)

def get_book_by_id(book_id):
    return connector.get(index=INDEX_NAME, id=book_id)