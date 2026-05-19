# Stack Rules — naa-JourneyS

Personal life-journey site with a RAG chatbot. Keep these rules tight; they
calibrate severity for both review passes.

## Stack one-liner

Astro 5 + Tailwind 4 static frontend (deployed to GitHub Pages), Python 3.11
Vercel Serverless backend (`BaseHTTPRequestHandler` handlers), HuggingFace
embeddings + numpy cosine similarity, switchable LLM provider (Groq / Claude
/ OpenAI / Ollama). Zero npm deps in the review tooling itself — uses native
fetch + `npx -y tsx`.

## Forbidden patterns

- Hardcoded secrets in source. The repo uses `os.environ['GROQ_API_KEY']`,
  `os.environ['HF_API_KEY']`, `os.environ['ANTHROPIC_API_KEY']`,
  `os.environ['OPENAI_API_KEY']` — keys must come from env, never literals.
- Logging secrets, full request bodies, or full LLM prompts containing keys.
- Using `npm ci` in CI — the repo's lockfile is gitignored on purpose
  (Apple-network npm registry quirk). Workflows MUST use `npm install`.
- Committing a `frontend/package-lock.json` (gitignored — see `.gitignore`).
- Removing the `functions` block in `backend/vercel.json` or downgrading
  it to bare `api/*.py` zero-config / legacy `builds` — both fail to deploy
  Python functions on this Vercel project.
- `dangerouslySetInnerHTML` on LLM-generated content in `ChatWindow.tsx`
  without explicit sanitization (XSS via assistant output).
- Broadening CORS beyond the current `Access-Control-Allow-Origin: *` baseline
  to something *less* safe (e.g. `Access-Control-Allow-Credentials: true`
  combined with `*` is invalid; reflecting arbitrary origins without an
  allow-list is worse than the current wildcard).
- New public Vercel endpoints under `backend/api/` without thinking about
  rate limiting and input length caps. The chat endpoint is the only public
  surface; new ones expand the attack surface.
- Hardcoding `localhost` URLs in production frontend code. The chat widget
  reads `import.meta.env.PUBLIC_BACKEND_URL` (set as a GitHub Actions
  Variable, not a Secret). Don't bake URLs in.

## Required patterns

- Every Vercel handler subclasses `BaseHTTPRequestHandler` and exposes the
  class as `handler` (Vercel's Python runtime contract). See
  `backend/api/chat.py:10` and `backend/api/health.py:5`.
- Every POST handler validates the input (length, type) before passing it
  downstream. `backend/api/chat.py:18` rejects empty `question`; new
  endpoints should follow the same shape.
- Every handler that returns a response uses the `_respond(status, data)`
  + `_cors_headers()` helpers (or the equivalent — don't write raw
  `self.send_header` boilerplate inline if a helper exists in that file).
- LLM calls go through `get_llm_provider()` (`backend/rag/llm.py:112`).
  Don't import a provider class directly in route code.
- Frontend chat output renders as React text (escaped by default), not
  `dangerouslySetInnerHTML`. See `ChatWindow.tsx:85`.
- Astro config keeps `base: '/naa-JourneyS/'` — required for GitHub Pages
  to resolve assets. Don't delete or rename it.

## Naming conventions

- Python: snake_case for functions/variables, PascalCase for classes
  (`GroqProvider`, `ClaudeProvider`).
- TypeScript / React: camelCase for vars, PascalCase for components
  (`ChatWindow`, `Globe`, `Timeline`).
- Astro components: PascalCase `.astro` files in `frontend/src/components/`.
- Env vars: SCREAMING_SNAKE_CASE; public ones (read by the browser) are
  prefixed `PUBLIC_` per Astro convention (e.g. `PUBLIC_BACKEND_URL`).

## Anti-patterns specific to this stack

- **Vercel Python BaseHTTPRequestHandler edge case**: `do_POST` reads
  `Content-Length` then `self.rfile.read(...)`. Forgetting to handle
  `Content-Length: 0` (or missing header) → `int('') ValueError` → 500.
  See `backend/api/chat.py:12` for the correct pattern (`headers.get(...,
  0)`).
- **Astro 5 + React 19 islands**: client components must be loaded with
  `client:load` / `client:idle` / `client:visible`. A new React component
  added to a page without a client directive will render as static HTML
  with no interactivity. Flag missing `client:*` directives on interactive
  React components.
- **Tailwind 4 @import**: this project uses Tailwind v4 (`@tailwindcss/vite`,
  `tailwindcss: ^4.0.0`). v4 changed config syntax — do NOT recommend v3
  `tailwind.config.js` patterns.
- **HuggingFace inference router URL**: embeddings call hits
  `https://router.huggingface.co/hf-inference/models/...`. The legacy
  `api-inference.huggingface.co` host is deprecated for many models.
  Don't switch back to it.
- **Embeddings file commit**: `backend/data/embeddings.npy` and
  `chunks.json` ARE intentionally committed (see the comments in
  `.gitignore:24-26`) so Vercel deploys can read them at runtime. PRs
  removing them break production.
- **CI workflow auth on writes**: `index-content.yml` does
  `git push` after re-embedding — needs `permissions: contents: write`.
  Any new workflow that pushes back must also have that permission.

## Out-of-scope for review

- Changes purely under `frontend/src/content/journey/**.md` (life-journey
  text content, not code) — the loader filter already excludes `*.md`.
- Generated build artifacts in `frontend/dist/` (gitignored anyway).
- The `backend/data/*.npy` / `*.json` artifacts — these are produced by
  the indexer; review the indexer code, not the binary blobs.
