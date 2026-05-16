"""
Content indexing script.
Reads markdown files from frontend/src/content/journey/,
chunks them, computes embeddings, and saves to backend/data/.
"""
import os
import re
import json
import time
import requests
import numpy as np

CONTENT_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'src', 'content', 'journey')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'backend', 'data')
HF_API_KEY = os.environ.get('HF_API_KEY', '')
EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def parse_frontmatter(content: str) -> tuple[dict, str]:
    match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
    if not match:
        return {}, content
    frontmatter = {}
    for line in match.group(1).split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            frontmatter[key.strip()] = value.strip().strip('"\'')
    return frontmatter, match.group(2)


def chunk_text(text: str, metadata: dict) -> list[dict]:
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks = []
    current_chunk = ''

    for para in paragraphs:
        if para.startswith('#'):
            if current_chunk:
                chunks.append({'text': current_chunk.strip(), 'metadata': metadata})
                current_chunk = ''
            current_chunk = para + '\n\n'
        elif len(current_chunk) + len(para) > CHUNK_SIZE:
            if current_chunk:
                chunks.append({'text': current_chunk.strip(), 'metadata': metadata})
            current_chunk = para + '\n\n'
        else:
            current_chunk += para + '\n\n'

    if current_chunk.strip():
        chunks.append({'text': current_chunk.strip(), 'metadata': metadata})

    return chunks


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    response = requests.post(
        f'https://router.huggingface.co/hf-inference/models/{EMBEDDING_MODEL}/pipeline/feature-extraction',
        headers={'Authorization': f'Bearer {HF_API_KEY}'},
        json={'inputs': texts, 'options': {'wait_for_model': True}},
    )
    if response.status_code == 503:
        print('  Model loading, waiting 20s...')
        time.sleep(20)
        return get_embeddings_batch(texts)
    response.raise_for_status()
    return response.json()


def main():
    print('=== naa-JourneyS Content Indexer ===\n')
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_chunks = []
    md_files = sorted(f for f in os.listdir(CONTENT_DIR) if f.endswith('.md'))

    for filename in md_files:
        filepath = os.path.join(CONTENT_DIR, filename)
        with open(filepath) as f:
            content = f.read()

        frontmatter, body = parse_frontmatter(content)
        metadata = {
            'source': filename,
            'title': frontmatter.get('title', filename),
            'dateRange': frontmatter.get('dateRange', ''),
            'category': frontmatter.get('category', ''),
        }

        chunks = chunk_text(body, metadata)
        all_chunks.extend(chunks)
        print(f'  {filename}: {len(chunks)} chunks')

    print(f'\nTotal chunks: {len(all_chunks)}')

    # Compute embeddings
    print('\nComputing embeddings...')
    texts = [chunk['text'] for chunk in all_chunks]
    batch_size = 32
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = get_embeddings_batch(batch)
        all_embeddings.extend(embeddings)
        print(f'  Batch {i // batch_size + 1}/{(len(texts) - 1) // batch_size + 1} done')

    # Save outputs
    chunks_path = os.path.join(OUTPUT_DIR, 'chunks.json')
    with open(chunks_path, 'w') as f:
        json.dump(all_chunks, f, indent=2)
    print(f'\nSaved chunks to {chunks_path}')

    embeddings_path = os.path.join(OUTPUT_DIR, 'embeddings.npy')
    np.save(embeddings_path, np.array(all_embeddings, dtype=np.float32))
    print(f'Saved embeddings to {embeddings_path}')

    print('\nDone!')


if __name__ == '__main__':
    main()
