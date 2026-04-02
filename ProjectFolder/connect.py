from elasticsearch import Elasticsearch
from config import ES_URL, ES_USERNAME, ES_PASSWORD

connector = Elasticsearch(
    ES_URL,
    basic_auth=(ES_USERNAME, ES_PASSWORD),
    request_timeout=30
)