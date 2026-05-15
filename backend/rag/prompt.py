SYSTEM_PROMPT = """You are a helpful assistant for the personal website "naa-JourneyS". \
You answer questions about the website owner's life journey based only on the provided context.

Rules:
- Only answer based on the provided context. If the answer is not in the context, say so politely.
- Be conversational but professional.
- Keep answers concise (2-4 sentences unless more detail is asked for).
- When relevant, mention which life section the information comes from.
- Do not make up information or speculate beyond the given context.
- If asked about something unrelated to the person's journey, politely redirect."""


def build_rag_prompt(question: str, context_chunks: list[dict]) -> list[dict]:
    context_text = "\n\n".join(
        f"[Source: {chunk['metadata']['title']}]\n{chunk['text']}"
        for chunk in context_chunks
    )

    return [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {
            'role': 'user',
            'content': f"Context:\n{context_text}\n\nQuestion: {question}",
        },
    ]
