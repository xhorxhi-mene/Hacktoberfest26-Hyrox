"""Impostazioni comuni dei test.

I test non chiamano mai la vera Gemini API: si usa MOCK_MODE oppure un Gemma finto
(fixture `fake_gemma`). Così girano senza chiave, senza internet e senza consumare quota.
"""

import io
import json
import os

import pytest

# Variabili impostate PRIMA di importare l'app: load_dotenv() non sovrascrive quelle già presenti,
# quindi il .env reale (con la chiave vera) non viene usato durante i test.
os.environ["MOCK_MODE"] = "1"
os.environ["GEMINI_API_KEY"] = "chiave-finta-per-i-test"
os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"
os.environ["TRUST_PROXY"] = "0"
os.environ["USE_GOOGLE_SEARCH"] = "0"

from PIL import Image  # noqa: E402

import app as app_module  # noqa: E402
import gemini_service  # noqa: E402

FAKE_KEY = os.environ["GEMINI_API_KEY"]

PREFS = {"days": "3", "budget": "medio", "season": "estate", "purpose": "mix", "people": 2, "notes": ""}
RECOGNITION = {
    "country": "Italia",
    "region": "Toscana",
    "places": [
        {"image": 1, "name": "Torre di Pisa", "city": "Pisa", "country": "Italia", "type": "monumento", "confidence": "alta"},
        {"image": 2, "name": "Ponte Vecchio", "city": "Firenze", "country": "Italia", "type": "monumento", "confidence": "alta"},
    ],
}


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def make_image(fmt="PNG", size=(200, 150), color=(200, 100, 50), exif_orientation=None):
    """Immagine generata in memoria nel formato richiesto."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    if fmt == "HEIF":
        import pillow_heif

        pillow_heif.from_pillow(img).save(buf, format="HEIF")
    else:
        kwargs = {}
        if exif_orientation:
            exif = Image.Exif()
            exif[0x0112] = exif_orientation
            kwargs["exif"] = exif
        img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


@pytest.fixture
def image_bytes():
    return make_image


# --- Gemma finto ------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, text):
        self.text = text
        self.candidates = []


class FakeGemma:
    """Sostituisce il client google-genai: restituisce le risposte preparate, in ordine,
    oppure solleva l'eccezione indicata."""

    def __init__(self):
        self.outputs = []
        self.calls = []
        self.models = self

    def reply(self, *outputs):
        self.outputs.extend(outputs)
        return self

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return _FakeResponse(out if isinstance(out, str) else json.dumps(out))


@pytest.fixture
def fake_gemma(monkeypatch):
    """Disattiva MOCK_MODE e collega un Gemma finto al posto della vera API."""
    fake = FakeGemma()
    monkeypatch.setenv("MOCK_MODE", "0")
    monkeypatch.setattr(gemini_service, "_client", fake)
    return fake
