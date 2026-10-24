"""Test di rate_limit.py: limite per IP e intestazione X-Forwarded-For."""

import app as app_module
import rate_limit
from rate_limit import RateLimiter


def test_limite_e_finestra_di_60_secondi(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now[0])
    limiter = RateLimiter(limit=2)
    assert limiter.check("1.1.1.1") == 0
    assert limiter.check("1.1.1.1") == 0
    assert limiter.check("1.1.1.1") == 60  # terza richiesta: aspetta 60 s
    assert limiter.check("2.2.2.2") == 0  # un altro IP non è limitato
    now[0] += 61
    assert limiter.check("1.1.1.1") == 0  # finestra scaduta


def _ip(headers, trust):
    with app_module.app.test_request_context(headers=headers, environ_base={"REMOTE_ADDR": "9.9.9.9"}):
        return rate_limit.client_ip()


def test_x_forwarded_for_ignorato_senza_proxy(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY", "0")
    assert _ip({"X-Forwarded-For": "6.6.6.6"}, False) == "9.9.9.9"


def test_x_forwarded_for_con_proxy(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY", "1")
    assert _ip({"X-Forwarded-For": "6.6.6.6, 1.1.1.1"}, True) == "1.1.1.1"
