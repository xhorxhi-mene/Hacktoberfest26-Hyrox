# 📸 Pics Travel Planner

Carica le foto di luoghi, monumenti e piatti tipici: **Gemma 4** riconosce dove si trovano e crea un itinerario da 1 a 10 giorni su misura per budget, stagione, scopo del viaggio e numero di persone. L'itinerario si legge a card nella pagina e si scarica come file `.md`.

Progetto creato per **Hacktoberfest Hack Day Pisa × GDG Pisa** (sfida *Best Open-Source AI Project*).

## Come funziona

1. **Foto e preferenze:** l'utente aggiunge fino a 6 foto (JPG, PNG, WEBP o HEIC dell'iPhone, max 10 MB ciascuna), una alla volta o trascinandole, e può rimuoverle con ✕. Poi sceglie:
   - durata: da 1 a 10 giorni;
   - budget: basso, medio o alto;
   - periodo: primavera, estate, autunno o inverno;
   - scopo: divertimento, cultura o mix;
   - persone: da 1 a 10;
   - note libere (facoltative, max 300 caratteri), ad esempio «siamo vegetariani».
2. **Riconoscimento:** Gemma 4 analizza le foto e restituisce per ognuna il luogo, la città, il paese, il tipo (monumento, paesaggio, cibo, evento) e l'affidabilità. Valuta anche se i luoghi si possono visitare nella durata scelta: se sono troppo lontani (es. Parigi e Tokyo in 3 giorni) l'app si ferma e spiega perché.
3. **Itinerario:** Gemma 4 crea il piano giorno per giorno (mattina, pomeriggio, sera), con alloggi, spostamenti, budget stimato e consigli, usando la **Ricerca Google** per orari e prezzi aggiornati. Ogni luogo delle foto compare nell'itinerario.
4. **Lettura a card:** riepilogo delle scelte, barra per saltare a un giorno, una card per giorno, card per alloggi, spostamenti, budget e consigli. Funziona anche da telefono e da tastiera.
5. **Download:** l'itinerario si scarica come file Markdown.

Il backend permette anche di **modificare** l'itinerario in linguaggio naturale («rendilo più economico») tramite `POST /api/modify`; la casella nella pagina non è ancora presente.

## Modello AI usato

