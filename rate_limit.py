"""Limite di richieste all'AI per indirizzo IP (in memoria, finestra scorrevole di 60 s)."""

import math
import os
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import jsonify, request


class RateLimiter:
    def __init__(self, limit, window=60):
        self.limit = limit
        self.window = window
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key):
        """Registra una richiesta. Restituisce 0 se è permessa, altrimenti i secondi da aspettare."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(1, math.ceil(hits[0] + self.window - now))
            hits.append(now)
            # Pulizia degli IP senza richieste recenti, per non far crescere la memoria
            if len(self._hits) > 10_000:
                for ip in [ip for ip, h in self._hits.items() if not h]:
                    del self._hits[ip]
            return 0


def client_ip():
    """IP del visitatore. X-Forwarded-For si usa solo dietro un proxy fidato (TRUST_PROXY=1,
    es. su Render): altrimenti chiunque potrebbe inventarsi l'intestazione e aggirare il limite.
    Il proxy aggiunge l'IP vero in fondo alla lista, quindi si prende l'ultimo."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded and os.getenv("TRUST_PROXY", "0") == "1":
        return forwarded.split(",")[-1].strip()
    return request.remote_addr or "sconosciuto"


def limited(limiter):
    """Decoratore per le route: risponde 429 se l'IP supera il limite."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            wait = limiter.check(client_ip())
            if wait:
                response = jsonify({"error": f"Troppe richieste: riprova tra {wait} secondi."})
                response.status_code = 429
                response.headers["Retry-After"] = str(wait)
                return response
            return view(*args, **kwargs)

        return wrapper

    return decorator


def _limit_from_env():
    try:
        return max(1, int(os.getenv("RATE_LIMIT_PER_MINUTE", "20")))
    except ValueError:
        return 20


ai_limiter = RateLimiter(_limit_from_env())
