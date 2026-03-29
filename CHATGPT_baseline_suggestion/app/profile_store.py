from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
STOPWORDS = {
    "the", "and", "for", "are", "with", "that", "this", "from", "you", "your", "have",
    "has", "was", "will", "how", "what", "when", "where", "why", "who", "into", "their",
    "about", "using", "used", "than", "then", "them", "they", "been", "can", "not", "but",
    "get", "use", "our", "his", "her", "she", "him", "its", "out", "too", "all", "new",
    "one", "two", "top", "best", "more", "most", "over", "under", "after", "before", "also",
}


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    return [t for t in TOKEN_RE.findall(text) if t not in STOPWORDS]


def parse_ts(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", ""))
    except ValueError:
        return None


class UserProfileStore:
    def __init__(self, interactions_path: Path):
        self.interactions_path = interactions_path

    def load_interactions(self) -> list[dict[str, Any]]:
        if not self.interactions_path.exists():
            return []

        rows: list[dict[str, Any]] = []
        with self.interactions_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    def build_profile(self, user_id: str) -> dict[str, Any]:
        interactions = [r for r in self.load_interactions() if str(r.get("user_id")) == str(user_id)]

        term_weights: Counter[str] = Counter()
        domain_weights: Counter[str] = Counter()
        recent_queries: list[str] = []

        now = max((parse_ts(r.get("timestamp")) for r in interactions if r.get("timestamp")), default=None)

        for row in interactions:
            query = row.get("query", "")
            domain = row.get("clicked_domain")
            clicked = bool(row.get("clicked", False))
            ts = parse_ts(row.get("timestamp"))

            recency_weight = 1.0
            if now and ts:
                age_days = max((now - ts).days, 0)
                recency_weight = math.exp(-age_days / 30)

            for token in tokenize(query):
                term_weights[token] += 1.0 * recency_weight
                if clicked:
                    term_weights[token] += 1.0 * recency_weight

            if domain and clicked:
                domain_weights[domain.lower()] += 2.0 * recency_weight

            if query:
                recent_queries.append(query)

        return {
            "user_id": str(user_id),
            "top_terms": term_weights.most_common(12),
            "top_domains": domain_weights.most_common(8),
            "recent_queries": recent_queries[-8:],
            "term_weights": dict(term_weights),
            "domain_weights": dict(domain_weights),
            "num_interactions": len(interactions),
        }
