"""Quick local test for the RAG pipeline."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from rag.retriever import retrieve_context
from rag.llm import get_llm_provider
from rag.prompt import build_rag_prompt


def test_query(question: str):
    print(f'\nQ: {question}')
    print('-' * 40)

    chunks = retrieve_context(question)
    print(f'Retrieved {len(chunks)} chunks:')
    for chunk in chunks:
        print(f"  - [{chunk['metadata']['title']}] {chunk['text'][:80]}...")

    messages = build_rag_prompt(question, chunks)
    llm = get_llm_provider()
    answer = llm.generate(messages)
    print(f'\nA: {answer}')


if __name__ == '__main__':
    questions = [
        "When was he born?",
        "Where did he complete his graduation?",
        "What is his work experience?",
    ]
    for q in questions:
        test_query(q)
        print()
