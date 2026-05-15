# naa-JourneyS

A personal life-journey website with an AI-powered chatbot that answers questions about my life story using Retrieval-Augmented Generation (RAG).

## Architecture

```
GitHub Pages (Astro + Tailwind)  →  Vercel Serverless (Python RAG API)
                                         │
                                    ┌────┴────┐
                                    │ FAISS   │  ← pre-built embeddings
                                    │ Search  │
                                    └────┬────┘
                                         │
                                    ┌────┴────┐
                                    │ Groq    │  ← LLM (switchable)
                                    │ LLM     │
                                    └─────────┘
```

## Tech Stack

- **Frontend**: Astro 5, Tailwind CSS 4, React (chat widget)
- **Backend**: Vercel Serverless (Python)
- **LLM**: Groq (Llama 3.3 70B) — switchable to Claude, OpenAI, or Ollama
- **Embeddings**: HuggingFace Inference API (all-MiniLM-L6-v2)
- **Vector Search**: NumPy cosine similarity on pre-computed embeddings
- **CI/CD**: GitHub Actions → GitHub Pages + Vercel auto-deploy

## Quick Start

### Frontend
```bash
cd frontend
npm install
npm run dev          # localhost:4321
```

### Backend (local)
```bash
cd backend
pip install -r requirements.txt
cp ../.env.example .env   # Fill in API keys
vercel dev               # localhost:3000
```

### Index Content
```bash
export HF_API_KEY=your_key
python scripts/index_content.py
```

### Test RAG Pipeline
```bash
export GROQ_API_KEY=your_key
export HF_API_KEY=your_key
python scripts/test_rag.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_PROVIDER` | Yes | `groq` (default), `claude`, `openai`, `ollama` |
| `GROQ_API_KEY` | Yes* | Groq API key (free at console.groq.com) |
| `HF_API_KEY` | Yes | HuggingFace token for embeddings |
| `ANTHROPIC_API_KEY` | No | For Claude provider |
| `OPENAI_API_KEY` | No | For OpenAI provider |

## Project Structure

```
├── frontend/          Astro static site (GitHub Pages)
├── backend/           Python RAG API (Vercel Serverless)
│   ├── api/           HTTP endpoints
│   ├── rag/           RAG pipeline (embeddings, retrieval, LLM, prompts)
│   └── data/          Pre-built chunks + embeddings
├── scripts/           Content indexing + testing
└── .github/workflows/ CI/CD automation
```

## How the RAG Works

1. **Indexing** (build time): Markdown content → chunked → embedded → saved as numpy array
2. **Query** (runtime): User question → embedded → cosine similarity search → top-5 chunks retrieved
3. **Generation**: Retrieved context + question → LLM prompt → answer with citations

## License

MIT
