"""Costruisce il file .md finale e la sua versione HTML per la pagina."""

import re
import unicodedata
from datetime import date

import markdown as md_lib

from validation import days_label, recognized_places

LABELS = {
    "budget": {"basso": "Basso", "medio": "Medio", "alto": "Alto"},
    "season": {"primavera": "Primavera", "estate": "Estate", "autunno": "Autunno", "inverno": "Inverno"},
    "purpose": {"divertimento": "Divertimento", "cultura": "Cultura", "mix": "Cultura + divertimento"},
}


def build_markdown(recognition, prefs, itinerary_text, sources):
    area = recognition.get("region") or recognition.get("country") or "Viaggio"
    lines = [
        f"# Itinerario: {area} – {days_label(prefs['days'])}",
        "",
        f"> Creato il {date.today().strftime('%d/%m/%Y')} con Gemma 4 (Gemini API).",
        "",
        "## Il tuo viaggio",
        "",
        "| Voce | Scelta |",
        "|---|---|",
        f"| Durata | {days_label(prefs['days'])} |",
        f"| Budget | {LABELS['budget'][prefs['budget']]} |",
        f"| Periodo | {LABELS['season'][prefs['season']]} |",
        f"| Scopo | {LABELS['purpose'][prefs['purpose']]} |",
        f"| Persone | {prefs['people']} |",
    ]
    if prefs.get("notes"):
        notes = " ".join(prefs["notes"].split()).replace("|", "/")
        lines.append(f"| Note | {notes} |")

    lines += ["", "## Luoghi riconosciuti dalle tue foto", ""]
    for p in recognized_places(recognition):
        where = ", ".join(x for x in (p.get("city"), p.get("country")) if x)
        if p.get("confidence") == "manuale":
            detail = "inserito da te"
        else:
            detail = f"affidabilità: {p.get('confidence', '?')}"
        lines.append(f"- **{p['name']}**" + (f" – {where}" if where else "") + f" *({detail})*")

    lines += ["", itinerary_text.strip(), ""]

    if sources:
        lines += ["## Fonti", ""]
        for s in sources:
            title = re.sub(r"[\[\]]", "", s["title"]) or s["url"]  # le parentesi quadre rompono il link
            lines.append(f"- [{title}]({s['url']})")
        lines.append("")

    lines += ["---", "*Orari e prezzi sono indicativi: verificali prima di partire.*", ""]
    return "\n".join(lines)


_LINK_RE = re.compile(r'<a href="([^"]*)"')
_IMG_RE = re.compile(r'<img alt="([^"]*)"[^>]*>')


def _safe_link(match):
    """Tiene solo i link http(s), aperti in una nuova scheda; gli altri (javascript:, data:...) perdono l'href."""
    url = match.group(1)
    if re.match(r"https?://", url, re.IGNORECASE):
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer nofollow"'
    return "<a"


def to_html(markdown_text):
    """Markdown → HTML per mostrarlo nella pagina, sicuro anche senza DOMPurify:
    - i '<' vengono neutralizzati, così l'HTML scritto dal modello non viene eseguito;
    - i link non http(s) (es. javascript:) vengono disattivati;
    - le immagini scritte dal modello diventano solo testo (niente tracciamento)."""
    safe = markdown_text.replace("<", "&lt;")
    html = md_lib.markdown(safe, extensions=["tables", "sane_lists"])
    html = _LINK_RE.sub(_safe_link, html)
    return _IMG_RE.sub(lambda m: m.group(1), html)


def make_filename(recognition, prefs):
    area = recognition.get("region") or recognition.get("country") or "viaggio"
    ascii_area = unicodedata.normalize("NFKD", area).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_area.lower()).strip("-") or "viaggio"
    return f"itinerario-{slug}-{days_label(prefs['days']).replace(' ', '-')}.md"

