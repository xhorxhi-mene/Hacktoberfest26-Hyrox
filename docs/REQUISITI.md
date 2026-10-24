# 📐 Requisiti, casi d'uso e progettazione

Documento di analisi di **Pics Travel Planner**. Per installazione, configurazione e API vedi il [README](../README.md); per il funzionamento interno vedi [ARCHITETTURA.md](ARCHITETTURA.md).

## ⚙️ Requisiti non funzionali

- **NF01)** Le chiavi API devono risiedere esclusivamente sul server (file `.env`) e non essere mai esposte al client.
- **NF02)** I file immagine temporanei caricati sul server devono essere sovrascritti o cancellati per evitare saturazione dello storage.
- **NF03)** Il sistema deve fornire un feedback visivo (stato di caricamento) durante l'attesa della risposta dell'API, che può richiedere diversi secondi.
- **NF04)** Il server non deve salvare foto né itinerari su disco/database; ogni richiesta deve contenere l'intero contesto.

## ✅ Requisiti funzionali (must have)

- **M01)** Il sistema deve accettare fino a 6 immagini (JPG, PNG, WEBP, HEIC), max 10 MB l'una, validandone il reale contenuto (non solo l'estensione), gestendo la rotazione EXIF e ridimensionandole a 1024 px.
- **M02)** Il sistema deve raccogliere i seguenti parametri tramite form:
  - Budget: basso, medio, alto
  - Durata: giorni (da 1 a 10)
  - Stagione: Primavera, Estate, Autunno, Inverno
  - Scopo: Divertimento, Cultura, Mix
  - Numero di persone (da 1 a 10)
  - Note (opzionali, es. esigenze di accessibilità, bambini, disabili)
- **M03)** Il backend deve inoltrare le immagini e i parametri all'API di Google Gemini (modello Gemma 4) per l'identificazione del luogo e la generazione del testo.
- **M04)** L'interfaccia deve estrarre e mostrare a schermo il nome della destinazione identificata.
- **M05)** Il sistema deve generare e forzare il download dell'itinerario in formato Markdown.

## 🔎 Tracciabilità: dove è implementato ogni requisito

