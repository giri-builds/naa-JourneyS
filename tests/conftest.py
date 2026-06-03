"""Shared pytest fixtures for the API test suite.

Run from project root:
    pip install -r requirements-dev.txt
    pytest tests/                       # run all
    pytest tests/test_chat_api.py -v    # one file
    pytest -k "rate_limit"              # match by name

Tests don't touch network or LLM APIs — RAG calls are mocked at module boundary.
"""
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'backend'))

from api import chat as chat_module  # noqa: E402
from api import health as health_module  # noqa: E402

ALLOWED_ORIGIN = 'http://localhost:4321'
DISALLOWED_ORIGIN = 'https://evil.example.com'


def _spawn_server(handler_cls):
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f'http://127.0.0.1:{server.server_address[1]}'


@pytest.fixture(scope='module')
def chat_url():
    server, url = _spawn_server(chat_module.handler)
    yield url
    server.shutdown()


@pytest.fixture(scope='module')
def health_url():
    server, url = _spawn_server(health_module.handler)
    yield url
    server.shutdown()


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear per-IP request log before every test."""
    chat_module._request_log.clear()
    yield
    chat_module._request_log.clear()


@pytest.fixture
def mock_rag(monkeypatch):
    """Patch retrieve_context and get_llm_provider with deterministic fakes."""
    fake_chunks = [
        {'text': 'Born in Chennavaram village.', 'metadata': {'title': 'Early Life', 'source': '01-early-life.md'}},
        {'text': 'Studied at govt school.', 'metadata': {'title': 'School', 'source': '02a-govt-school.md'}},
        {'text': 'Moved to Yerraguntla in 1998.', 'metadata': {'title': 'Early Life', 'source': '01-early-life.md'}},
    ]

    class FakeLLM:
        def generate(self, messages):
            return 'He was born in Chennavaram village.'

    monkeypatch.setattr(chat_module, 'retrieve_context', lambda q: fake_chunks)
    monkeypatch.setattr(chat_module, 'get_llm_provider', lambda: FakeLLM())
    return {'chunks': fake_chunks, 'answer': 'He was born in Chennavaram village.'}


@pytest.fixture
def mock_rag_timeout(monkeypatch):
    """Simulate an upstream LLM timeout."""
    class TimeoutLLM:
        def generate(self, messages):
            raise requests.Timeout('simulated upstream timeout')

    monkeypatch.setattr(chat_module, 'retrieve_context', lambda q: [])
    monkeypatch.setattr(chat_module, 'get_llm_provider', lambda: TimeoutLLM())


@pytest.fixture
def mock_rag_error(monkeypatch):
    """Simulate an unexpected internal error during RAG."""
    def boom(_):
        raise RuntimeError('internal stack secrets: /Users/secret/path key=sk-12345')

    monkeypatch.setattr(chat_module, 'retrieve_context', boom)


def post_chat(url, body, origin=ALLOWED_ORIGIN, ip='192.0.2.1', raw=False):
    """Helper: POST to /api/chat with origin + per-test fake IP."""
    headers = {
        'Content-Type': 'application/json',
        'Origin': origin,
        'X-Forwarded-For': ip,
    }
    data = body if raw else json.dumps(body)
    return requests.post(url, data=data, headers=headers, timeout=5)
