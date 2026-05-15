import os
import json
import numpy as np
import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')


def get_embedding(text: str) -> list[float]:
    api_key = os.environ.get('HF_API_KEY', '')
    model = 'sentence-transformers/all-MiniLM-L6-v2'
    response = requests.post(
        f'https://api-inference.huggingface.co/pipeline/feature-extraction/{model}',
        headers={'Authorization': f'Bearer {api_key}'},
        json={'inputs': text, 'options': {'wait_for_model': True}},
    )
    response.raise_for_status()
    return response.json()


def load_chunks() -> list[dict]:
    chunks_path = os.path.join(DATA_DIR, 'chunks.json')
    with open(chunks_path) as f:
        return json.load(f)


def load_embeddings() -> np.ndarray:
    embeddings_path = os.path.join(DATA_DIR, 'embeddings.npy')
    return np.load(embeddings_path)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = a / np.linalg.norm(a)
    b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
    return b_norm @ a_norm
