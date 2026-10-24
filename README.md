# 📐 Architettura e Requisiti

## ⚙️ Requisiti non funzionali

- **NF01)** Le chiavi API devono risiedere esclusivamente sul server (file `.env`) e non essere mai esposte al client.
- **NF02)** I file immagine temporanei caricati sul server devono essere sovrascritti o cancellati per evitare saturazione dello storage.
- **NF03)** Il sistema deve fornire un feedback visivo (stato di caricamento) durante l'attesa della risposta dell'API, che può richiedere diversi secondi.
- **NF04)** Il server non deve salvare foto né itinerari su disco/database; ogni richiesta deve contenere l'intero contesto.

## ✅ Requisiti funzionali

### 📌 Must have

- **M01)** Il sistema deve accettare fino a 6 immagini (JPG, PNG, WEBP, HEIC), max 10 MB l'una, validandone il reale contenuto (non solo l'estensione), gestendo la rotazione EXIF e ridimensionandole a 1024 px.
- **M02)** Il sistema deve raccogliere i seguenti parametri tramite form:
  - Budget: basso, medio, alto
  - Durata: giorni
  - Stagione: Primavera, Estate, Autunno, Inverno
  - Scopo: Divertimento, Cultura, Mix
  - Numero di persone
  - Note (opzionali, es. esigenze di accessibilità, bambini, disabili)
- **M03)** Il backend deve inoltrare le immagini e i parametri all'API di Google Gemini (modello Gemma 4) per l'identificazione del luogo e la generazione del testo.
- **M04)** L'interfaccia deve estrarre e mostrare a schermo il nome della destinazione identificata.
- **M05)** Il sistema deve generare e forzare il download dell'itinerario in formato Markdown.

---

# 🎭 Casi d'uso

## 🖼️ Use Case: CaricamentoImmagini

**Primary Actor:** Utente

**Preconditions:**
L'utente si trova sulla pagina principale dell'applicazione e ha a disposizione i file immagine da caricare.

**Flow of Events:**
1. L'utente clicca sul pulsante "Sfoglia".
2. Il sistema apre la finestra di selezione dei file del dispositivo locale.
3. L'utente seleziona una o più foto (fino a un massimo di 6).
4. Il sistema verifica che i formati corrispondano a JPG, PNG, WEBP o HEIC e che nessun file superi i 10 MB.
5. Il sistema elabora i file e mostra a schermo l'anteprima delle immagini caricate (es. miniatura "Foto 1" raffigurante la Statua della Libertà).

**Postconditions:**
Le immagini sono state validate, ridimensionate e memorizzate in memoria (non su disco) per la successiva elaborazione.

**Alternative Flow 1 — Formato o dimensioni non validi:**
Al passo 4, se un'immagine non rispetta i vincoli di estensione o supera i 10 MB, il sistema mostra un messaggio di errore e richiede di selezionare un file valido.

---

## 🧭 Use Case: ConfigurazionePreferenze

**Primary Actor:** Utente

**Preconditions:**
L'utente ha caricato con successo almeno un'immagine (UC1).

**Flow of Events:**
1. L'utente compila i campi del form: Budget (basso, medio, alto), Durata (giorni), Stagione (Primavera, Estate, Autunno, Inverno), Scopo (Divertimento, Cultura, Mix), Numero di persone.
2. L'utente può aggiungere note opzionali (es. esigenze di accessibilità, bambini, disabili).
3. L'utente invia i dati (tramite un'azione implicita o la pressione di un pulsante di generazione).
4. Il sistema valida i parametri (es. numero di persone >= 1).
5. Il sistema registra correttamente i parametri nel form e li rende pronti per l'invio.

**Postconditions:**
I parametri sono validati e pronti per la generazione dell'itinerario.

**Alternative Flow 1 — Valore numerico non valido:**
Al passo 4, se il campo "Persone" riceve un input non numerico o inferiore a 1, il sistema ripristina il valore di default o mostra un messaggio di validazione.

**Alternative Flow 2:**
Tutti i parametri del viaggio sono registrati correttamente nel form e pronti per l'invio.

---

## 🗺️ Use Case: GeneraItinerario

**Primary Actor:** Utente

**Preconditions:**
L'utente ha caricato con successo almeno un'immagine (UC1) e compilato i campi obbligatori delle preferenze di viaggio (UC2).

**Flow of Events:**
1. L'utente invia i dati (tramite un'azione implicita o la pressione di un pulsante di generazione).
2. Il sistema trasmette le foto caricate e i parametri di viaggio (Durata, Budget, Periodo, Scopo, Persone, Note) al Servizio AI (Gemma 4).
3. Il Servizio AI analizza le immagini ed esegue il riconoscimento dei posti e dei monumenti.
4. Il Servizio AI elabora un itinerario personalizzato incrociando i luoghi identificati con i filtri e le note forniti dall'utente.
5. Il sistema riceve l'itinerario testuale generato dall'AI e lo renderizza a schermo.

