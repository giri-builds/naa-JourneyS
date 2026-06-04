import json
import os
from http.server import BaseHTTPRequestHandler

ALLOWED_ORIGINS = {
    o.strip() for o in os.environ.get(
        'ALLOWED_ORIGINS',
        'https://giri-builds.github.io,http://localhost:4321,http://localhost:3000',
    ).split(',') if o.strip()
}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        origin = self.headers.get('Origin', '')
        self.send_response(200)
        self._cors_headers(origin)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'ok'}).encode())

    def do_OPTIONS(self):
        origin = self.headers.get('Origin', '')
        self.send_response(204)
        self._cors_headers(origin)
        self.end_headers()

    def _cors_headers(self, origin: str):
        if origin in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')
