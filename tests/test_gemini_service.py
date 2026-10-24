"""Test di gemini_service.py (M03) con un Gemma finto: nessuna chiamata reale all'API."""

import httpx
import pytest
from google.genai import errors

import gemini_service as gs
from conftest import PREFS, RECOGNITION
from validation import ValidationError

IMG = [b"jpeg-finto-1", b"jpeg-finto-2"]


def _place(i, name, country="Italia"):
    return {"image": i, "name": name, "city": "X", "country": country, "type": "monumento", "confidence": "alta"}


# --- Riconoscimento -----------------------------------------------------------------------
def test_riconoscimento_invia_immagini_e_durata(fake_gemma):
    fake_gemma.reply({"country": "Italia", "same_trip": True, "places": [_place(1, "A"), _place(2, "B")]})
    result = gs.recognize_places(IMG, 4)
    call = fake_gemma.calls[0]
    assert call["model"] == "gemma-4-26b-a4b-it"
    assert sum(1 for c in call["contents"] if not isinstance(c, str)) == 2  # 2 immagini
    assert "4 giorni" in call["contents"][-1]  # la durata arriva nel prompt
    assert [p["name"] for p in result["places"]] == ["A", "B"]


def test_json_malformato_poi_corretto(fake_gemma):
    fake_gemma.reply("non è json", '```json\n{"same_trip": true, "places": [{"image": 1, "name": "A"}]}\n```')
    assert gs.recognize_places(IMG[:1])["places"][0]["name"] == "A"
    assert len(fake_gemma.calls) == 2


def test_json_malformato_due_volte(fake_gemma):
    fake_gemma.reply("boh", "ancora boh")
    with pytest.raises(gs.AIError, match="formato inatteso") as exc:
        gs.recognize_places(IMG[:1])
    assert exc.value.status == 502


@pytest.mark.parametrize("value", [False, "false", "no"])
def test_luoghi_troppo_lontani(fake_gemma, value):
    fake_gemma.reply({"same_trip": value, "places": [_place(1, "Torre Eiffel", "Francia"), _place(2, "Colosseo")]})
    with pytest.raises(ValidationError, match="troppo lontani"):
        gs.recognize_places(IMG, 3)


def test_same_trip_mancante_non_blocca(fake_gemma):
    fake_gemma.reply({"places": [_place(1, "A", "Francia"), _place(2, "B")]})
    assert len(gs.recognize_places(IMG)["places"]) == 2


def test_paese_dedotto_dai_luoghi(fake_gemma):
    fake_gemma.reply({"country": None, "same_trip": True, "places": [_place(1, "A"), _place(2, "B")]})
    assert gs.recognize_places(IMG)["country"] == "Italia"


# --- Itinerario e modifica ----------------------------------------------------------------
def test_itinerario(fake_gemma):
    fake_gemma.reply("```markdown\n## Panoramica\nCiao\n```")
    result = gs.generate_itinerary(RECOGNITION, {**PREFS, "notes": "vegetariani"})
    assert result == {"text": "## Panoramica\nCiao", "sources": []}
    prompt = fake_gemma.calls[0]["contents"]
    assert "Torre di Pisa" in prompt and "<note_viaggiatore>\nvegetariani\n</note_viaggiatore>" in prompt


def test_risposta_vuota(fake_gemma):
    fake_gemma.reply("")
    with pytest.raises(gs.AIError, match="vuota"):
        gs.generate_itinerary(RECOGNITION, PREFS)


def test_modifica_con_tag(fake_gemma):
    fake_gemma.reply("## Panoramica\nPiù economico")
    gs.modify_itinerary(RECOGNITION, PREFS, "## Panoramica\nVecchio", "rendilo più economico")
    prompt = fake_gemma.calls[0]["contents"]
    assert "<richiesta>\nrendilo più economico\n</richiesta>" in prompt and "<itinerario>" in prompt


# --- Errori dell'API tradotti in italiano -----------------------------------------------------
def _api_error(code):
    return errors.APIError(code, {"error": {"message": "boom", "status": "X"}})


@pytest.mark.parametrize(
    "exc,status,text",
    [
        (_api_error(429), 503, "Troppe richieste"),
        (_api_error(401), 500, "Chiave API non valida"),
        (_api_error(403), 500, "Chiave API non valida"),
        (_api_error(404), 500, "Modello non trovato"),
        (_api_error(500), 503, "Problema temporaneo"),
        (_api_error(503), 503, "Problema temporaneo"),
        (httpx.ReadTimeout("timed out"), 504, "troppo"),
        (RuntimeError("???"), 502, "Qualcosa è andato storto"),
    ],
)
def test_errori_leggibili(fake_gemma, exc, status, text):
    fake_gemma.reply(exc)
    with pytest.raises(gs.AIError, match=text) as info:
        gs.generate_itinerary(RECOGNITION, PREFS)
    assert info.value.status == status
    assert "boom" not in info.value.user_message  # il dettaglio tecnico resta nei log


# --- Chiave e modalità di prova ---------------------------------------------------------------
@pytest.mark.parametrize("key,ok", [("", False), ("incolla_qui_la_tua_chiave", False), ("AIzaVera", True)])
def test_controllo_chiave(monkeypatch, key, ok):
    monkeypatch.setenv("GEMINI_API_KEY", key)
    assert (gs.key_problem() is None) == ok


def test_chiave_di_esempio_dà_messaggio_chiaro(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "0")
    monkeypatch.setenv("GEMINI_API_KEY", "incolla_qui_la_tua_chiave")
    monkeypatch.setattr(gs, "_client", None)
    with pytest.raises(gs.AIError, match="testo di esempio"):
        gs.generate_itinerary(RECOGNITION, PREFS)


def test_mock_mode_non_chiama_l_api(monkeypatch):
    monkeypatch.setattr(gs, "_client", None)
    assert gs.is_mock()
    assert gs.recognize_places(IMG)["places"][0]["name"] == "Torre di Pisa"
    assert gs.generate_itinerary(RECOGNITION, PREFS)["text"].startswith("## Panoramica")
    assert gs._client is None  # nessun client creato
