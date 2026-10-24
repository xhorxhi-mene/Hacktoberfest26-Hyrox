// Logica della pagina: anteprime, chiamate al server, risultati, download.

const form = document.getElementById("trip-form");
const input = document.getElementById("images");
const previews = document.getElementById("previews");
const statusEl = document.getElementById("status");
const submitBtn = document.getElementById("submit-btn");
const placesSection = document.getElementById("places-section");
const placesEl = document.getElementById("places");
const countryEl = document.getElementById("country");
const itinerarySection = document.getElementById("itinerary-section");
const itineraryEl = document.getElementById("itinerary");
const downloadBtn = document.getElementById("download-btn");

const MAX_IMAGES = window.MAX_IMAGES || 6;
let photoUrls = [];     // anteprime delle foto, per mostrarle accanto ai luoghi
let lastResult = null;  // ultimo itinerario generato (per il download)

// --- Anteprime delle foto ---------------------------------------------------
input.addEventListener("change", () => {
  photoUrls.forEach(URL.revokeObjectURL);
  previews.innerHTML = "";
  const files = [...input.files];
  if (files.length > MAX_IMAGES) {
    showStatus(`Massimo ${MAX_IMAGES} foto: verranno usate solo le prime ${MAX_IMAGES}.`, true);
  } else {
    showStatus("");
  }
  photoUrls = files.slice(0, MAX_IMAGES).map((file) => URL.createObjectURL(file));
  photoUrls.forEach((url, i) => {
    const fig = document.createElement("figure");
    const img = document.createElement("img");
    img.src = url;
    img.alt = `Foto ${i + 1}`;
    const cap = document.createElement("figcaption");
    cap.textContent = `Foto ${i + 1}`;
    fig.append(img, cap);
    previews.append(fig);
  });
});

// --- Invio del modulo ---------------------------------------------------------
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const files = [...input.files].slice(0, MAX_IMAGES);
  if (!files.length) return showStatus("Carica almeno una foto.", true);

  setBusy(true);
  placesSection.hidden = true;
  itinerarySection.hidden = true;

  try {
    // Passo 1: riconoscimento dei luoghi
    showStatus("1/2 · Gemma sta riconoscendo i luoghi…");
    const formData = new FormData();
    files.forEach((file) => formData.append("images", file));
    const recognition = await callApi("/api/recognize", { method: "POST", body: formData });
    renderPlaces(recognition);

    // Passo 2: itinerario
    showStatus("2/2 · Gemma sta creando l'itinerario (può richiedere fino a un minuto)…");
    const result = await callApi("/api/itinerary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recognition, prefs: readPrefs() }),
    });
    lastResult = result;
    itineraryEl.innerHTML = result.html; // HTML già reso sicuro dal server
    itinerarySection.hidden = false;
    itinerarySection.scrollIntoView({ behavior: "smooth" });
    showStatus("Fatto! ✅");
  } catch (err) {
    showStatus(err.message, true);
  } finally {
    setBusy(false);
  }
});

// --- Download del file .md -----------------------------------------------------
downloadBtn.addEventListener("click", async () => {
  if (!lastResult) return;
  try {
    const res = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown: lastResult.markdown, filename: lastResult.filename }),
    });
    if (!res.ok) throw new Error("Download non riuscito");
    const blob = await res.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = lastResult.filename || "itinerario.md";
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (err) {
    showStatus(err.message, true);
  }
});

// --- Funzioni di supporto -----------------------------------------------------
function readPrefs() {
  const f = form.elements;
  return {
    days: f.days.value,
    budget: f.budget.value,
    season: f.season.value,
    purpose: f.purpose.value,
    people: Number(f.people.value),
    notes: f.notes.value,
  };
}

async function callApi(url, options) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Errore del server (${res.status})`);
  return data;
}

function renderPlaces(recognition) {
  placesEl.innerHTML = "";
  const area = [recognition.region, recognition.country].filter(Boolean).join(", ");
  countryEl.textContent = area ? `Destinazione: ${area}` : "";

  (recognition.places || []).forEach((place, i) => {
    const card = document.createElement("div");
    card.className = "place";

    const photo = photoUrls[(place.image || i + 1) - 1];
    if (photo) {
      const img = document.createElement("img");
      img.src = photo;
      img.alt = place.name || "";
      card.append(img);
    }

    const body = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = place.name || "Non riconosciuto";
    const where = document.createElement("p");
    where.className = "muted";
    where.textContent = [place.city, place.country].filter(Boolean).join(", ");
    const desc = document.createElement("p");
    desc.textContent = place.description || "";
    const conf = document.createElement("span");
    conf.className = `conf conf-${place.confidence || "bassa"}`;
    conf.textContent = `affidabilità: ${place.confidence || "?"}`;
    body.append(title, where, desc, conf);

    card.append(body);
    placesEl.append(card);
  });
  placesSection.hidden = false;
}

function showStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function setBusy(busy) {
  submitBtn.disabled = busy;
  submitBtn.textContent = busy ? "Attendi…" : "Crea il mio itinerario ✨";
}
