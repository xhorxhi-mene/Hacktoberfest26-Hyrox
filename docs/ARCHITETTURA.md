# 🏗️ Architettura e flusso di funzionamento

Questo documento descrive l'architettura interna, i moduli e il flusso delle chiamate di **Pics Travel Planner** (repository *Hacktoberfest26-Hyrox*: "Hyrox" è il nome del team). Requisiti e casi d'uso sono in [REQUISITI.md](REQUISITI.md).

## 1. 🔭 Panoramica

Applicazione web full-stack:
- **backend** in Python con **Flask**, senza database e senza stato tra una richiesta e l'altra;
- **frontend** in HTML, CSS e JavaScript, senza framework;
- **AI**: Gemma 4 (`gemma-4-26b-a4b-it`) tramite la Gemini API di Google (libreria `google-genai`), con comprensione delle immagini e Ricerca Google.

```
┌─────────────── BROWSER (templates/index.html + static/) ───────────────┐
│ foto + preferenze ──▶ luoghi riconosciuti ──▶ itinerario a card ──▶ .md │
└──────┬────────────────────────┬───────────────────────────┬────────────┘
       │ POST /api/recognize    │ POST /api/itinerary       │ (POST /api/modify, solo API)
       │ multipart: images,days │ JSON: recognition, prefs  │
       ▼                        ▼                           ▼
┌──────────────────────────── app.py (Flask) ────────────────────────────┐
│ rate_limit ▸ validation ▸ image_utils ▸ gemini_service ▸ markdown_builder│
└──────────────────────────────────┬─────────────────────────────────────┘
                                   ▼
                    Gemini API → gemma-4-26b-a4b-it
                (immagini JPEG, istruzioni di sistema, Ricerca Google)
```

## 2. 🧩 Moduli

### 🐍 Backend
| File | Ruolo |
|---|---|
| `app.py` | Controller: route HTTP, coordinamento dei moduli, gestione centralizzata degli errori (sempre `{"error": "..."}`) |
| `gemini_service.py` | Unico punto di contatto con Gemma 4: riconoscimento, itinerario, modifica; nuovo tentativo se il JSON è malformato; errori tecnici tradotti in messaggi in italiano; dati di prova con `MOCK_MODE=1` |
| `prompts.py` | Istruzioni di sistema e testi inviati al modello; dati di prova |
| `image_utils.py` | Verifica del contenuto reale delle foto, conversione HEIC, rotazione EXIF, ridimensionamento a 1024 px, conversione in JPEG. Tutto in memoria |
| `validation.py` | Validazione delle preferenze, normalizzazione dei luoghi restituiti da Gemma o inviati dalla pagina, filtri contro la prompt injection su note, richieste e nomi dei luoghi |
| `rate_limit.py` | Limite di richieste all'AI per IP (finestra di 60 secondi, default 20) con risposta 429 e `Retry-After` |
| `markdown_builder.py` | Costruisce il file `.md` completo (titolo, riepilogo, luoghi, itinerario, fonti) e lo converte in HTML sicuro: niente HTML del modello, solo link `http(s)`, niente immagini |

### 🎨 Frontend
| File | Ruolo |
|---|---|
| `templates/index.html` | Pagina unica (template Jinja: numero massimo di foto, persone e giorni arrivano dal server) |
| `static/script.js` | Scelta delle foto (clic e trascinamento, aggiunta e rimozione), chiamate al backend, animazione del globo, trasformazione dell'itinerario in card, download del file |
| `static/style.css` | Tema scuro, layout responsive, card, animazioni (disattivate con "riduci movimento") |

### 🧪 Test e documentazione
| Cartella | Contenuto |
|---|---|
| `tests/` | Test automatici `pytest`, girano senza chiave API (Gemma viene simulato) |
| `docs/` | Requisiti, casi d'uso e questa architettura |

## 3. 🔌 Endpoint

