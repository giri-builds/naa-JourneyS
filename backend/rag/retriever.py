import numpy as np
from .embeddings import get_embedding, load_chunks, load_embeddings, cosine_similarity

TOP_K = 5


def retrieve_context(question: str) -> list[dict]:
    query_embedding = np.array(get_embedding(question), dtype=np.float32)
    chunks = load_chunks()
    embeddings = load_embeddings()

    similarities = cosine_similarity(query_embedding, embeddings)
    top_indices = np.argsort(similarities.flatten())[::-1][:TOP_K]

    return [chunks[i] for i in top_indices]
