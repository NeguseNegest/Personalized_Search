import os
from elasticsearch import Elasticsearch

def get_client() -> Elasticsearch:
    url = os.environ["ES_LOCAL_URL"]
    api_key = os.environ["ES_LOCAL_API_KEY"]

    client = Elasticsearch(
        url,
        api_key=api_key,
    )
    return client

if __name__ == "__main__":
    client = get_client()
    print(client.info())