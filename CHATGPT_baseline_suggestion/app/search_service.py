from __future__ import annotations

from typing import Any

from app.config import INDEX_NAME, INTERACTIONS_PATH
from app.es_client import get_es_client
from app.profile_store import UserProfileStore, tokenize

TERM_BONUS_WEIGHT = 0.20
DOMAIN_BONUS_WEIGHT = 0.75


class SearchService:
    def __init__(self):
        self.es = get_es_client()
        self.profile_store = UserProfileStore(INTERACTIONS_PATH)

    def retrieve(self, query: str, size: int = 10) -> list[dict[str, Any]]:
        response = self.es.search(
            index=INDEX_NAME,
            size=size,
            query={
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "content", "topics^2", "domain"],
                }
            },
        )
        return response["hits"]["hits"]

    def rerank(self, query: str, user_id: str, size: int = 10) -> dict[str, Any]:
        hits = self.retrieve(query=query, size=size)
        profile = self.profile_store.build_profile(user_id)
        term_weights = profile["term_weights"]
        domain_weights = profile["domain_weights"]

        reranked: list[dict[str, Any]] = []
        for hit in hits:
            source = hit["_source"]
            es_score = float(hit.get("_score", 0.0))
            doc_text = " ".join([
                source.get("title", ""),
                source.get("content", ""),
                " ".join(source.get("topics", [])),
            ])
            doc_terms = set(tokenize(doc_text))
            doc_domain = (source.get("domain") or "").lower()

            raw_term_bonus = sum(term_weights.get(t, 0.0) for t in doc_terms)
            raw_domain_bonus = domain_weights.get(doc_domain, 0.0)

            term_bonus = TERM_BONUS_WEIGHT * raw_term_bonus
            domain_bonus = DOMAIN_BONUS_WEIGHT * raw_domain_bonus
            final_score = es_score + term_bonus + domain_bonus

            reranked.append(
                {
                    "id": hit["_id"],
                    "title": source.get("title"),
                    "content": source.get("content"),
                    "url": source.get("url"),
                    "domain": source.get("domain"),
                    "topics": source.get("topics", []),
                    "es_score": round(es_score, 4),
                    "term_bonus": round(term_bonus, 4),
                    "domain_bonus": round(domain_bonus, 4),
                    "final_score": round(final_score, 4),
                }
            )

        reranked.sort(key=lambda x: x["final_score"], reverse=True)
        return {"profile": profile, "results": reranked}
