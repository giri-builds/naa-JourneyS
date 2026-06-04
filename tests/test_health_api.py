"""Tests for /api/health — liveness endpoint.

Covers: response shape, CORS, preflight, info-leakage prevention.
"""
import requests

from tests.conftest import ALLOWED_ORIGIN, DISALLOWED_ORIGIN


def test_get_returns_200_with_status_ok(health_url):
    r = requests.get(health_url, headers={'Origin': ALLOWED_ORIGIN}, timeout=5)
    assert r.status_code == 200
    assert r.json() == {'status': 'ok'}


def test_response_does_not_leak_service_internals(health_url):
    r = requests.get(health_url, headers={'Origin': ALLOWED_ORIGIN}, timeout=5)
    body = r.json()
    for forbidden in ('service', 'version', 'stack', 'env', 'host'):
        assert forbidden not in body


def test_allowed_origin_is_reflected(health_url):
    r = requests.get(health_url, headers={'Origin': ALLOWED_ORIGIN}, timeout=5)
    assert r.headers.get('Access-Control-Allow-Origin') == ALLOWED_ORIGIN
    assert r.headers.get('Vary') == 'Origin'


def test_disallowed_origin_gets_no_allow_header(health_url):
    r = requests.get(health_url, headers={'Origin': DISALLOWED_ORIGIN}, timeout=5)
    assert 'Access-Control-Allow-Origin' not in r.headers


def test_options_preflight_returns_204(health_url):
    r = requests.options(
        health_url,
        headers={'Origin': ALLOWED_ORIGIN, 'Access-Control-Request-Method': 'GET'},
        timeout=5,
    )
    assert r.status_code == 204
    assert r.headers.get('Access-Control-Allow-Origin') == ALLOWED_ORIGIN
    assert 'GET' in r.headers.get('Access-Control-Allow-Methods', '')
