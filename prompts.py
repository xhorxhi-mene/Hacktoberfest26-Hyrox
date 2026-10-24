"""I testi (prompt) mandati a Gemma 4.
Per migliorare i risultati, quasi sempre basta modificare questo file."""

# --- Passo 1: riconoscimento ---------------------------------------------------
RECOGNIZE_SYSTEM = (
    "Sei un esperto di geografia, arte, architettura e turismo. "
    "Riconosci luoghi, monumenti, paesaggi e piatti tipici a partire da fotografie. "
    "Rispondi SEMPRE e SOLO con JSON valido, senza testo prima o dopo."
)


def recognize_prompt(n_images):
    return f"""Ti invio {n_images} immagini, in ordine (la prima è l'immagine 1).
Per ogni immagine individua il luogo, il monumento o l'elemento tipico mostrato.
Poi deduci il paese (ed eventualmente la regione) su cui si concentra il viaggio.

Rispondi con questo JSON:
{{
  "country": "paese principale del viaggio",
  "region": "regione o area, oppure null",
  "places": [
    {{
      "image": 1,
      "name": "nome del luogo",
      "city": "città o località",
      "country": "paese",
      "type": "monumento | paesaggio | cibo | evento | altro",
      "description": "una frase su cosa si vede e perché è interessante",
      "confidence": "alta | media | bassa"
    }}
  ]
}}

Regole:
- Un elemento in "places" per ogni immagine, nello stesso ordine.
- Se non riconosci un'immagine: "name": "Non riconosciuto", "confidence": "bassa".
- Scrivi tutti i testi in italiano."""


# --- Passo 2: itinerario -------------------------------------------------------
ITINERARY_SYSTEM = (
    "Sei una guida turistica esperta che crea itinerari realistici, ben organizzati "
    "e facili da seguire. Scrivi in italiano, in Markdown. "
    "Non inventare orari o prezzi precisi se non sei sicuro: indica stime e consiglia di verificarli."
)

BUDGET = {
    "basso": "basso (ostelli o B&B economici, street food, mezzi pubblici, attrazioni gratuite)",
    "medio": "medio (hotel 3 stelle, ristoranti tipici, qualche attrazione a pagamento)",
    "alto": "alto (hotel 4-5 stelle, ristoranti rinomati, esperienze esclusive, taxi o auto)",
}
PURPOSE = {
    "divertimento": "divertimento (vita notturna, esperienze, attività all'aperto, svago)",
    "cultura": "cultura (musei, monumenti, storia, arte, tradizioni locali)",
    "mix": "un mix equilibrato di cultura e divertimento",
}


def itinerary_prompt(recognition, prefs):
    places = "\n".join(
        f"- {p.get('name')} ({p.get('city')}, {p.get('country')})"
        for p in recognition.get("places", [])
        if p.get("name") and p.get("name") != "Non riconosciuto"
    ) or "- nessun luogo preciso: proponi i luoghi più rappresentativi del paese"
    area = recognition.get("region") or recognition.get("country") or "il paese indicato"

    return f"""Crea il miglior itinerario possibile per un viaggio in {area}.

Luoghi che il viaggiatore vuole vedere (riconosciuti dalle sue foto):
{places}

Preferenze:
- Durata: {prefs['days']} giorni
- Budget: {BUDGET[prefs['budget']]}
- Periodo: {prefs['season']}
- Scopo: {PURPOSE[prefs['purpose']]}
- Persone: {prefs['people']}
- Note del viaggiatore: {prefs.get('notes') or 'nessuna'}

Regole:
1. Includi tutti i luoghi della lista, se raggiungibili in modo sensato nei giorni disponibili.
   Se uno è troppo lontano, spiegalo in "Consigli utili".
2. Raggruppa le tappe vicine nello stesso giorno, per ridurre gli spostamenti.
3. Adatta attività, ristoranti e alloggi al budget, allo scopo e al numero di persone.
4. Tieni conto della stagione: clima, aperture, attività stagionali, abbigliamento.
5. Indica per ogni spostamento il mezzo consigliato e il tempo indicativo.

Usa esattamente queste sezioni (non aggiungere un titolo "#" principale):

## Panoramica
2-3 frasi sul viaggio.

## Giorno 1 – titolo breve
### Mattina
### Pomeriggio
### Sera
(ripeti per ogni giorno, fino al giorno {prefs['days']})

## Dove dormire
2-3 zone o tipi di alloggio adatti al budget.

## Come spostarsi

## Budget stimato
Tabella Markdown con colonne: Voce | Costo per persona | Totale per {prefs['people']} persone.
Voci: alloggio, cibo, trasporti, attrazioni, totale.

## Consigli utili
Elenco puntato."""


# --- Dati finti per MOCK_MODE=1 ------------------------------------------------
MOCK_ITINERARY = """## Panoramica
Tre giorni tra le città d'arte della Toscana, con ritmo tranquillo e budget medio. *(Itinerario di prova: MOCK_MODE è attivo.)*

## Giorno 1 – Pisa
### Mattina
Piazza dei Miracoli: Torre, Duomo e Battistero.
### Pomeriggio
Passeggiata sui Lungarni e Borgo Stretto.
### Sera
Cena in una trattoria del quartiere di Santa Maria.

## Giorno 2 – Lucca
### Mattina
Treno Pisa → Lucca (circa 30 minuti). Giro delle Mura in bicicletta.
### Pomeriggio
Piazza dell'Anfiteatro e Torre Guinigi.
### Sera
Rientro a Pisa.

## Giorno 3 – Firenze
### Mattina
Treno per Firenze (circa 1 ora). Ponte Vecchio e Uffizi.
### Pomeriggio
Duomo e Piazzale Michelangelo.
### Sera
Bistecca alla fiorentina in centro.

## Dove dormire
- B&B nel centro storico di Pisa
- Hotel 3 stelle vicino alla stazione

## Come spostarsi
Treni regionali tra le città, a piedi nei centri storici.

## Budget stimato
| Voce | Costo per persona | Totale per 2 persone |
|---|---|---|
| Alloggio | 150 € | 300 € |
| Cibo | 120 € | 240 € |
| Trasporti | 30 € | 60 € |
| Attrazioni | 60 € | 120 € |
| **Totale** | **360 €** | **720 €** |

## Consigli utili
- Prenota gli Uffizi online in anticipo.
- La salita sulla Torre di Pisa ha posti limitati.
"""
