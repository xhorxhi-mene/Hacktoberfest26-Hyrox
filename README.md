# 📸 Photo Travel Planner

Carica le foto di luoghi, monumenti e piatti tipici: **Gemma 4** riconosce dove si trovano e crea un itinerario di 3–5 giorni su misura per budget, stagione, scopo del viaggio e numero di persone. L'itinerario si scarica come file `.md`.

Progetto creato per **Hacktoberfest Hack Day Pisa × GDG Pisa** (sfida *Best Open-Source AI Project*).

## Come funziona

1. L'utente carica fino a 6 foto e sceglie le preferenze.
2. **Riconoscimento:** le foto vengono inviate a Gemma 4, che restituisce i luoghi (nome, città, paese, affidabilità).
3. **Itinerario:** Gemma 4 crea il piano giorno per giorno, usando la Ricerca Google per informazioni aggiornate.
4. L'itinerario viene mostrato nella pagina e si può scaricare in Markdown.

## Modello AI usato

- **Gemma 4** (`gemma-4-26b-a4b-it`), modello open-weight di Google, usato tramite la [Gemini API](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api).
- Licenza / termini del modello: [Gemma Terms of Use](https://ai.google.dev/gemma/terms)
- Funzioni usate: comprensione delle immagini, istruzioni di sistema, Ricerca Google.

## Tecnologie

Python · Flask · google-genai · HTML/CSS/JavaScript

## Come avviarlo

```bash
git clone https://github.com/NOME-UTENTE/NOME-REPO.git
cd NOME-REPO
python -m venv venv
# Windows: venv\Scripts\activate    macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # poi inserisci la tua GEMINI_API_KEY nel file .env
python app.py
```

Apri **http://localhost:8000**.

La chiave API gratuita si ottiene su [Google AI Studio](https://aistudio.google.com/apikey).
Con `MOCK_MODE=1` nel file `.env` l'app funziona con dati di prova, senza chiave.

## Struttura

```
app.py               route del server (pagina, riconoscimento, itinerario, download)
gemini_service.py    chiamate a Gemma 4
prompts.py           testi inviati al modello
markdown_builder.py  costruzione del file .md
templates/index.html pagina web
static/              stile e JavaScript
```

## API

| Metodo | Route | Cosa fa |
|---|---|---|
| GET | `/` | Pagina web |
| GET | `/api/health` | Stato del server |
| POST | `/api/recognize` | Foto → luoghi riconosciuti (JSON) |
| POST | `/api/itinerary` | Luoghi + preferenze → itinerario (Markdown e HTML) |
| POST | `/api/download` | Markdown → file `.md` |

## Team

- Nome Cognome – ruolo
- Nome Cognome – ruolo

## Licenza

[MIT](LICENSE)