**Postconditions:**
L'itinerario è visualizzato a schermo e il pulsante "Scarica Itinerario (.md)" è abilitato.

**Alternative Flow 1 — Immagini non riconoscibili:**
Al passo 3, se il Servizio AI non riesce a identificare alcun luogo noto nelle foto fornite, il sistema restituisce un messaggio chiedendo all'utente di caricare immagini più chiare o iconiche.

**Alternative Flow 2 — Timeout o errore API:**
Al passo 2 o 4, se la comunicazione con Gemma 4 fallisce, il sistema interrompe l'attesa e mostra un avviso di errore tecnico, invitando a riprovare.

**Alternative Flow 3:**
L'utente visualizza a schermo l'itinerario di viaggio generato su misura dal Servizio AI.

---

## 💾 Use Case: ScaricaItinerario

**Primary Actor:** Utente

**Preconditions:**
Il sistema ha generato con successo l'itinerario (UC3 completato) e il testo è visibile a schermo. Il pulsante "Scarica Itinerario (.md)" è abilitato nell'interfaccia.

**Flow of Events:**
1. L'utente clicca sul pulsante di download.
2. Il sistema recupera il testo in formato Markdown.
3. Il sistema crea un file locale di tipo Blob (Binary Large Object) contenente il testo dell'itinerario.
4. Il sistema assegna un nome coerente al file (es. `Itinerario_Roma_Italia.md`, basato sulla destinazione identificata).
5. Il sistema avvia il download del file sul dispositivo locale dell'utente.

**Postconditions:**
Il file `.md` contenente l'itinerario generato è salvato fisicamente sul dispositivo dell'utente. L'applicazione rimane nello stato di visualizzazione dei risultati, pronta per un'eventuale nuova ricerca.

**Alternative Flow 1 — Blocco download del browser:**
Se il browser dell'utente blocca l'azione di salvataggio file (es. restrizioni di sicurezza o blocco pop-up), il sistema mostra un messaggio di avviso che spiega come abilitare il download, oppure mostra il testo in una casella copiabile manualmente.

---

## 📊 Diagramma dei casi d'uso

*[Nel documento originale è presente un'immagine del diagramma dei casi d'uso. Di seguito la descrizione testuale.]*

**Attore:** Utente

**Casi d'uso collegati:**
- CaricamentoImmagini
- ConfigurazionePreferenze
- GeneraItinerario
- ScaricaItinerario

---

# 🏗️ Progettazione Architetturale (Struttura Modulare Python)

Il sistema abbandona il pattern MVC classico per un'architettura **Service-Oriented e Stateless**, basata sui moduli definiti nel README.

- **`app.py` (Controller di Routing):** espone gli endpoint REST (Flask). Gestisce la ricezione delle richieste, delega la logica ai moduli specializzati e intercetta le eccezioni restituendo JSON formattati `{"error": "..."}`.
- **`image_utils.py` (Image Processor):** gestisce la sicurezza (MIME sniffing), la conversione (Pillow / pillow-heif), la correzione dell'orientamento (EXIF) e la compressione ottimizzata per le API AI.
- **`gemini_service.py` (AI Core Service):** wrapper per `google-genai` (modello Gemma 4). Gestisce le chiamate per riconoscimento, generazione e modifica. Implementa meccanismi di retry per JSON malformati e fallback su `prompts.py` in caso di `MOCK_MODE=1`.
- **`validation.py` (Data Validator):** controlla la validità dei payload in ingresso (limiti di persone, coerenza dei luoghi inviati, lunghezza massima delle note e delle modifiche).
- **`markdown_builder.py` (Output Formatter):** sanifica l'HTML generato dal modello e prepara la struttura dati `{text, markdown, html, filename}` per il client.
- **`rate_limit.py` (Security Layer):** traccia le chiamate per IP (es. 20 req/min) proteggendo la `GEMINI_API_KEY` da abusi.

---

# 🧩 Carte CRC (Class-Responsibility-Collaboration)

## 🧱 Scheda 1: AppController (`app.py`)

| Responsabilità | Collaboratori |
|---|---|
| Definire e proteggere le route REST (`/api/recognize`, `/api/itinerary`, `/api/modify`). | `rate_limit.py` |
| Estrarre dati dalle richieste HTTP (File form, JSON). | `validation.py` |
| Passare le immagini per la pre-elaborazione. | `image_utils.py` |
| Invocare il servizio AI in base all'endpoint. | `gemini_service.py` |
| Raccogliere i risultati e formattare le risposte JSON di errore o successo. | `markdown_builder.py` |

---

## 🤖 Scheda 2: GeminiService (`gemini_service.py`)

