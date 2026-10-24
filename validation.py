"""Controllo dei dati che arrivano dalla pagina e normalizzazione delle risposte di Gemma."""

OPTIONS = {
    "days": {"3", "4", "5"},
    "budget": {"basso", "medio", "alto"},
    "season": {"estate", "inverno"},
    "purpose": {"divertimento", "cultura", "mix"},
}
MAX_PEOPLE = 10
MAX_NOTES = 500
NOTES_ENABLED = False  # note libere disattivate per ora: il server le ignora
MAX_REQUEST = 300
MAX_TEXT = 30_000

PLACE_TYPES = {"monumento", "paesaggio", "cibo", "evento", "altro"}
CONFIDENCE = {"alta", "media", "bassa", "manuale"}
NOT_RECOGNIZED = "Non riconosciuto"


class ValidationError(Exception):
    """Dato non valido: il messaggio è pensato per l'utente."""

    def __init__(self, user_message):
        super().__init__(user_message)
        self.user_message = user_message


# --- Preferenze ----------------------------------------------------------------
def validate_prefs(raw):
    """Controlla le preferenze del viaggio. Solleva ValidationError se qualcosa non va."""
    if not isinstance(raw, dict):
        raise ValidationError("Preferenze del viaggio mancanti.")

    prefs = {}
    for key, allowed in OPTIONS.items():
        value = str(raw.get(key, "")).strip().lower()
        if value not in allowed:
            raise ValidationError(f"Valore non valido per '{key}'. Scegli tra: {', '.join(sorted(allowed))}.")
        prefs[key] = value

    try:
        people = int(raw.get("people", 0))
    except (TypeError, ValueError):
        people = 0
    if not 1 <= people <= MAX_PEOPLE:
        raise ValidationError(f"Il numero di persone deve essere tra 1 e {MAX_PEOPLE}.")
    prefs["people"] = people

    notes = raw.get("notes") if NOTES_ENABLED else None
    prefs["notes"] = str(notes).strip()[:MAX_NOTES] if notes else ""
    return prefs


# --- Luoghi riconosciuti --------------------------------------------------------
def _clip(value, limit):
    """Testo pulito e accorciato; stringa vuota per valori mancanti o strani."""
    if value is None or isinstance(value, (dict, list, bool)):
        return ""
    return " ".join(str(value).split())[:limit]


def _normalize_place(raw, index, max_places):
    if not isinstance(raw, dict):
        raw = {}

    try:
        image = int(raw.get("image"))
    except (TypeError, ValueError):
        image = index
    if not 1 <= image <= max_places:
        image = index

    kind = _clip(raw.get("type"), 20).lower()
    confidence = _clip(raw.get("confidence"), 20).lower()
    city, country = _clip(raw.get("city"), 80), _clip(raw.get("country"), 80)
    return {
        "image": image,
        "name": _clip(raw.get("name"), 100) or NOT_RECOGNIZED,
        "city": "" if city.lower() == NOT_RECOGNIZED.lower() else city,
        "country": "" if country.lower() == NOT_RECOGNIZED.lower() else country,
        "type": kind if kind in PLACE_TYPES else "altro",
        "description": _clip(raw.get("description"), 300),
        "confidence": confidence if confidence in CONFIDENCE else "bassa",
    }


def normalize_recognition(data, max_places):
    """Restituisce SEMPRE {"country", "region", "places": [...]}, qualunque sia l'input."""
    if not isinstance(data, dict):
        data = {}
    raw_places = data.get("places")
    if not isinstance(raw_places, list):
        raw_places = []

    places = [_normalize_place(p, i + 1, max_places) for i, p in enumerate(raw_places[:max_places])]
    return {
        "country": _clip(data.get("country"), 80) or None,
        "region": _clip(data.get("region"), 80) or None,
        "places": places,
    }


def align_to_images(recognition, n_images):
    """Esattamente un luogo per foto, in ordine (Gemma a volte ne salta uno o li scambia)."""
    by_image = {}
    for place in recognition["places"]:
        by_image.setdefault(place["image"], place)
    recognition["places"] = [
        by_image.get(i) or _normalize_place({"image": i}, i, n_images) for i in range(1, n_images + 1)
    ]
    return recognition


def check_same_trip(recognition, same_trip):
    """Ferma il flusso se Gemma dice che i luoghi non stanno in un unico viaggio."""
    places = recognized_places(recognition)
    if same_trip or len(places) < 2:
        return
    found = "; ".join(
        f"foto {p['image']}: {p['name']}" + (f" ({p['country']})" if p["country"] else "") for p in places
    )
    raise ValidationError(
        "Le foto sembrano mostrare luoghi troppo lontani tra loro per un unico viaggio di 3-5 giorni "
        f"({found}). Carica foto di luoghi della stessa zona. Se un luogo è stato riconosciuto male, "
        "prova con una foto più nitida in cui si veda bene il monumento o il paesaggio."
    )


def recognized_places(recognition):
    """Solo i luoghi con un nome vero (non "Non riconosciuto")."""
    return [p for p in recognition.get("places", []) if p.get("name") and p["name"] != NOT_RECOGNIZED]


def require_places(recognition):
    if not recognized_places(recognition):
        raise ValidationError(
            "Nessun luogo riconosciuto: prova con foto più nitide, in cui si veda bene "
            "un monumento, un paesaggio o un piatto tipico."
        )


# --- Richiesta di modifica -------------------------------------------------------
def validate_modify(text, request_text):
    """Controlla l'itinerario attuale e la richiesta di modifica; restituisce i testi puliti."""
    text = text.strip() if isinstance(text, str) else ""
    request_text = request_text.strip() if isinstance(request_text, str) else ""

    if not text:
        raise ValidationError("Manca l'itinerario da modificare: crealo di nuovo.")
    if len(text) > MAX_TEXT:
        raise ValidationError("L'itinerario è troppo lungo per essere modificato.")
    if not request_text:
        raise ValidationError("Scrivi cosa vuoi cambiare nell'itinerario.")
    if len(request_text) > MAX_REQUEST:
        raise ValidationError(f"La richiesta di modifica può avere al massimo {MAX_REQUEST} caratteri.")
    return text, request_text
