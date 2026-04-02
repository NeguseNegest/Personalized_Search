import json
from elasticsearch import Elasticsearch, helpers
from tqdm import tqdm
from config import ES_PASSWORD, ES_URL, ES_USERNAME
from connect import connector

INDEX_NAME = "booksummaries"
FILE_PATH = "ProjectFolder/Corpus/booksummaries.txt"


mapping = { 
    "mappings": {
        "properties": {
            "wikipedia_id": {"type": "keyword"},
            "freebase_id": {"type": "keyword"},
            "title": {
                "type": "text",
                "fields": {
                    "keyword": {"type": "keyword"}
                }
            },
            "author": {
                "type": "text",
                "fields": {
                    "keyword": {"type": "keyword"}
                }
            },
            "publication_date": {
                "type": "date",
                "format": "yyyy-MM-dd||strict_date_optional_time"
            },
            "genres": {
                "type": "text",
                "fields": {
                    "keyword": {"type": "keyword"}
                }
            },
            "summary": {"type": "text"}
        }
    }
}

def parse_line(line):
    parts = line.rstrip("\n").split("\t", 6)

    if len(parts) != 7:
        print("Observed malformed line with parts:", parts)
        return None

    wikipedia_id, freebase_id, title, author, publication_date, genres_raw, summary = parts

    try:
        genres_dict = json.loads(genres_raw)
        genres = list(genres_dict.values())
    except Exception:
        genres = []

    return {
        "wikipedia_id": wikipedia_id,
        "freebase_id": freebase_id,
        "title": title.strip(),
        "author": author.strip(),
        "publication_date": publication_date.strip() if publication_date.strip() else None,
        "genres": genres,
        "summary": summary.strip()
    }

def count_lines(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f)

def generate_actions(file_path):
    total_lines = count_lines(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(
            tqdm(f, total=total_lines, desc="Preparing documents"),
            start=1
        ):
            doc = parse_line(line)

            if doc is None:
                print(f"Skipping malformed line {line_number}")
                continue

            yield {
                "_index": INDEX_NAME,
                "_id": doc["wikipedia_id"],
                "_source": doc
            }

if __name__ == "__main__":
    if connector.indices.exists(index=INDEX_NAME):
        connector.indices.delete(index=INDEX_NAME)

    connector.indices.create(index=INDEX_NAME, body=mapping)
    print(f"Created index: {INDEX_NAME}")

    success, errors = helpers.bulk(
        connector,
        generate_actions(FILE_PATH),
        chunk_size=500 # number of documents sent to elasticsearch in each buld request 
    )

    print(f"Indexing complete. Indexed {success} documents.")

response = connector.search(
    index="booksummaries",
    query={
        "multi_match": {
            "query": "political satire farm revolution",
            "fields": ["title^3", "summary", "author^2", "genres"]
        }
    },
    size=10
)

for hit in response["hits"]["hits"]:
    print(hit["_score"], hit["_source"]["title"], hit["_source"]["author"])