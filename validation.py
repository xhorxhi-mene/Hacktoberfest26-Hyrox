"""Controllo dei dati che arrivano dalla pagina e normalizzazione delle risposte di Gemma."""

import re
import unicodedata

MIN_DAYS, MAX_DAYS = 1, 10
DEFAULT_DAYS = 5  # usato dal riconoscimento se la pagina non manda la durata
OPTIONS = {
    "days": {str(d) for d in range(MIN_DAYS, MAX_DAYS + 1)},
    "budget": {"basso", "medio", "alto"},
    "season": {"primavera", "estate", "autunno", "inverno"},
    "purpose": {"divertimento", "cultura", "mix"},
}
MAX_PEOPLE = 10
MAX_NOTES = 300
NOTES_ENABLED = True
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
            if key == "days":
                raise ValidationError(f"La durata deve essere tra {MIN_DAYS} e {MAX_DAYS} giorni.")
            raise ValidationError(f"Valore non valido per '{key}'. Scegli tra: {', '.join(sorted(allowed))}.")
        prefs[key] = value

    raw_people = raw.get("people", 0)
    try:
        # true/false o numeri con la virgola (2.7) non sono un numero di persone valido
        if isinstance(raw_people, bool) or (isinstance(raw_people, float) and not raw_people.is_integer()):
            raise ValueError
        people = int(raw_people)
    except (TypeError, ValueError):
        people = 0
    if not 1 <= people <= MAX_PEOPLE:
        raise ValidationError(f"Il numero di persone deve essere tra 1 e {MAX_PEOPLE}.")
    prefs["people"] = people

    notes = raw.get("notes") if NOTES_ENABLED else None
    prefs["notes"] = clean_free_text(notes, MAX_NOTES, "nelle note") if isinstance(notes, str) else ""
    return prefs


def parse_days(value):
    """Durata per il riconoscimento: se manca o non è valida si usa DEFAULT_DAYS."""
    value = str(value or "").strip()
    return int(value) if value in OPTIONS["days"] else DEFAULT_DAYS


def days_label(days):
    """'1 giorno', '3 giorni'..."""
    return f"{days} giorno" if str(days) == "1" else f"{days} giorni"


# --- Testo libero (note, richieste di modifica): protezione da prompt injection --------
# Frasi tipiche di chi prova a dare ordini al modello invece di descrivere il viaggio.
_INJECTION_PATTERNS = [
    r"\b(ignora|ignorare|dimentica|dimenticare|trascura|ignore|forget|disregard|override)\b.{0,40}"
    r"\b(istruzion\w*|prompt|regol\w*|precedent\w*|instructions?|rules?|previous|above)\b",
    r"\b(system|developer)\s*(prompt|message|mode)\b",
    r"\b(prompt|istruzioni|messaggio)\s+(di\s+)?sistema\b",
    r"\b(sei|ora sei|adesso sei|da ora sei)\s+(un|una|il|la)\s+(assistente|ai|chatbot|modello|hacker|programmatore)\b",
    r"\b(you are now|act as|pretend to be|fingi di essere|comportati come|impersona)\b",
    r"\b(jailbreak|dan mode|do anything now)\b",
    r"\b(rivela|mostra|stampa|ripeti|reveal|print|show|repeat)\b.{0,30}\b(prompt|istruzion\w*|instructions?|chiave|api key|password)\b",
    # (non "storia" o "programma": nelle note di viaggio hanno un significato normale)
    r"\b(scrivi|genera|crea|write|generate)\b.{0,25}\b(codice|code|script|poesia|poem|canzone|song|racconto|essay)\b",
    r"\b(rispondi|answer|reply)\b.{0,20}\b(solo|soltanto|only)\b",
    r"</?\s*(itinerario|richiesta|note\w*|system|user|assistant)\b",  # tag del prompt (es. </note_viaggiatore>)
]
_INJECTION_RE = re.compile("|".join(f"(?:{p})" for p in _INJECTION_PATTERNS), re.IGNORECASE | re.DOTALL)
# Link: "http(s)://" o "www." in qualsiasi forma; domini "nudi" solo se scritti in minuscolo
# (es. "sito.com"), così "vegetariani.Io preferisco" (spazio dimenticato dopo il punto) non viene bloccato.
_URL_RE = re.compile(
    r"(?i:https?://|www\.)\S+|\b[a-z0-9-]{2,}\.(?:com|it|net|org|info|ru|xyz)(?:/\S*)?(?![\w.])"
)


