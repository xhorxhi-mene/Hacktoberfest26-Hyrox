"""Tutto ciò che parla con Gemma 4 tramite la Gemini API."""

import json
import os
import re

from google import genai
from google.genai import types

import prompts

DEFAULT_MODEL = "gemma-4-26b-a4b-it"  # alternativa: "gemma-4-31b-it"
_client = None


def model_name():
    return os.getenv("GEMMA_MODEL", DEFAULT_MODEL)


def is_mock():
    """Con MOCK_MODE=1 l'app risponde con dati finti, senza chiamare l'API.
    Utile per lavorare sulla grafica senza consumare richieste."""
    return os.getenv("MOCK_MODE", "0") == "1"


def _get_client():
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY mancante: controlla il file .env")
        _client = genai.Client(api_key=key)
    return _client


# --- Passo 1: riconoscere i luoghi ---------------------------------------------
def recognize_places(images):
    """images = lista di (bytes, mime_type). Restituisce un dizionario:
    {"country": ..., "region": ..., "places": [{"image": 1, "name": ..., ...}]}"""
    if is_mock():
        return _mock_recognition(len(images))

    parts = [types.Part.from_bytes(data=data, mime_type=mime) for data, mime in images]
    response = _get_client().models.generate_content(
        model=model_name(),
        contents=[*parts, prompts.recognize_prompt(len(images))],
        config=types.GenerateContentConfig(
            system_instruction=prompts.RECOGNIZE_SYSTEM,
            temperature=0.2,  # bassa = risposte più precise e meno "creative"
        ),
    )
    data = _extract_json(response.text)
    data.setdefault("country", None)
    data.setdefault("region", None)
    data.setdefault("places", [])
    return data


# --- Passo 2: creare l'itinerario ----------------------------------------------
def generate_itinerary(recognition, prefs):
    """Restituisce {"text": markdown dell'itinerario, "sources": [{"title", "url"}]}"""
    if is_mock():
        return {"text": prompts.MOCK_ITINERARY, "sources": []}

    config = {"system_instruction": prompts.ITINERARY_SYSTEM, "temperature": 0.7}
    if os.getenv("USE_GOOGLE_SEARCH", "1") == "1":
        # Gemma cerca su Google informazioni aggiornate (orari, prezzi, eventi)
        config["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    if os.getenv("USE_THINKING", "0") == "1":
        # Ragionamento: itinerari più curati ma risposta più lenta
        config["thinking_config"] = types.ThinkingConfig(thinking_level="high")

    response = _get_client().models.generate_content(
        model=model_name(),
        contents=prompts.itinerary_prompt(recognition, prefs),
        config=types.GenerateContentConfig(**config),
    )
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Il modello ha restituito una risposta vuota, riprova.")
    return {"text": text, "sources": _extract_sources(response)}


# --- Funzioni di supporto ------------------------------------------------------
def _extract_json(text):
    """Il modello a volte aggiunge ```json ... ``` o testo extra: teniamo solo il JSON."""
    if not text:
        raise ValueError("risposta vuota dal modello")
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("il modello non ha restituito JSON")
    return json.loads(cleaned[start : end + 1])


def _extract_sources(response):
    """Link delle pagine trovate con la Ricerca Google (se usata)."""
    sources, seen = [], set()
    try:
        chunks = response.candidates[0].grounding_metadata.grounding_chunks or []
    except (AttributeError, IndexError, TypeError):
        return sources
    for chunk in chunks:
        web = getattr(chunk, "web", None)
        if web and web.uri and web.uri not in seen:
            seen.add(web.uri)
            sources.append({"title": web.title or web.uri, "url": web.uri})
    return sources


def _mock_recognition(n_images):
    examples = [
        ("Torre di Pisa", "Pisa", "monumento", "Il celebre campanile pendente in Piazza dei Miracoli."),
        ("Ponte Vecchio", "Firenze", "monumento", "Ponte medievale sull'Arno con le botteghe orafe."),
        ("Mura di Lucca", "Lucca", "monumento", "Mura rinascimentali percorribili a piedi o in bici."),
        ("Cinque Terre", "Vernazza", "paesaggio", "Borghi colorati affacciati sul mare."),
        ("Bistecca alla fiorentina", "Firenze", "cibo", "Piatto tipico toscano."),
        ("Siena, Piazza del Campo", "Siena", "monumento", "La piazza a conchiglia del Palio."),
    ]
    places = [
        {
            "image": i + 1,
            "name": name,
            "city": city,
            "country": "Italia",
            "type": kind,
            "description": desc,
            "confidence": "alta",
        }
        for i, (name, city, kind, desc) in enumerate(examples[:n_images])
    ]
    return {"country": "Italia", "region": "Toscana", "places": places}