| Metodo | Route | Ingresso | Uscita |
|---|---|---|---|
| GET | `/` | — | Pagina web |
| GET | `/api/health` | — | `{ok, mock, model, key_configured}` (la chiave non viene mai mostrata) |
| POST | `/api/recognize` | `multipart`: `images` (1–6 file), `days` (facoltativo) | `{country, region, places[], warning?}` |
| POST | `/api/itinerary` | JSON: `recognition`, `prefs` | `{text, markdown, html, filename}` |
| POST | `/api/modify` | JSON: `recognition`, `prefs`, `text`, `request` | come `/api/itinerary` |
| POST | `/api/download` | JSON: `markdown`, `filename` | file `.md` (`Content-Disposition: attachment`) |

Codici di errore: 400 (dati non validi), 413 (file troppo grandi), 429 (troppe richieste), 500 (configurazione: chiave o modello), 502/503/504 (problemi di Gemma o del servizio Google).

## 4. 🔄 Flusso di una richiesta

1. **Utente (frontend):** aggiunge le foto (il browser scarta subito formati sbagliati e file sopra i 10 MB), sceglie le preferenze e preme "Crea il mio itinerario". Durante l'attesa vede il messaggio di stato, il pulsante "Elaborazione in corso…" e il globo che accelera.

2. **Riconoscimento — `POST /api/recognize`:**
   1. `rate_limit.py` controlla il limite per IP (altrimenti 429).
   2. `app.py` controlla numero (max 6) e dimensione (max 10 MB) dei file.
   3. `image_utils.py` apre ogni file con Pillow per verificarne il contenuto reale, lo ruota secondo i dati EXIF, lo riduce a 1024 px e lo converte in JPEG (byte in memoria, nessun Base64).
   4. `gemini_service.py` invia a Gemma le immagini (`Part.from_bytes`, `image/jpeg`) con il prompt di `prompts.py` e riceve un JSON. Se il JSON è malformato riprova una volta.
   5. `validation.py` normalizza la risposta (un luogo per foto, valori ammessi, testi accorciati) e blocca il flusso con un errore 400 se Gemma indica che i luoghi non stanno in un viaggio della durata scelta.
   6. Se nessun luogo è riconosciuto la risposta contiene `warning`.

3. **Itinerario — `POST /api/itinerary`:**
   1. limite per IP;
   2. `validation.py` normalizza di nuovo i luoghi inviati dalla pagina, li controlla contro la prompt injection e valida le preferenze (note comprese);
   3. `gemini_service.py` chiama Gemma con la Ricerca Google attiva; le note sono racchiuse in un tag e trattate solo come preferenze;
   4. `markdown_builder.py` compone il file `.md` (riepilogo, luoghi, itinerario, fonti) e la sua versione HTML sicura;
   5. `app.py` risponde con `{text, markdown, html, filename}`.

4. **Visualizzazione (frontend):** `script.js` divide l'HTML per sezioni e costruisce le card (riepilogo, barra dei giorni, una card per giorno con mattina/pomeriggio/sera e spostamenti, alloggi, budget, consigli). DOMPurify è una protezione in più.

5. **Download:** `script.js` crea il file `.md` nel browser (Blob) e lo scarica. Se il browser blocca il download, mostra il testo in una casella da copiare. `POST /api/download` offre lo stesso file lato server.

6. **Modifica (solo API, per ora):** `POST /api/modify` riceve il contesto completo (luoghi, preferenze, testo attuale, richiesta) e restituisce l'itinerario riscritto. Il server non ricorda nulla tra una richiesta e l'altra.

## 5. 🔐 Sicurezza in sintesi

- La `GEMINI_API_KEY` sta solo nel `.env` sul server (escluso da Git) e non compare mai nelle risposte.
- Foto verificate sul contenuto; immagini enormi bloccate (max 40 milioni di pixel).
- Prompt injection: filtri su note, richieste e nomi dei luoghi (istruzioni per l'AI, link, caratteri invisibili, testo senza senso) e regola esplicita nelle istruzioni di sistema.
- HTML del modello mai eseguito; solo link `http(s)` aperti in una nuova scheda.
- Limite di richieste per IP; `X-Forwarded-For` considerato solo con `TRUST_PROXY=1`.
- Nessun dato salvato: niente database, niente file su disco.
