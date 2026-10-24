"""Test di markdown_builder.py (M05): file .md, HTML sicuro, nome del file."""

import pytest

from conftest import PREFS, RECOGNITION
from markdown_builder import build_markdown, make_filename, to_html


def test_file_markdown_completo():
    rec = {**RECOGNITION, "places": RECOGNITION["places"] + [{"image": 3, "name": "Non riconosciuto"}]}
    md = build_markdown(rec, {**PREFS, "notes": "vegetariani | niente scale"}, "## Panoramica\nTesto", [])
    assert md.startswith("# Itinerario: Toscana – 3 giorni")
    assert "| Note | vegetariani / niente scale |" in md  # il "|" non rompe la tabella
    assert "**Torre di Pisa**" in md and "Non riconosciuto" not in md  # solo i luoghi riconosciuti
    assert "## Panoramica" in md and md.rstrip().endswith("verificali prima di partire.*")


def test_fonti():
    md = build_markdown(RECOGNITION, PREFS, "## Panoramica\nx", [{"title": "Sito [ufficiale]", "url": "https://a.it"}])
    assert "- [Sito ufficiale](https://a.it)" in md


@pytest.mark.parametrize(
    "rec,days,expected",
    [
        ({"region": "Toscana"}, "3", "itinerario-toscana-3-giorni.md"),
        ({"country": "Città del Vaticano"}, "1", "itinerario-citta-del-vaticano-1-giorno.md"),
        ({}, "10", "itinerario-viaggio-10-giorni.md"),
    ],
)
def test_nome_del_file(rec, days, expected):
    assert make_filename(rec, {**PREFS, "days": days}) == expected


@pytest.mark.parametrize(
    "markdown,forbidden",
    [
        ("<script>alert(1)</script>", "<script"),
        ("[clicca](javascript:alert(1))", "javascript:"),
        ("[x](JaVaScRiPt:alert(1))", "JaVaScRiPt:"),
        ("[x](data:text/html;base64,AA)", "data:"),
        ("![pixel](https://tracker.example/p.gif)", "<img"),
    ],
)
def test_html_sicuro(markdown, forbidden):
    assert forbidden not in to_html(markdown)


def test_link_sicuri_in_nuova_scheda():
    html = to_html("[ok](https://example.com)")
    assert 'href="https://example.com"' in html and 'target="_blank"' in html and "noopener" in html


def test_tabelle_convertite():
    assert "<table>" in to_html("| A | B |\n|---|---|\n| 1 | 2 |")
