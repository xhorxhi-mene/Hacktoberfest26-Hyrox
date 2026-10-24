# 📘 Documentazione del progetto 

## 📸 Pics Travel Planner

Carica le foto di luoghi, monumenti e piatti tipici: **Gemma 4** riconosce dove si trovano e crea un itinerario su misura per budget, stagione, scopo del viaggio, durata e numero di persone. 

Progetto creato per **Hacktoberfest Hack Day Pisa × GDG Pisa** (sfida *Best Use of Gemma4*).

### 🚀 Come funziona

1. **Foto e preferenze:** l'utente carica fino a 6 foto (JPG, PNG, WEBP o HEIC dell'iPhone, max 10 MB ciascuna) e sceglie:
   - durata: in giorni;
   - budget: basso, medio o alto;
   - periodo: primavera, estate, autonno o inverno;
   - scopo: divertimento, cultura o mix;
   - persone: da 1 a 10;
   - note libere (facoltative).
2. **Riconoscimento:** Gemma 4 analizza le foto e restituisce per ognuna il luogo, la città, il paese, il tipo (monumento, paesaggio, cibo, evento) e l'affidabilità.
3. **Controllo:** l'utente vede i luoghi riconosciuti, se nessun luogo viene riconosciuto o i luoghi sono troppo distanti, l'app lo segnala.
4. **Itinerario:** Gemma 4 crea il piano giorno per giorno (mattina, pomeriggio, sera), con alloggi, spostamenti, budget stimato e consigli. Usa la **Ricerca Google** per orari e prezzi aggiornati.
5. **Modifiche:** l'utente può chiedere cambiamenti in linguaggio naturale, per esempio "rendilo più economico" o "aggiungi più musei". Gemma riscrive l'itinerario cambiando solo ciò che serve.
6. **Download:** l'itinerario finale si scarica come file Markdown.

### 🧠 Modello AI usato

- **Gemma 4** (`gemma-4-26b-a4b-it`; in alternativa `gemma-4-31b-it`), modello open-weight di Google, usato tramite la [Gemini API](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api).
- Licenza / termini del modello: [Gemma Terms of Use](https://ai.google.dev/gemma/terms)
- Funzioni usate: comprensione delle immagini, istruzioni di sistema, Ricerca Google, ragionamento (facoltativo).

Gemma è usato in tre momenti: **riconoscimento** dei luoghi dalle foto, **creazione** dell'itinerario e **modifica** su richiesta.

### 💻 Tecnologie

Python · Flask · google-genai · Pillow (+ pillow-heif) · Markdown · HTML/CSS/JavaScript

### ▶️ Come avviarlo

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

**Windows:** se PowerShell blocca l'attivazione del venv ("l'esecuzione di script è disabilitata"), puoi:
- avviare direttamente il Python del venv: `venv\Scripts\python.exe app.py`, oppure
- sbloccare gli script solo per la finestra aperta: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, poi `venv\Scripts\activate`.

### 🔧 Configurazione (`.env`)

| Variabile | Default | Significato |
|---|---|---|
| `GEMINI_API_KEY` | — | Chiave di Google AI Studio (non va mai caricata su GitHub) |
| `GEMMA_MODEL` | `gemma-4-26b-a4b-it` | Modello da usare (oppure `gemma-4-31b-it`) |
| `USE_GOOGLE_SEARCH` | `1` | `1` = Gemma usa la Ricerca Google |
| `USE_THINKING` | `0` | `1` = ragionamento attivo (più lento, a volte più preciso) |
| `MOCK_MODE` | `0` | `1` = dati di prova, nessuna chiamata all'API |
| `RATE_LIMIT_PER_MINUTE` | `20` | Richieste all'AI consentite per IP al minuto |

### 🔒 Affidabilità e sicurezza

- **Foto controllate sul contenuto**, non sull'estensione: un file finto rinominato in `.jpg` viene rifiutato con un messaggio chiaro.
- **Foto preparate prima dell'invio:** rotazione corretta (EXIF), conversione HEIC → JPEG, ridimensionamento a 1024 px. Le immagini enormi vengono bloccate.
- **Risposte di Gemma ripulite:** se il JSON è malformato l'app riprova una volta; tipi e valori non validi vengono corretti; i testi troppo lunghi vengono accorciati.
- **Errori comprensibili:** quota esaurita, chiave non valida, timeout e problemi del servizio diventano messaggi chiari in italiano. I dettagli tecnici finiscono solo nei log del server.
- **Limite di richieste** all'AI per indirizzo IP, per proteggere la quota della chiave.
- **HTML sicuro:** l'HTML eventualmente scritto dal modello non viene mai eseguito nella pagina.
- **Nessun dato salvato:** il server non conserva foto né itinerari; ogni richiesta contiene tutto il contesto.

### 📂 Struttura

```
app.py               route del server, controlli e gestione degli errori
gemini_service.py    chiamate a Gemma 4 (riconoscimento, itinerario, modifica) ed errori leggibili
prompts.py           testi inviati al modello e dati di prova per MOCK_MODE
validation.py        controllo delle preferenze, dei luoghi e delle richieste di modifica
image_utils.py       verifica delle foto, conversione HEIC, rotazione e ridimensionamento
rate_limit.py        limite di richieste all'AI per IP
markdown_builder.py  costruzione del file .md e della versione HTML sicura
templates/index.html pagina web
static/              stile e JavaScript
```

### 🔌 API

Tutti gli errori hanno la forma `{"error": "messaggio per l'utente"}`.

| Metodo | Route | Cosa fa |
|---|---|---|
| GET | `/` | Pagina web |
| GET | `/api/health` | Stato del server e modello in uso |
| POST | `/api/recognize` | Foto (`multipart`, campo `images`) → luoghi riconosciuti; include `warning` se nessun luogo è stato riconosciuto |
| POST | `/api/itinerary` | Luoghi (anche corretti dall'utente) + preferenze → itinerario (`text`, `markdown`, `html`, `filename`) |
| POST | `/api/modify` | Itinerario attuale + richiesta di modifica (max 300 caratteri) → nuovo itinerario, stessa forma di `/api/itinerary` |
| POST | `/api/download` | Markdown → file `.md` da scaricare |


---

### 📄 Licenza

[MIT](LICENSE)