def _ascii_fold(text):
    """Toglie gli accenti, così 'è' e 'e' vengono controllati allo stesso modo."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def clean_free_text(text, limit, where):
    """Pulisce un testo scritto dall'utente e lo rifiuta se sembra un tentativo di
    manipolare il modello o se non ha senso. `where` es. "nelle note". Restituisce il testo pulito."""
    # Caratteri invisibili (zero-width ecc., usati per spezzare le parole e nascondere istruzioni)
    # → eliminati; a capo e tabulazioni → spazio
    text = "".join(
        "" if unicodedata.category(c) == "Cf" else " " if unicodedata.category(c) == "Cc" else c for c in text
    )
    text = " ".join(text.split())
    if not text:
        return ""
    if len(text) > limit:
        raise ValidationError(f"Testo troppo lungo {where}: massimo {limit} caratteri.")

    folded = _ascii_fold(text)
    if _URL_RE.search(folded):
        raise ValidationError(f"Non inserire link {where}.")
    if _INJECTION_RE.search(folded):
        raise ValidationError(
            f"Il testo {where} sembra contenere istruzioni per l'AI invece di informazioni sul viaggio. "
            "Scrivi solo preferenze, ad esempio: «siamo vegetariani», «niente musei lunghi»."
        )

    # Testo senza senso: lettere ripetute, sequenze di consonanti, quasi solo simboli
    letters = sum(c.isalpha() for c in text)
    if (
        re.search(r"(.)\1{5,}", text)
        or re.search(r"(\w{2,4})\1{3,}", folded, re.IGNORECASE)  # sillabe ripetute: "hahahaha", "lololol"
        or re.search(r"[bcdfghjklmnpqrstvwxz]{7,}", folded, re.IGNORECASE)
        or (len(text) >= 15 and letters < len(text) * 0.3)
    ):
        raise ValidationError(f"Il testo {where} non sembra comprensibile: scrivi una frase chiara.")

    # Simboli che potrebbero chiudere i tag del prompt o formattare codice
    return re.sub(r"[<>{}`\[\]\\]", "", text).strip()


# --- Luoghi riconosciuti --------------------------------------------------------
def _clip(value, limit):
    """Testo pulito e accorciato; stringa vuota per valori mancanti o strani.
    Toglie anche i caratteri invisibili e i simboli che potrebbero chiudere i tag del prompt."""
    if value is None or isinstance(value, (dict, list, bool)):
        return ""
    text = "".join(c for c in str(value) if unicodedata.category(c) != "Cf")
    text = re.sub(r"[<>{}`\[\]\\|]", "", text)
    return " ".join(text.split())[:limit]


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


def check_same_trip(recognition, same_trip, days=DEFAULT_DAYS):
    """Ferma il flusso se Gemma dice che i luoghi non stanno in un unico viaggio della durata scelta."""
    places = recognized_places(recognition)
    if same_trip or len(places) < 2:
        return
    found = "; ".join(
        f"foto {p['image']}: {p['name']}" + (f" ({p['country']})" if p["country"] else "") for p in places
    )
    longer = f" oppure aumenta la durata del viaggio" if int(days) < MAX_DAYS else ""
    raise ValidationError(
        f"Le foto sembrano mostrare luoghi troppo lontani tra loro per un viaggio di {days_label(days)} "
        f"({found}). Carica foto di luoghi della stessa zona{longer}. Se un luogo è stato riconosciuto male, "
        "prova con una foto più nitida in cui si veda bene il monumento o il paesaggio."
    )


def check_places_text(recognition):
    """I luoghi arrivano dalla pagina (e un domani l'utente potrà correggerli): finiscono nel
    prompt, quindi si applicano gli stessi controlli anti-manipolazione delle note.
    Niente filtro "testo senza senso": bloccherebbe nomi veri come "Llanfairpwllgwyngyll"."""
    fields = [recognition.get("country"), recognition.get("region")]
    for p in recognition.get("places", []):
        fields += [p.get("name"), p.get("city"), p.get("country")]
    for value in filter(None, fields):
        folded = _ascii_fold(value)
        if _URL_RE.search(folded) or _INJECTION_RE.search(folded):
            raise ValidationError(f"Il nome del luogo «{value[:40]}» non è valido: scrivi solo il nome del posto.")


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
    request_text = clean_free_text(request_text, MAX_REQUEST, "nella richiesta di modifica")
    if not request_text:
        raise ValidationError("Scrivi cosa vuoi cambiare nell'itinerario.")
    return text, request_text
