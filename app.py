"""Server web: definisce le route (gli indirizzi) dell'app.

Avvio:  python app.py   →   apri http://localhost:8000
"""

import os

from dotenv import load_dotenv

load_dotenv()  # legge il file .env PRIMA di importare il resto

from flask import Flask, Response, jsonify, render_template, request  # noqa: E402

import gemini_service  # noqa: E402
from markdown_builder import build_markdown, make_filename, to_html  # noqa: E402

# --- Regole sugli input ------------------------------------------------------
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGES = 6
MAX_IMAGE_MB = 5

OPTIONS = {
    "days": {"3", "4", "5"},
    "budget": {"basso", "medio", "alto"},
    "season": {"estate", "inverno"},
    "purpose": {"divertimento", "cultura", "mix"},
}
MAX_PEOPLE = 10

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
    )


@app.get("/api/health")
def health():
    """Controllo veloce che il server sia acceso."""
    return jsonify({"ok": True, "mock": gemini_service.is_mock(), "model": gemini_service.model_name()})


@app.post("/api/recognize")
def recognize():
    """Passo 1: riceve le foto e restituisce i luoghi riconosciuti."""
    files = [f for f in request.files.getlist("images") if f and f.filename]
    if not files:
        return error("Carica almeno un'immagine.")
    if len(files) > MAX_IMAGES:
        return error(f"Puoi caricare al massimo {MAX_IMAGES} immagini.")

    images = []
    for f in files:
        if f.mimetype not in ALLOWED_MIME:
            return error(f"Formato non supportato: {f.filename}. Usa JPG, PNG o WEBP.")
        data = f.read()
        if len(data) > MAX_IMAGE_MB * 1024 * 1024:
            return error(f"{f.filename} supera {MAX_IMAGE_MB} MB.")
        images.append((data, f.mimetype))

    try:
        result = gemini_service.recognize_places(images)
    except Exception as exc:  # errore di rete, chiave sbagliata, JSON non valido...
        app.logger.exception("Errore nel riconoscimento")
        return error(f"Riconoscimento non riuscito: {exc}", 502)
    return jsonify(result)


@app.post("/api/itinerary")
def itinerary():
    """Passo 2: riceve luoghi + preferenze e restituisce l'itinerario."""
    body = request.get_json(silent=True) or {}
    recognition = body.get("recognition") or {}
    if not recognition.get("places"):
        return error("Nessun luogo riconosciuto: rifai il passo 1.")

    prefs, problem = validate_prefs(body.get("prefs") or {})
    if problem:
        return error(problem)

    try:
        result = gemini_service.generate_itinerary(recognition, prefs)
    except Exception as exc:
        app.logger.exception("Errore nella generazione dell'itinerario")
        return error(f"Generazione non riuscita: {exc}", 502)

    markdown_text = build_markdown(recognition, prefs, result["text"], result["sources"])
    return jsonify(
        {
            "markdown": markdown_text,
            "html": to_html(markdown_text),
            "filename": make_filename(recognition, prefs),
        }
    )


@app.post("/api/download")
def download():
    """Passo 3: trasforma il Markdown in un file .md da scaricare."""
    body = request.get_json(silent=True) or {}
    markdown_text = body.get("markdown") or ""
    if not markdown_text.strip():
        return error("Niente da scaricare.")

    filename = os.path.basename(body.get("filename") or "itinerario.md")
    if not filename.endswith(".md"):
        filename += ".md"
    filename = "".join(c for c in filename if c.isalnum() or c in "-_.") or "itinerario.md"

    return Response(
        markdown_text,
        mimetype="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.errorhandler(413)
def too_large(_):
    return error(f"File troppo grandi: massimo {MAX_IMAGE_MB} MB per immagine.", 413)


# --- Validazione -------------------------------------------------------------
def validate_prefs(raw):
    """Controlla che le preferenze arrivate dalla pagina siano valide."""
    prefs = {}
    for key, allowed in OPTIONS.items():
        value = str(raw.get(key, "")).strip().lower()
        if value not in allowed:
            return None, f"Valore non valido per '{key}'. Scegli tra: {', '.join(sorted(allowed))}."
        prefs[key] = value

    try:
        people = int(raw.get("people", 0))
    except (TypeError, ValueError):
        people = 0
    if not 1 <= people <= MAX_PEOPLE:
        return None, f"Il numero di persone deve essere tra 1 e {MAX_PEOPLE}."
    prefs["people"] = people

    prefs["notes"] = str(raw.get("notes", "")).strip()[:500]
    return prefs, None


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(debug=True, port=port)
