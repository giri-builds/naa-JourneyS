"""Tests for /api/chat — the public RAG endpoint.

Covers: happy path, input validation, rate limiting, CORS, error handling.
"""
import json

import pytest
import requests

from tests.conftest import (
    ALLOWED_ORIGIN,
    DISALLOWED_ORIGIN,
    post_chat,
)


# ---------- Happy path ----------

class TestHappyPath:
    def test_post_returns_200_with_answer_and_sources(self, chat_url, mock_rag):
        r = post_chat(chat_url, {'question': 'Where was he born?'})
        assert r.status_code == 200
        data = r.json()
        assert data['answer'] == mock_rag['answer']
        assert set(data['sources']) == {'01-early-life.md', '02a-govt-school.md'}

    def test_sources_are_deduplicated(self, chat_url, mock_rag):
        r = post_chat(chat_url, {'question': 'anything'})
        sources = r.json()['sources']
        assert len(sources) == len(set(sources))


# ---------- Input validation ----------

class TestInputValidation:
    def test_empty_body_returns_413(self, chat_url, mock_rag):
        r = post_chat(chat_url, '', raw=True)
        assert r.status_code == 413

    def test_missing_question_field_returns_400(self, chat_url, mock_rag):
        r = post_chat(chat_url, {})
        assert r.status_code == 400
        assert 'required' in r.json()['error'].lower()

    def test_empty_question_returns_400(self, chat_url, mock_rag):
        r = post_chat(chat_url, {'question': '   '})
        assert r.status_code == 400

    def test_question_over_length_cap_returns_400(self, chat_url, mock_rag):
        r = post_chat(chat_url, {'question': 'x' * 600})
        assert r.status_code == 400
        assert 'characters' in r.json()['error']

    def test_invalid_json_returns_400(self, chat_url, mock_rag):
        r = post_chat(chat_url, 'not json {{', raw=True)
        assert r.status_code == 400

    def test_oversized_body_returns_413(self, chat_url, mock_rag, monkeypatch):
        from api import chat as chat_module
        monkeypatch.setattr(chat_module, 'MAX_BODY_BYTES', 100)
        big_body = json.dumps({'question': 'x' * 200})
        r = post_chat(chat_url, big_body, raw=True)
        assert r.status_code == 413


# ---------- Rate limiting ----------

class TestRateLimiting:
    def test_under_limit_succeeds(self, chat_url, mock_rag, monkeypatch):
        from api import chat as chat_module
        monkeypatch.setattr(chat_module, 'RATE_LIMIT_REQUESTS', 3)
        for _ in range(3):
            r = post_chat(chat_url, {'question': 'hi'}, ip='10.0.0.1')
            assert r.status_code == 200

    def test_over_limit_returns_429(self, chat_url, mock_rag, monkeypatch):
        from api import chat as chat_module
        monkeypatch.setattr(chat_module, 'RATE_LIMIT_REQUESTS', 3)
        for _ in range(3):
            post_chat(chat_url, {'question': 'hi'}, ip='10.0.0.2')
        r = post_chat(chat_url, {'question': 'hi'}, ip='10.0.0.2')
        assert r.status_code == 429
        assert 'too many' in r.json()['error'].lower()

    def test_rate_limit_is_per_ip(self, chat_url, mock_rag, monkeypatch):
        from api import chat as chat_module
        monkeypatch.setattr(chat_module, 'RATE_LIMIT_REQUESTS', 2)
        for _ in range(2):
            post_chat(chat_url, {'question': 'hi'}, ip='10.0.0.3')
        r_blocked = post_chat(chat_url, {'question': 'hi'}, ip='10.0.0.3')
        r_other = post_chat(chat_url, {'question': 'hi'}, ip='10.0.0.4')
        assert r_blocked.status_code == 429
        assert r_other.status_code == 200


# ---------- CORS ----------

class TestCORS:
    def test_allowed_origin_is_reflected(self, chat_url, mock_rag):
        r = post_chat(chat_url, {'question': 'hi'}, origin=ALLOWED_ORIGIN)
        assert r.headers.get('Access-Control-Allow-Origin') == ALLOWED_ORIGIN
        assert r.headers.get('Vary') == 'Origin'

    def test_disallowed_origin_gets_no_allow_header(self, chat_url, mock_rag):
        r = post_chat(chat_url, {'question': 'hi'}, origin=DISALLOWED_ORIGIN)
        assert 'Access-Control-Allow-Origin' not in r.headers

    def test_options_preflight_allowed_origin(self, chat_url):
        r = requests.options(
            chat_url,
            headers={'Origin': ALLOWED_ORIGIN, 'Access-Control-Request-Method': 'POST'},
            timeout=5,
        )
        assert r.status_code == 204
        assert r.headers.get('Access-Control-Allow-Origin') == ALLOWED_ORIGIN
        assert 'POST' in r.headers.get('Access-Control-Allow-Methods', '')

    def test_options_preflight_disallowed_origin(self, chat_url):
        r = requests.options(
            chat_url,
            headers={'Origin': DISALLOWED_ORIGIN, 'Access-Control-Request-Method': 'POST'},
            timeout=5,
        )
        assert r.status_code == 204
        assert 'Access-Control-Allow-Origin' not in r.headers


# ---------- Error handling ----------

class TestErrorHandling:
    def test_internal_error_returns_500_with_generic_message(self, chat_url, mock_rag_error):
        r = post_chat(chat_url, {'question': 'hi'})
        assert r.status_code == 500
        body = r.json()
        assert body == {'error': 'Internal server error'}

    def test_internal_error_does_not_leak_stack_or_secrets(self, chat_url, mock_rag_error):
        r = post_chat(chat_url, {'question': 'hi'})
        body_text = r.text
        assert 'Traceback' not in body_text
        assert 'RuntimeError' not in body_text
        assert '/Users/secret' not in body_text
        assert 'sk-' not in body_text

    def test_upstream_timeout_returns_504(self, chat_url, mock_rag_timeout):
        r = post_chat(chat_url, {'question': 'hi'})
        assert r.status_code == 504
        assert 'try again' in r.json()['error'].lower()

    def test_upstream_connection_error_returns_504(self, chat_url, monkeypatch):
        from api import chat as chat_module

        class FailingLLM:
            def generate(self, messages):
                raise requests.ConnectionError('upstream down')

        monkeypatch.setattr(chat_module, 'retrieve_context', lambda q: [])
        monkeypatch.setattr(chat_module, 'get_llm_provider', lambda: FailingLLM())

        r = post_chat(chat_url, {'question': 'hi'})
        assert r.status_code == 504
