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
const photoCount = document.getElementById("photo-count");

const MAX_IMAGES = window.MAX_IMAGES || 6;
const MAX_IMAGE_MB = 10;
let selectedFiles = []; // foto scelte finora (si accumulano a ogni "aggiungi")
let photoUrls = [];     // anteprime delle foto, per mostrarle accanto ai luoghi
const urlCache = new Map(); // un solo URL di anteprima per file
let lastResult = null;  // ultimo itinerario generato (per il download)

// --- Scelta delle foto: si aggiungono a quelle già scelte ----------------------
input.addEventListener("change", () => {
  const problems = [];
  for (const file of input.files) {
    const already = selectedFiles.some(
      (f) => f.name === file.name && f.size === file.size && f.lastModified === file.lastModified
    );
    if (already) continue;
    if (file.size > MAX_IMAGE_MB * 1024 * 1024) {
      problems.push(`${file.name} supera ${MAX_IMAGE_MB} MB.`);
      continue;
    }
    if (selectedFiles.length >= MAX_IMAGES) {
      problems.push(`Massimo ${MAX_IMAGES} foto: rimuovine una per aggiungerne altre.`);
      break;
    }
    selectedFiles.push(file);
  }
  input.value = ""; // così si può riscegliere anche lo stesso file dopo averlo rimosso
  showStatus(problems.join(" "), problems.length > 0);
  renderPreviews();
});

function renderPreviews() {
  previews.innerHTML = "";
  photoUrls = selectedFiles.map((file) => {
    if (!urlCache.has(file)) urlCache.set(file, URL.createObjectURL(file));
    return urlCache.get(file);
  });

  photoUrls.forEach((url, i) => {
    const fig = document.createElement("figure");
    const img = document.createElement("img");
    img.src = url;
    img.alt = `Foto ${i + 1}`;
    const cap = document.createElement("figcaption");
    cap.textContent = `Foto ${i + 1}`;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove-photo";
    remove.textContent = "✕";
    remove.title = "Rimuovi questa foto";
    remove.setAttribute("aria-label", `Rimuovi foto ${i + 1}`);
    remove.disabled = submitBtn.disabled;
    remove.addEventListener("click", () => {
      selectedFiles.splice(i, 1);
      showStatus("");
      renderPreviews();
    });
    fig.append(img, remove, cap);
    previews.append(fig);
  });

  photoCount.textContent = selectedFiles.length
    ? `${selectedFiles.length}/${MAX_IMAGES} foto scelte`
    : "";
}

// --- Invio del modulo ---------------------------------------------------------
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const files = selectedFiles.slice(0, MAX_IMAGES);
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
    notes: f.notes ? f.notes.value : "", // campo note disattivato per ora
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
  input.disabled = busy; // niente aggiunte o rimozioni mentre Gemma lavora
  previews.querySelectorAll(".remove-photo").forEach((b) => (b.disabled = busy));
  submitBtn.textContent = busy ? "Attendi…" : "Crea il mio itinerario ✨";
}
