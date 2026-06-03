import json
import logging
import os
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler

from rag.retriever import retrieve_context
from rag.llm import get_llm_provider
from rag.prompt import build_rag_prompt

logger = logging.getLogger(__name__)

MAX_QUESTION_LEN = int(os.environ.get('MAX_QUESTION_LEN', '500'))
MAX_BODY_BYTES = int(os.environ.get('MAX_BODY_BYTES', '4096'))
RATE_LIMIT_REQUESTS = int(os.environ.get('RATE_LIMIT_REQUESTS', '20'))
RATE_LIMIT_WINDOW_SEC = int(os.environ.get('RATE_LIMIT_WINDOW_SEC', '60'))

ALLOWED_ORIGINS = {
    o.strip() for o in os.environ.get(
        'ALLOWED_ORIGINS',
        'https://giri-builds.github.io,http://localhost:4321,http://localhost:3000',
    ).split(',') if o.strip()
}

# Per-instance sliding window. Vercel reuses warm instances so this catches
# bursty abuse, but it is NOT a global limit. For strict cross-instance
# enforcement, swap with Upstash Redis (@upstash/ratelimit) keyed by IP.
_MAX_TRACKED_IPS = 10_000
_request_log: dict[str, deque] = defaultdict(deque)


def _client_ip(headers) -> str:
    forwarded = headers.get('x-forwarded-for', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return headers.get('x-real-ip', 'unknown')


def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SEC

    if len(_request_log) > _MAX_TRACKED_IPS:
        for stale_ip in [k for k, v in _request_log.items() if not v or v[-1] < window_start]:
            _request_log.pop(stale_ip, None)

    timestamps = _request_log[ip]
    while timestamps and timestamps[0] < window_start:
        timestamps.popleft()
    if len(timestamps) >= RATE_LIMIT_REQUESTS:
        return True
    timestamps.append(now)
    return False


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        origin = self.headers.get('Origin', '')
        ip = _client_ip(self.headers)

        if _is_rate_limited(ip):
            self._respond(429, {'error': 'Too many requests. Please slow down.'}, origin)
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
        except ValueError:
            self._respond(400, {'error': 'Invalid request'}, origin)
            return

        if content_length <= 0 or content_length > MAX_BODY_BYTES:
            self._respond(413, {'error': 'Request body too large'}, origin)
            return

        try:
            body = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._respond(400, {'error': 'Invalid JSON'}, origin)
            return

        question = (body.get('question') or '').strip() if isinstance(body, dict) else ''

        if not question:
            self._respond(400, {'error': 'Question is required'}, origin)
            return

        if len(question) > MAX_QUESTION_LEN:
            self._respond(
                400,
                {'error': f'Question must be {MAX_QUESTION_LEN} characters or fewer'},
                origin,
            )
            return

        try:
            context_chunks = retrieve_context(question)
            messages = build_rag_prompt(question, context_chunks)
            llm = get_llm_provider()
            answer = llm.generate(messages)

            sources = list({chunk['metadata']['source'] for chunk in context_chunks})
            self._respond(200, {'answer': answer, 'sources': sources}, origin)
        except Exception:
            logger.exception('chat handler failed')
            self._respond(500, {'error': 'Internal server error'}, origin)

    def do_OPTIONS(self):
        origin = self.headers.get('Origin', '')
        self.send_response(204)
        self._cors_headers(origin)
        self.end_headers()

    def _respond(self, status, data, origin=''):
        self.send_response(status)
        self._cors_headers(origin)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _cors_headers(self, origin: str):
        if origin in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')