| Req. | Implementazione | Verifica (test automatici in `tests/`) | Stato |
|---|---|---|---|
| NF01 | La chiave è letta solo da `gemini_service.py` (variabile d'ambiente da `.env`); nessuna risposta la contiene. `.env` è escluso da Git. | `test_api.py::test_health_non_espone_la_chiave`, `test_api.py::test_pagina_non_contiene_la_chiave` | ✅ |
| NF02 | Le foto sono lette in memoria (`BytesIO`) e mai salvate. Gli upload grandi che Flask/Werkzeug parcheggia in file temporanei vengono cancellati automaticamente a fine richiesta. | `test_images.py` (lavora solo in memoria) | ✅ |
| NF03 | Messaggio di stato (`role="status"`), pulsante "Elaborazione in corso…", campi disabilitati e globo animato che accelera durante la ricerca. | Prova manuale nel browser | ✅ |
| NF04 | Le route sono stateless: `/api/itinerary` e `/api/modify` ricevono luoghi, preferenze e testo a ogni richiesta. Nessun database. | `test_api.py::test_modify_contesto_completo` | ✅ |
| M01 | `image_utils.prepare_image` (contenuto verificato da Pillow, HEIC, EXIF, 1024 px) + controlli in `app.py` (max 6 file, 10 MB). Primo controllo anche nel browser. | `test_images.py`, `test_api.py::test_recognize_*` | ✅ |
| M02 | Form in `templates/index.html`; validazione in `validation.validate_prefs` (note filtrate contro la prompt injection). | `test_validation.py`, `test_api.py::test_itinerary_preferenze_*` | ✅ |
| M03 | `gemini_service.recognize_places` (immagini + durata) e `generate_itinerary` (luoghi + preferenze), modello `gemma-4-26b-a4b-it`. | `test_gemini_service.py` (con un Gemma finto) | ✅ |
| M04 | Sezione "📍 Luoghi riconosciuti" ("Destinazione: …") e pannello del globo ("Destinazione individuata"). | Prova manuale nel browser | ✅ |
| M05 | Pulsante "Scarica .md": il file viene creato nel browser (Blob) con nome `itinerario-<destinazione>-<N>-giorni.md`. `POST /api/download` restituisce lo stesso file con `Content-Disposition: attachment`. | `test_api.py::test_download_*`, prova manuale | ✅ |

## 🎭 Casi d'uso

Attore primario di tutti i casi d'uso: **Utente**.

```
            ┌──────────────────────────── Pics Travel Planner ────────────────────────────┐
            │                                                                             │
  Utente ───┼──▶ CaricamentoImmagini ──▶ ConfigurazionePreferenze ──▶ GeneraItinerario ──▶ ScaricaItinerario
            │                                                                             │
            └─────────────────────────────────────────────────────────────────────────────┘
```

### 🖼️ CaricamentoImmagini

**Precondizioni:** l'utente si trova sulla pagina principale e ha a disposizione i file immagine.

**Flusso principale:**
1. L'utente clicca sull'area "Trascina qui le tue foto oppure clicca per aggiungerle" (oppure vi trascina i file).
2. Il sistema apre la finestra di selezione dei file del dispositivo.
3. L'utente seleziona una o più foto (fino a un massimo di 6, anche in più volte; ogni foto si può rimuovere con ✕).
4. Il sistema verifica che i formati siano JPG, PNG, WEBP o HEIC e che nessun file superi i 10 MB.
5. Il sistema mostra l'anteprima delle immagini (es. miniatura "1. statua-liberta.jpg").

**Postcondizioni:** le immagini sono selezionate e tenute in memoria nel browser; al momento dell'invio il server ne verifica il contenuto, le ridimensiona e le elabora in memoria (non su disco).

**Flusso alternativo 1 — Formato o dimensioni non validi:** al passo 4, se un file non è un'immagine supportata o supera i 10 MB, il sistema non lo aggiunge, mostra un messaggio di errore e chiede di scegliere un file valido. Se un file finto supera il controllo del browser (es. un `.txt` rinominato in `.jpg`), è il server a rifiutarlo con un messaggio chiaro.

### 🧭 ConfigurazionePreferenze

**Precondizioni:** l'utente ha caricato almeno un'immagine (CaricamentoImmagini).

**Flusso principale:**
1. L'utente compila i campi: Budget, Durata (1–10 giorni), Stagione, Scopo, Numero di persone.
2. L'utente può aggiungere note opzionali (es. esigenze di accessibilità, bambini, disabili).
3. L'utente preme "Crea il mio itinerario ✨".
4. Il sistema valida i parametri (es. numero di persone tra 1 e 10, note senza istruzioni per l'AI, link o testo senza senso).
5. I parametri sono pronti per l'invio.

**Postcondizioni:** i parametri sono validati e pronti per la generazione dell'itinerario.

**Flusso alternativo 1 — Valore non valido:** al passo 4, se "Persone" non è un numero tra 1 e 10, il browser mostra un messaggio di validazione e non invia il modulo; il server ricontrolla comunque i valori e risponde con un messaggio chiaro. Lo stesso vale per note non valide.

### 🗺️ GeneraItinerario

**Precondizioni:** almeno un'immagine caricata e preferenze compilate.

**Flusso principale:**
1. L'utente invia i dati.
2. Il sistema trasmette le foto (e la durata) al servizio AI (Gemma 4).
3. Il servizio AI riconosce luoghi e monumenti e verifica che stiano in un unico viaggio della durata scelta.
4. Il servizio AI elabora un itinerario personalizzato incrociando i luoghi con preferenze e note.
5. Il sistema mostra l'itinerario a schermo, organizzato in card.

**Postcondizioni:** l'itinerario è visibile e il pulsante "Scarica .md" è disponibile.

**Flusso alternativo 1 — Immagini non riconoscibili:** al passo 3, se nessun luogo è riconosciuto, il sistema chiede di caricare immagini più nitide o iconiche.

**Flusso alternativo 2 — Luoghi troppo lontani:** al passo 3, se i luoghi non stanno in un viaggio della durata scelta (es. Parigi e Tokyo in 3 giorni), il sistema si ferma e chiede foto della stessa zona o una durata maggiore.

**Flusso alternativo 3 — Timeout o errore API:** al passo 2 o 4, se la comunicazione con Gemma 4 fallisce (quota, chiave, timeout, servizio non disponibile), il sistema interrompe l'attesa e mostra un avviso chiaro, invitando a riprovare.

### 💾 ScaricaItinerario

**Precondizioni:** l'itinerario è stato generato ed è visibile; il pulsante "Scarica .md" è disponibile.

**Flusso principale:**
1. L'utente clicca su "Scarica .md".
2. Il sistema recupera il testo Markdown dell'itinerario.
3. Il sistema crea nel browser un file Blob con il testo.
4. Il sistema assegna un nome coerente al file, basato sulla destinazione e sulla durata (es. `itinerario-lazio-3-giorni.md`).
5. Il sistema avvia il download.

**Postcondizioni:** il file `.md` è salvato sul dispositivo; la pagina resta sui risultati, pronta per una nuova ricerca.

**Flusso alternativo 1 — Download bloccato dal browser:** se il browser impedisce il salvataggio, il sistema mostra un messaggio che spiega come abilitare il download e una casella con il testo Markdown e il pulsante "Copia testo".

## 🏗️ Progettazione architetturale

Il sistema usa un'architettura **service-oriented e stateless** invece del pattern MVC classico. Ogni modulo Python ha un compito preciso:

- **`app.py` (controller di routing):** espone gli endpoint REST Flask, delega la logica ai moduli specializzati e trasforma ogni errore in JSON `{"error": "..."}`.
- **`image_utils.py` (image processor):** verifica il contenuto reale dei file, converte HEIC (Pillow / pillow-heif), corregge l'orientamento EXIF e comprime le immagini per l'API.
- **`gemini_service.py` (AI core service):** wrapper di `google-genai` per Gemma 4; gestisce riconoscimento, generazione e modifica, riprova se il JSON è malformato e usa i dati di prova di `prompts.py` con `MOCK_MODE=1`.
- **`prompts.py` (prompt):** testi inviati al modello e dati di prova.
- **`validation.py` (data validator):** controlla preferenze, luoghi, note e richieste di modifica (limiti, coerenza, prompt injection).
- **`markdown_builder.py` (output formatter):** costruisce il file `.md`, lo converte in HTML sicuro e prepara `{text, markdown, html, filename}` per il client.
- **`rate_limit.py` (security layer):** limita le chiamate all'AI per IP (default 20 al minuto) per proteggere la `GEMINI_API_KEY` da abusi.

## 🧩 Carte CRC

### AppController (`app.py`)
| Responsabilità | Collaboratori |
|---|---|
| Definire e proteggere le route REST (`/api/recognize`, `/api/itinerary`, `/api/modify`, `/api/download`, `/api/health`) | `rate_limit.py` |
| Estrarre i dati dalle richieste HTTP (file del form, JSON) e farli validare | `validation.py` |
| Passare le immagini alla pre-elaborazione | `image_utils.py` |
| Invocare il servizio AI in base all'endpoint | `gemini_service.py` |
| Formattare le risposte di successo o di errore | `markdown_builder.py` |

### GeminiService (`gemini_service.py`)
| Responsabilità | Collaboratori |
|---|---|
| Inizializzare il client `google-genai` e leggere le opzioni (`USE_GOOGLE_SEARCH`, `USE_THINKING`) | `.env` |
| Intercettare `MOCK_MODE=1` e restituire dati di prova invece di chiamare l'API | `prompts.py` |
| Costruire le richieste combinando istruzioni di sistema, immagini e input dell'utente | `prompts.py` |
| Tradurre gli errori dell'API (quota, chiave, timeout, servizio) in messaggi in italiano | — |
| Ripulire e leggere l'output dell'AI (JSON malformato → un nuovo tentativo) | `validation.py` |

### ImageUtils (`image_utils.py`)
| Responsabilità | Collaboratori |
|---|---|
| Verificare il contenuto reale del file per rifiutare i falsi (es. finti `.jpg`) | Pillow (lettura in memoria) |
| Convertire i file HEIC in JPEG | pillow-heif |
| Leggere i dati EXIF e ruotare l'immagine | Pillow |
| Ridimensionare l'immagine (max 1024 px) per ridurre il carico verso l'API | Pillow |

## 🛠️ Correzioni rispetto alla prima versione del documento

- **NF05 vuoto rimosso:** era privo di contenuto.
- **M02:** aggiunte le note; durata indicata come 1–10 giorni, come nell'app.
- **M03:** "API di Google Gemini (modello Gemma 4)" usato ovunque.
- **Limite di 10 MB e formato HEIC** uniformati in tutti i casi d'uso.
- **Flussi alternativi completati** (CaricamentoImmagini) e aggiunto quello dei luoghi troppo lontani (GeneraItinerario).
- **ConfigurazionePreferenze ricostruito** come caso d'uso completo.
- **Refusi corretti:** GeneralItinerario → GeneraItinerario; ScaricalItinerario → ScaricaItinerario.
- **Postcondizioni aggiunte** dove mancavano.
- **Allineamento con l'app reale:** il pulsante "Sfoglia" è l'area di caricamento; il nome del file scaricato segue il formato `itinerario-<destinazione>-<N>-giorni.md`; la sezione README duplicata è stata sostituita da un rimando al [README](../README.md), che è l'unica versione aggiornata.
