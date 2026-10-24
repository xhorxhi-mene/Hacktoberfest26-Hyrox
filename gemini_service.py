"""Tutto ciò che parla con Gemma 4 tramite la Gemini API.

Gli errori tecnici vengono scritti nei log e trasformati in AIError, con un
messaggio comprensibile per l'utente.
"""

import json
import logging
import os
import re

from google import genai
from google.genai import types

import prompts
from validation import align_to_images, check_same_trip, normalize_recognition, recognized_places

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gemma-4-26b-a4b-it"  # alternativa: "gemma-4-31b-it"
TIMEOUT_MS = 180_000  # l'itinerario con la Ricerca Google può richiedere tempo
_client = None


class AIError(Exception):
    """Errore nella chiamata a Gemma, con messaggio per l'utente e codice HTTP."""

    def __init__(self, user_message, status=502):
        super().__init__(user_message)
        self.user_message = user_message
        self.status = status


def model_name():
    return os.getenv("GEMMA_MODEL") or DEFAULT_MODEL


def is_mock():
    """Con MOCK_MODE=1 l'app risponde con dati finti, senza chiamare l'API.
    Utile per lavorare sulla grafica senza consumare richieste."""
    return os.getenv("MOCK_MODE", "0") == "1"


def _get_client():
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise AIError("Chiave API mancante: controlla GEMINI_API_KEY nel file .env.", 500)
        _client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=TIMEOUT_MS))
    return _client


def _friendly_error(exc):
    """Traduce un errore tecnico in un AIError leggibile."""
    code = getattr(exc, "code", None)
    if not isinstance(code, int):
        code = getattr(exc, "status_code", None)
    text = str(exc).lower()

    if code == 429 or "quota" in text or "resource_exhausted" in text:
        return AIError("Troppe richieste a Gemma in questo momento: riprova tra un minuto.", 503)
    if code in (401, 403) or "api key" in text or "api_key" in text:
        return AIError("Chiave API non valida: controlla GEMINI_API_KEY nel file .env.", 500)
    if code == 404:
        return AIError("Modello non trovato: controlla GEMMA_MODEL nel file .env.", 500)
    if isinstance(code, int) and 500 <= code < 600:
        return AIError("Problema temporaneo del servizio di Google: riprova tra poco.", 503)
    if "timeout" in text or "timed out" in text or "Timeout" in type(exc).__name__:
        return AIError("Gemma ci sta mettendo troppo a rispondere: riprova.", 504)
    return AIError("Qualcosa è andato storto nella chiamata a Gemma: riprova.", 502)


def _generate(contents, config):
    """Chiama Gemma; qualsiasi errore diventa un AIError (il dettaglio va solo nei log)."""
    try:
        return _get_client().models.generate_content(
            model=model_name(),
            contents=contents,
            config=types.GenerateContentConfig(**config),
        )
    except AIError:
        raise
    except Exception as exc:
        log.exception("Errore nella chiamata a Gemma")
        raise _friendly_error(exc) from exc


def _text_config():
    """Configurazione per itinerario e modifiche (Ricerca Google, ragionamento)."""
    config = {"temperature": 0.7}
    if os.getenv("USE_GOOGLE_SEARCH", "1") == "1":
        # Gemma cerca su Google informazioni aggiornate (orari, prezzi, eventi)
        config["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    if os.getenv("USE_THINKING", "0") == "1":
        # Ragionamento: itinerari più curati ma risposta più lenta
        config["thinking_config"] = types.ThinkingConfig(thinking_level="high")
    return config


def _response_text(response):
    try:
        return response.text or ""
    except Exception:  # risposta bloccata o senza candidati
        log.exception("Risposta di Gemma non leggibile")
        return ""


# --- Passo 1: riconoscere i luoghi ---------------------------------------------
def recognize_places(images):
    """images = lista di byte JPEG. Restituisce {"country", "region", "places": [...]}."""
    if is_mock():
        return normalize_recognition(_mock_recognition(len(images)), len(images))

    parts = [types.Part.from_bytes(data=data, mime_type="image/jpeg") for data in images]
    config = {"system_instruction": prompts.RECOGNIZE_SYSTEM, "temperature": 0.2}

    for attempt in (1, 2):  # se il JSON è sbagliato riprova una volta
        response = _generate([*parts, prompts.recognize_prompt(len(images))], config)
        text = _response_text(response)
        try:
            data = _extract_json(text)
            break
        except ValueError:
            log.warning("JSON non valido da Gemma (tentativo %d): %.500s", attempt, text)
    else:
        raise AIError("Gemma ha risposto in un formato inatteso: riprova.", 502)

    recognition = align_to_images(normalize_recognition(data, len(images)), len(images))
    check_same_trip(recognition, _same_trip(data))  # solleva ValidationError → 400

    # Se Gemma non ha indicato il paese ma i luoghi sono tutti nello stesso, usiamo quello
    countries = {p["country"] for p in recognized_places(recognition) if p["country"]}
    if not recognition["country"] and len(countries) == 1:
        recognition["country"] = countries.pop()
    return recognition


def _same_trip(data):
    """Legge "same_trip" dal JSON di Gemma; se manca o è strano, non blocca nulla."""
    value = data.get("same_trip") if isinstance(data, dict) else None
    return not (value is False or str(value).strip().lower() in {"false", "no"})


# --- Passo 2: creare l'itinerario ----------------------------------------------
def generate_itinerary(recognition, prefs):
    """Restituisce {"text": markdown dell'itinerario, "sources": [{"title", "url"}]}"""
    if is_mock():
        return {"text": prompts.MOCK_ITINERARY, "sources": []}

    config = {**_text_config(), "system_instruction": prompts.ITINERARY_SYSTEM}
    response = _generate(prompts.itinerary_prompt(recognition, prefs), config)
    return _itinerary_result(response)


# --- Passo 3: modificare l'itinerario ------------------------------------------
def modify_itinerary(recognition, prefs, current_text, request_text):
    """Riscrive l'itinerario seguendo la richiesta dell'utente. Stessa forma di generate_itinerary."""
    if is_mock():
        note = f'\n\n> *Modifica di prova (MOCK_MODE): "{request_text}"*\n'
        return {"text": current_text.rstrip() + note, "sources": []}

    config = {**_text_config(), "system_instruction": prompts.MODIFY_SYSTEM}
    response = _generate(prompts.modify_prompt(recognition, prefs, current_text, request_text), config)
    return _itinerary_result(response)


# --- Funzioni di supporto ------------------------------------------------------
def _itinerary_result(response):
    text = _strip_code_fence(_response_text(response))
    if not text:
        raise AIError("Gemma ha restituito una risposta vuota: riprova.", 502)
    return {"text": text, "sources": _extract_sources(response)}


def _strip_code_fence(text):
    """Toglie l'eventuale ```markdown ... ``` che racchiude tutto il testo."""
    text = (text or "").strip()
    match = re.fullmatch(r"```[a-zA-Z]*\s*\n(.*?)\n?```", text, flags=re.DOTALL)
    return match.group(1).strip() if match else text


def _extract_json(text):
    """Il modello a volte aggiunge ```json ... ``` o testo extra: teniamo solo il JSON."""
    if not text:
        raise ValueError("risposta vuota dal modello")
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("il modello non ha restituito JSON")
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON non valido: {exc}") from exc


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
        for i, (name, city, kind, desc) in enumerate(prompts.MOCK_PLACES[:n_images])
    ]
    return {"country": "Italia", "region": "Toscana", "places": places}