| Responsabilità | Collaboratori |
|---|---|
| Inizializzare il client `google-genai` con le flag (`USE_GOOGLE_SEARCH`, `USE_THINKING`). | `.env` |
| Intercettare `MOCK_MODE=1` e restituire dati statici invece di chiamare l'API. | `prompts.py` |
| Costruire i prompt combinando istruzioni di sistema, immagini e input utente. | `prompts.py` |
| Gestire eccezioni specifiche dell'API (Quota, Timeout) traducendole in italiano. | Nessuno |
| Ripulire e parsare l'output AI (es. correzione JSON malformati con retry). | Nessuno |

---

## 🖼️ Scheda 3: ImageUtils (`image_utils.py`)

| Responsabilità | Collaboratori |
|---|---|
| Verificare l'effettivo "magic number" del file per impedire upload nocivi (es. finti `.jpg`). | File System locale (in memoria) |
| Convertire file HEIC in JPEG standard. | `pillow-heif` |
| Leggere i dati EXIF e ruotare l'immagine correttamente. | Pillow (PIL) |
| Ridimensionare l'immagine (es. max 1024 px) riducendo il payload per la Gemini API. | Pillow (PIL) |

---

# 🛠️ Correzioni applicate rispetto al documento originale

1. **NF05 vuoto rimosso**: il requisito non funzionale NF05 era privo di contenuto ed è stato eliminato per non lasciare una voce incompleta.
2. **M02 integrato con le note**: aggiunta la voce "Note (opzionali...)" tra i parametri raccolti dal form, coerentemente con il caso d'uso `GeneraItinerario`.
3. **M03 e modello AI unificati**: indicato "API di Google Gemini (modello Gemma 4)" per allineare M03, il caso d'uso e l'architettura, che citavano rispettivamente "Google Gemini" e "Gemma 4".
4. **Limite di dimensione unificato a 10 MB**: il caso d'uso `CaricamentoImmagini` riportava 5 MB al passo 4 e 10 MB nel flusso alternativo; ora è 10 MB ovunque, come da M01.
5. **Formati immagine allineati a M01**: aggiunto HEIC anche nel caso d'uso `CaricamentoImmagini`.
6. **Flusso alternativo di `CaricamentoImmagini` completato**: la frase interrotta ("...il") è stata terminata con "il sistema mostra un messaggio di errore e richiede di selezionare un file valido."
7. **Titolo e contenuto di `ConfigurazionePreferenze` ricostruiti**: il frammento senza titolo è stato trasformato in un caso d'uso completo, con precondizioni, flusso principale e postcondizioni coerenti con M02.
8. **Refusi nei nomi dei casi d'uso corretti**: `GeneralItinerario` → `GeneraItinerario`; `ScaricalItinerario` → `ScaricaItinerario`.
9. **Postcondizioni mancanti aggiunte**: inserite postcondizioni esplicite per `CaricamentoImmagini`, `GeneraItinerario` e `ScaricaItinerario` (per quest'ultimo, spostando nel campo "Postconditions" quanto già descritto nel flusso alternativo 2).
10. **Coerenza terminologica**: uniformato il riferimento al servizio AI come "Gemma 4" nei casi d'uso e come "Google Gemini (modello Gemma 4)" nei requisiti, mantenendo `gemini_service.py` come wrapper tecnico.

---

# 📘 Documentazione del progetto (README)

## 📸 Photo Travel Planner

Carica le foto di luoghi, monumenti e piatti tipici: **Gemma 4** riconosce dove si trovano e crea un itinerario di 3–5 giorni su misura per budget, stagione, scopo del viaggio e numero di persone. Puoi correggere i luoghi riconosciuti, chiedere modifiche in linguaggio naturale ("rendilo più economico") e scaricare l'itinerario come file `.md`.

Progetto creato per **Hacktoberfest Hack Day Pisa × GDG Pisa** (sfida *Best Open-Source AI Project*).

### 🚀 Come funziona

1. **Foto e preferenze:** l'utente carica fino a 6 foto (JPG, PNG, WEBP o HEIC dell'iPhone, max 10 MB ciascuna) e sceglie:
   - durata: 3, 4 o 5 giorni;
   - budget: basso, medio o alto;
   - periodo: estate o inverno;
   - scopo: divertimento, cultura o mix;
   - persone: da 1 a 10;
   - note libere (facoltative).
2. **Riconoscimento:** Gemma 4 analizza le foto e restituisce per ognuna il luogo, la città, il paese, il tipo (monumento, paesaggio, cibo, evento) e l'affidabilità.
3. **Controllo:** l'utente vede i luoghi riconosciuti e può correggerli prima di continuare. Se nessun luogo viene riconosciuto, l'app lo segnala.
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


### 📄 Licenza

[MIT](LICENSE)