- **Gemma 4** (`gemma-4-26b-a4b-it`; in alternativa `gemma-4-31b-it`), modello open-weight di Google, usato tramite la [Gemini API](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api).
- Licenza / termini del modello: [Gemma Terms of Use](https://ai.google.dev/gemma/terms)
- Funzioni usate: comprensione delle immagini, istruzioni di sistema, Ricerca Google, ragionamento (facoltativo).

Gemma è usato in tre momenti: **riconoscimento** dei luoghi dalle foto (con la verifica che stiano in un unico viaggio), **creazione** dell'itinerario e **modifica** su richiesta.

## Tecnologie

Python · Flask · google-genai · Pillow (+ pillow-heif) · Markdown · HTML/CSS/JavaScript · DOMPurify

## Come avviarlo

```bash
git clone https://github.com/NOME-UTENTE/NOME-REPO.git
cd NOME-REPO
python -m venv venv
# Windows: venv\Scripts\activate    macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
# copia (non rinominare) il file di esempio e inserisci la tua GEMINI_API_KEY nel nuovo .env
# Windows: copy .env.example .env    macOS/Linux: cp .env.example .env
python app.py
```

Apri **http://localhost:8000**.

La chiave API gratuita si ottiene su [Google AI Studio](https://aistudio.google.com/apikey). Dopo ogni modifica al `.env` riavvia il server.
Con `MOCK_MODE=1` nel file `.env` l'app funziona con dati di prova, senza chiave.
Per controllare la configurazione apri `http://localhost:8000/api/health`: `key_configured` deve essere `true`.

**Windows:** se PowerShell blocca l'attivazione del venv ("l'esecuzione di script è disabilitata"), puoi:
- avviare direttamente il Python del venv: `venv\Scripts\python.exe app.py`, oppure
- sbloccare gli script solo per la finestra aperta: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, poi `venv\Scripts\activate`.

## Test

I test automatici (`pytest`) non usano la vera API: girano senza chiave, senza internet e senza consumare quota.

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Coprono validazione delle preferenze, filtri anti prompt injection, foto (formati, HEIC, EXIF, 1024 px), HTML sicuro, nome del file, errori dell'API tradotti, limite di richieste e tutte le route. La corrispondenza tra requisiti e test è in [docs/REQUISITI.md](docs/REQUISITI.md).

## Configurazione (`.env`)

| Variabile | Default | Significato |
|---|---|---|
| `GEMINI_API_KEY` | — | Chiave di Google AI Studio (non va mai caricata su GitHub) |
| `GEMMA_MODEL` | `gemma-4-26b-a4b-it` | Modello da usare (oppure `gemma-4-31b-it`) |
| `USE_GOOGLE_SEARCH` | `1` | `1` = Gemma usa la Ricerca Google |
| `USE_THINKING` | `0` | `1` = ragionamento attivo (più lento, a volte più preciso) |
| `MOCK_MODE` | `0` | `1` = dati di prova, nessuna chiamata all'API |
| `RATE_LIMIT_PER_MINUTE` | `20` | Richieste all'AI consentite per IP al minuto |
| `TRUST_PROXY` | `0` | `1` solo se il sito è online dietro un proxy (es. Render) |

## Affidabilità e sicurezza

- **Foto controllate sul contenuto**, non sull'estensione: un file finto rinominato in `.jpg` viene rifiutato con un messaggio chiaro.
- **Foto preparate prima dell'invio:** rotazione corretta (EXIF), conversione HEIC → JPEG, ridimensionamento a 1024 px. Le immagini enormi vengono bloccate.
- **Risposte di Gemma ripulite:** se il JSON è malformato l'app riprova una volta; tipi e valori non validi vengono corretti; c'è sempre un luogo per ogni foto, nell'ordine giusto.
- **Protezione da prompt injection:** note, richieste di modifica e nomi dei luoghi vengono controllati. Istruzioni per l'AI («ignora le istruzioni…»), link, caratteri invisibili e testo senza senso vengono rifiutati con un messaggio chiaro. Nel prompt il testo dell'utente è racchiuso in tag e trattato solo come preferenza, mai come ordine.
- **Errori comprensibili:** quota esaurita, chiave mancante o non valida, timeout e problemi del servizio diventano messaggi chiari in italiano. I dettagli tecnici finiscono solo nei log del server.
- **Limite di richieste** all'AI per indirizzo IP, per proteggere la quota della chiave.
- **HTML sicuro:** l'HTML scritto dal modello non viene mai eseguito; sono ammessi solo link `http(s)`, aperti in una nuova scheda. DOMPurify nel browser è una protezione in più.
- **Nessun dato salvato:** il server non conserva foto né itinerari; ogni richiesta contiene tutto il contesto.

## Struttura

```
app.py               route del server, controlli e gestione degli errori
gemini_service.py    chiamate a Gemma 4 (riconoscimento, itinerario, modifica) ed errori leggibili
prompts.py           testi inviati al modello e dati di prova per MOCK_MODE
validation.py        controllo di preferenze, luoghi e testo libero (anti prompt injection)
image_utils.py       verifica delle foto, conversione HEIC, rotazione e ridimensionamento
rate_limit.py        limite di richieste all'AI per IP
markdown_builder.py  costruzione del file .md e della versione HTML sicura
templates/index.html pagina web
static/              stile e JavaScript (scelta foto, animazione, itinerario a card)
tests/               test automatici pytest (Gemma simulato, nessuna chiave necessaria)
docs/                requisiti, casi d'uso, carte CRC e architettura
.env.example         modello del file di configurazione
requirements.txt     librerie per avviare l'app
requirements-dev.txt librerie per lo sviluppo (pytest)
pytest.ini           configurazione dei test
```

Documentazione: [requisiti e casi d'uso](docs/REQUISITI.md) · [architettura e flusso](docs/ARCHITETTURA.md).

## API

Tutti gli errori hanno la forma `{"error": "messaggio per l'utente"}`.

| Metodo | Route | Cosa fa |
|---|---|---|
| GET | `/` | Pagina web |
| GET | `/api/health` | Stato del server, modello in uso e se la chiave è configurata |
| POST | `/api/recognize` | Foto (`multipart`, campo `images`; campo facoltativo `days`) → luoghi riconosciuti; include `warning` se nessun luogo è stato riconosciuto; errore 400 se i luoghi sono troppo lontani per la durata scelta |
| POST | `/api/itinerary` | Luoghi + preferenze → itinerario (`text`, `markdown`, `html`, `filename`) |
| POST | `/api/modify` | Itinerario attuale (`text`) + richiesta di modifica (max 300 caratteri) → nuovo itinerario, stessa forma di `/api/itinerary` |
| POST | `/api/download` | Markdown → file `.md` da scaricare |

## Team

- Nome Cognome – ruolo
- Nome Cognome – ruolo

## Licenza

[MIT](LICENSE)
