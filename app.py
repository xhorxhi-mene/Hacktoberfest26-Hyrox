"""Server web: definisce le route (gli indirizzi) dell'app.

Avvio:  python app.py   →   apri http://localhost:8000
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()  # legge il file .env PRIMA di importare il resto

from flask import Flask, Response, jsonify, render_template, request  # noqa: E402
from werkzeug.exceptions import HTTPException  # noqa: E402

import gemini_service  # noqa: E402
from gemini_service import AIError  # noqa: E402
from image_utils import InvalidImage, prepare_image  # noqa: E402
from markdown_builder import build_markdown, make_filename, to_html  # noqa: E402
from rate_limit import ai_limiter, limited  # noqa: E402
from validation import (  # noqa: E402
    MAX_DAYS,
    MAX_PEOPLE,
    parse_days,
    ValidationError,
    normalize_recognition,
    recognized_places,
    require_places,
    validate_modify,
    validate_prefs,
)

# --- Regole sugli input ------------------------------------------------------
MAX_IMAGES = 6
MAX_IMAGE_MB = 10

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = (MAX_IMAGES * MAX_IMAGE_MB + 1) * 1024 * 1024


def error(message, status=400):
    return jsonify({"error": message}), status


# --- Route -------------------------------------------------------------------
@app.get("/")
def index():
    """La pagina web."""
    return render_template(
        "index.html",
        mock=gemini_service.is_mock(),
        max_images=MAX_IMAGES,
        max_people=MAX_PEOPLE,
        max_days=MAX_DAYS,
    )


@app.get("/api/health")
def health():
    """Controllo veloce che il server sia acceso."""
    return jsonify(
        {
            "ok": True,
            "mock": gemini_service.is_mock(),
            "model": gemini_service.model_name(),
            "key_configured": gemini_service.key_problem() is None,
        }
    )


@app.post("/api/recognize")
@limited(ai_limiter)
def recognize():
    """Passo 1: riceve le foto e restituisce i luoghi riconosciuti."""
    files = [f for f in request.files.getlist("images") if f and f.filename]
    if not files:
        return error("Carica almeno un'immagine.")
    if len(files) > MAX_IMAGES:
        return error(f"Puoi caricare al massimo {MAX_IMAGES} immagini.")

    images = []
    for f in files:
        data = f.read()
        if len(data) > MAX_IMAGE_MB * 1024 * 1024:
            return error(f"{f.filename} supera {MAX_IMAGE_MB} MB.")
        images.append(prepare_image(data, f.filename))  # solleva InvalidImage → 400

    # Durata scelta (facoltativa): serve a Gemma per capire se i luoghi stanno in un unico viaggio
    result = gemini_service.recognize_places(images, parse_days(request.form.get("days")))
    if not recognized_places(result):
        result["warning"] = (
            "Non sono riuscito a riconoscere nessun luogo: prova con foto più nitide, in cui si veda bene "
            "un monumento, un paesaggio o un piatto tipico."
        )
    return jsonify(result)


@app.post("/api/itinerary")
@limited(ai_limiter)
def itinerary():
    """Passo 2: riceve luoghi (eventualmente corretti) + preferenze e restituisce l'itinerario."""
    body = _json_body()
    recognition = normalize_recognition(body.get("recognition"), MAX_IMAGES)
    require_places(recognition)
    prefs = validate_prefs(body.get("prefs"))

    result = gemini_service.generate_itinerary(recognition, prefs)
    return jsonify(_itinerary_response(recognition, prefs, result))


@app.post("/api/modify")
@limited(ai_limiter)
def modify():
    """Passo 2b: modifica l'itinerario con una richiesta in linguaggio naturale."""
    body = _json_body()
    recognition = normalize_recognition(body.get("recognition"), MAX_IMAGES)
    require_places(recognition)
    prefs = validate_prefs(body.get("prefs"))
    text, request_text = validate_modify(body.get("text"), body.get("request"))

    result = gemini_service.modify_itinerary(recognition, prefs, text, request_text)
    return jsonify(_itinerary_response(recognition, prefs, result))


@app.post("/api/download")
def download():
    """Passo 3: trasforma il Markdown in un file .md da scaricare."""
    body = _json_body()
    markdown_text = body.get("markdown")
    if not isinstance(markdown_text, str) or not markdown_text.strip():
        return error("Niente da scaricare.")

    filename = str(body.get("filename") or "itinerario.md").replace("\\", "/")
    filename = os.path.basename(filename)
    filename = "".join(c for c in filename if c.isascii() and (c.isalnum() or c in "-_.")).lstrip(".")
    if not filename.endswith(".md"):
        filename += ".md"
    if filename == ".md":
        filename = "itinerario.md"

    return Response(
        markdown_text,
        mimetype="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Supporto ----------------------------------------------------------------
def _json_body():
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def _itinerary_response(recognition, prefs, result):
    markdown_text = build_markdown(recognition, prefs, result["text"], result["sources"])
    return {
        "text": result["text"],
        "markdown": markdown_text,
        "html": to_html(markdown_text),
        "filename": make_filename(recognition, prefs),
    }


# --- Gestione degli errori: sempre {"error": "..."} -----------------------------
@app.errorhandler(AIError)
def handle_ai_error(exc):
    return error(exc.user_message, exc.status)


@app.errorhandler(ValidationError)
@app.errorhandler(InvalidImage)
def handle_bad_input(exc):
    return error(exc.user_message, 400)


@app.errorhandler(413)
def too_large(_):
    return error(f"File troppo grandi: massimo {MAX_IMAGE_MB} MB per immagine.", 413)


@app.errorhandler(Exception)
def handle_unexpected(exc):
    if isinstance(exc, HTTPException):
        if request.path.startswith("/api/"):
            messages = {404: "Indirizzo non trovato.", 405: "Metodo non consentito per questo indirizzo."}
            return error(messages.get(exc.code, "Richiesta non valida."), exc.code or 500)
        return exc
    log.exception("Errore imprevisto")
    return error("Errore interno del server: riprova.", 500)


if __name__ == "__main__":
    if not gemini_service.is_mock() and gemini_service.key_problem():
        log.warning("ATTENZIONE: %s (oppure usa MOCK_MODE=1 per i dati di prova)", gemini_service.key_problem())
    port = int(os.getenv("PORT", "8000"))
    app.run(debug=True, port=port)
