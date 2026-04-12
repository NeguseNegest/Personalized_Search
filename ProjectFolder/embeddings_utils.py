from __future__ import annotations

from functools import lru_cache
import numpy as np

EMBEDDING_DIM = 384
MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)


def encode_text(text: str) -> list[float]:
    """
    Encode a single text into a normalized embedding vector.
    """
    text = (text or "").strip()
    if not text:
        return [0.0] * EMBEDDING_DIM

    model = get_model()
    vec = model.encode(
        text,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return np.asarray(vec, dtype=float).tolist()


def encode_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """
    Encode multiple texts at once for much better throughput.
    The outputs are normalized embeddings, just like encode_text().
    """
    if not texts:
        return []

    cleaned_texts = [(text or "").strip() for text in texts]

    model = get_model()
    vectors = model.encode(
        cleaned_texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    vectors = np.asarray(vectors, dtype=float)

    result: list[list[float]] = []
    for text, vec in zip(cleaned_texts, vectors):
        if not text:
            result.append([0.0] * EMBEDDING_DIM)
        else:
            result.append(vec.tolist())

    return result


def normalize_vector(vec: list[float]) -> list[float]:
    if not vec:
        return [0.0] * EMBEDDING_DIM

    arr = np.array(vec, dtype=float)
    norm = np.linalg.norm(arr)
    if norm == 0.0:
        return [0.0] * EMBEDDING_DIM

    return (arr / norm).tolist()


def weighted_average_vectors(vectors: list[list[float]], weights: list[float]) -> list[float]:
    if not vectors or not weights or len(vectors) != len(weights):
        return [0.0] * EMBEDDING_DIM

    mat = np.array(vectors, dtype=float)
    w = np.array(weights, dtype=float)

    if w.sum() == 0.0:
        return [0.0] * EMBEDDING_DIM

    avg = np.average(mat, axis=0, weights=w)
    return normalize_vector(avg.tolist())


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0

    a = np.array(vec_a, dtype=float)
    b = np.array(vec_b, dtype=float)

    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))