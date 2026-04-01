import os
from elasticsearch import Elasticsearch
from config import ES_URL,ES_LOCAL_API_KEY

#print(ES_URL,ES_LOCAL_API_KEY)

def get_client() -> Elasticsearch:
    # url = os.environ["ES_LOCAL_URL"]
    # api_key = os.environ["ES_LOCAL_API_KEY"]
    url=ES_URL
    api_key=ES_LOCAL_API_KEY

    client = Elasticsearch(
        url,
        api_key=api_key,
    )
    return client

if __name__ == "__main__":
    client = get_client()
    print(client.info())