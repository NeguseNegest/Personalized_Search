from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / "elastic-start-local" / ".env"

load_dotenv(ENV_PATH)
ES_LOCAL_API_KEY = os.getenv("ES_LOCAL_API_KEY")
ES_URL = os.getenv("ES_LOCAL_URL", "http://localhost:9200")
#ES_USERNAME = os.getenv("ES_LOCAL_USERNAME")
ES_USERNAME = os.getenv("ES_LOCAL_USERNAME", "elastic")
ES_PASSWORD = os.getenv("ES_LOCAL_PASSWORD")
INDEX_NAME = os.getenv("APP_INDEX_NAME", "demo_personalized_docs")
INTERACTIONS_PATH = BASE_DIR / os.getenv("APP_INTERACTIONS_PATH", "data/sample_interactions.jsonl")

