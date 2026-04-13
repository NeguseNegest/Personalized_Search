from __future__ import annotations

BOOKS_INDEX = "booksummaries"
LOGS_INDEX = "user_logs"
PROFILES_INDEX = "user_profiles"
VECTOR_DIM = 384

BOOKS_SETTINGS = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "index.mapping.exclude_source_vectors": False,
        "analysis": {
            "analyzer": {
                "english_custom": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "english_possessive_stemmer",
                        "english_stop",
                        "english_stemmer",
                    ],
                }
            },
            "filter": {
                "english_stop": {"type": "stop", "stopwords": "_english_"},
                "english_stemmer": {"type": "stemmer", "language": "english"},
                "english_possessive_stemmer": {
                    "type": "stemmer",
                    "language": "possessive_english",
                },
            },
        },
    },
    "mappings": {
        "properties": {
            "wikipedia_id": {"type": "keyword"},
            "freebase_id": {"type": "keyword"},
            "title": {
                "type": "text",
                "analyzer": "standard",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
            },
            "author": {
                "type": "text",
                "analyzer": "standard",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "publication_date": {
                "type": "date",
                "format": "yyyy-MM-dd||strict_date_optional_time",
            },
            "genres": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "summary": {
                "type": "text",
                "analyzer": "english_custom",
            },
            "doc_vector": {
                "type": "dense_vector",
                "dims": VECTOR_DIM,
                "index": True,
                "similarity": "cosine",
            },
        }
    },
}

LOGS_SETTINGS = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "user_id": {"type": "keyword"},
            "query": {"type": "text"},
            "doc_id": {"type": "keyword"},
            "title": {"type": "text"},
            "author": {"type": "keyword"},
            "genres": {"type": "keyword"},
            "timestamp": {"type": "date"},
        }
    },
}

PROFILES_SETTINGS = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "index.mapping.exclude_source_vectors": False,
        "analysis": {
            "analyzer": {
                "english_custom": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "english_possessive_stemmer",
                        "english_stop",
                        "english_stemmer",
                    ],
                }
            },
            "filter": {
                "english_stop": {"type": "stop", "stopwords": "_english_"},
                "english_stemmer": {"type": "stemmer", "language": "english"},
                "english_possessive_stemmer": {
                    "type": "stemmer",
                    "language": "possessive_english",
                },
            },
        },
    },
    "mappings": {
        "properties": {
            "user_id": {"type": "keyword"},

            "favorite_genres": {"type": "keyword"},
            "favorite_authors": {"type": "keyword"},
            "favorite_books": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
            },
            "interests_text": {
                "type": "text",
                "analyzer": "english_custom",
            },

            "explicit_profile_text": {
                "type": "text",
                "analyzer": "english_custom",
            },
            "explicit_profile_vector": {
                "type": "dense_vector",
                "dims": VECTOR_DIM,
                "index": True,
                "similarity": "cosine",
            },

            "clicked_doc_ids": {
                "type": "object",
                "enabled": False,
            },
            "click_genre_counts": {
                "type": "object",
                "enabled": False,
            },
            "click_author_counts": {
                "type": "object",
                "enabled": False,
            },

            "recent_queries": {"type": "keyword"},
            "num_clicks": {"type": "integer"},
            "explicit_profile_completed": {"type": "boolean"},

            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        }
    },
}