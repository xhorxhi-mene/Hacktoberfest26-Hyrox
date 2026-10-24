"""Controllo e preparazione delle foto prima di inviarle a Gemma.

Ogni immagine viene verificata sul CONTENUTO (non sull'estensione), raddrizzata
secondo i dati EXIF, convertita in RGB, ridotta a 1024 px e salvata in JPEG.
"""

import io
import logging

from PIL import Image, ImageOps, UnidentifiedImageError

log = logging.getLogger(__name__)

try:  # foto HEIC/HEIF degli iPhone
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:  # pragma: no cover - dipende dall'ambiente
    HEIF_SUPPORT = False

# Protezione dalle immagini enormi ("decompression bomb")
Image.MAX_IMAGE_PIXELS = 40_000_000

ALLOWED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP", "HEIF"}
MAX_SIDE = 1024
JPEG_QUALITY = 85


class InvalidImage(Exception):
    """Immagine non valida: il messaggio è pensato per l'utente."""

    def __init__(self, user_message):
        super().__init__(user_message)
        self.user_message = user_message


def _looks_like_heic(data, filename):
    name = (filename or "").lower()
    if name.endswith((".heic", ".heif")):
        return True
    # I file HEIF hanno "ftyp" + marca (heic, heix, mif1...) all'inizio
    return data[4:8] == b"ftyp" and data[8:12] in {b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1"}


def prepare_image(data, filename=""):
    """Verifica l'immagine e restituisce i byte di un JPEG pronto per Gemma."""
    label = filename or "immagine"
    if not data:
        raise InvalidImage(f"{label} è vuota.")

    if not HEIF_SUPPORT and _looks_like_heic(data, filename):
        raise InvalidImage(
            f"{label}: le foto HEIC non sono supportate su questo server. Convertila in JPG e riprova."
        )

    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in ALLOWED_FORMATS:
                raise InvalidImage(f"Formato non supportato: {label}. Usa JPG, PNG, WEBP o HEIC.")
            if img.width * img.height > Image.MAX_IMAGE_PIXELS:
                raise InvalidImage(f"{label} ha una risoluzione troppo alta.")

            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            img.thumbnail((MAX_SIDE, MAX_SIDE))

            out = io.BytesIO()
            img.save(out, format="JPEG", quality=JPEG_QUALITY)
            return out.getvalue()
    except InvalidImage:
        raise
    except Image.DecompressionBombError:
        raise InvalidImage(f"{label} ha una risoluzione troppo alta.")
    except UnidentifiedImageError:
        raise InvalidImage(f"{label} non è un'immagine valida. Usa JPG, PNG, WEBP o HEIC.")
    except Exception:
        log.exception("Errore nella lettura di %s", label)
        raise InvalidImage(f"Impossibile leggere {label}: il file potrebbe essere danneggiato.")
