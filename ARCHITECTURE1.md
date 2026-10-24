# 🏗️ Architettura e Flusso di Funzionamento - Hacktoberfest26-Hyrox

Questo documento descrive l'architettura interna, la struttura dei moduli e il flusso delle chiamate API del progetto.

## 1. 🔭 Panoramica del Sistema
Il progetto è un'applicazione web full-stack. Il backend è sviluppato in Python utilizzando il framework **Flask**, mentre il frontend utilizza standard web (HTML, CSS, JS). L'applicazione interagisce con un'API esterna (Google Gemini) per elaborare richieste e generare risposte (testuali e basate su immagini), formattandole poi in Markdown.

## 2. 🧩 Struttura dei Componenti Interni

### 🐍 Backend (Python / Flask)
*   **`app.py`**: È il cuore dell'applicazione (Controller). Espone le rotte HTTP (es. `/`, `/api/generate`), riceve le richieste dal frontend, coordina gli altri moduli e restituisce le risposte.
*   **`gemini_service.py`**: Gestisce l'integrazione con l'API esterna di Google Gemini. Si occupa di autenticarsi, inviare i payload corretti e ricevere le risposte del modello AI.
*   **`prompts.py`**: Contiene i "system prompt" e i template di testo predefiniti. Separa la logica del codice dal comportamento dell'intelligenza artificiale.
*   **`image_utils.py`**: Modulo di utilità per la gestione delle immagini. Probabilmente si occupa di validare, ridimensionare o codificare in Base64 le immagini caricate dall'utente prima di inviarle a Gemini (che supporta input multimodali).
*   **`validation.py`**: Contiene la logica per validare gli input dell'utente (testo, formati file, grandezza) per garantire sicurezza e prevenire errori prima di elaborare la richiesta.
*   **`rate_limit.py`**: Implementa un meccanismo di limitazione delle richieste (Rate Limiting) per prevenire abusi (spam, attacchi DDoS) e non superare le quote gratuite dell'API di Gemini.
*   **`markdown_builder.py`**: Modulo dedicato alla formattazione. Prende l'output grezzo fornito da Gemini e lo struttura in Markdown leggibile, pronto per essere renderizzato sul frontend.

### 🎨 Frontend
*   **`templates/index.html`**: L'interfaccia utente principale (UI).
*   **`static/style.css`**: Il foglio di stile per il layout e la grafica.
*   **`static/script.js`**: Gestisce l'interattività lato client, raccoglie i dati dai form, effettua chiamate asincrone (AJAX/Fetch) al backend (`app.py`) e aggiorna il DOM con i risultati.

---

## 3. 🔄 Flusso di Esecuzione Schematico (Come funziona internamente)

Ecco il ciclo di vita di una tipica richiesta dell'utente:

1.  **👤 Interazione Utente (Frontend):**
    *   L'utente inserisce dati (testo, e possibilmente un'immagine) nella pagina `index.html`.
    *   Clicca su "Invia". `script.js` intercetta l'evento.

2.  **📡 Richiesta HTTP (Client -> Server):**
    *   `script.js` raggruppa i dati e fa una chiamata `POST` (probabilmente verso un endpoint come `/api/...` in `app.py`).

3.  **🔒 Sicurezza e Validazione (Backend):**
    *   `app.py` riceve la richiesta.
    *   Chiama `rate_limit.py` per verificare se l'utente può fare la richiesta (es. max 5 richieste al minuto). Se supera il limite, blocca e restituisce errore 429.
    *   Chiama `validation.py` per controllare che i dati siano corretti e sicuri.

4.  **🛠️ Preparazione Dati:**
    *   Se c'è un'immagine, viene passata a `image_utils.py` per l'elaborazione.
    *   Viene recuperato il contesto adeguato da `prompts.py`.

5.  **🤖 Chiamata API Esterna (Backend -> Gemini):**
    *   `app.py` invoca `gemini_service.py`.
    *   `gemini_service.py` crea il payload unendo il prompt, l'input dell'utente e le eventuali immagini, e fa una **chiamata API REST/gRPC ai server di Google Gemini**.
    *   Attende e riceve la risposta generata dall'AI.

6.  **📝 Elaborazione Risposta:**
    *   La risposta grezza di Gemini viene passata a `markdown_builder.py` che la "pulisce" e la formatta con una struttura Markdown predefinita per l'applicazione (es. aggiungendo titoli, liste per gli esercizi Hyrox).

7.  **📤 Risposta HTTP (Server -> Client):**
    *   `app.py` prende il Markdown formattato e lo restituisce come risposta JSON o HTML al frontend.

8.  **🖥️ Aggiornamento UI (Frontend):**
    *   `script.js` riceve la risposta, converte il Markdown in HTML (se non fatto lato server) e lo inietta nella pagina `index.html` per mostrarlo all'utente.
