import json
import os
from http.server import BaseHTTPRequestHandler

from rag.retriever import retrieve_context
from rag.llm import get_llm_provider
from rag.prompt import build_rag_prompt


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(content_length))
        question = body.get('question', '').strip()

        if not question:
            self._respond(400, {'error': 'Question is required'})
            return

        try:
            context_chunks = retrieve_context(question)
            messages = build_rag_prompt(question, context_chunks)
            llm = get_llm_provider()
            answer = llm.generate(messages)

            sources = [chunk['metadata']['source'] for chunk in context_chunks]
            self._respond(200, {'answer': answer, 'sources': list(set(sources))})
        except Exception as e:
            self._respond(500, {'error': str(e)})

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def _respond(self, status, data):
        self.send_response(status)
        self._cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
