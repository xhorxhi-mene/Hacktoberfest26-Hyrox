// Logica della pagina: scelta foto (clic + drag & drop), chiamate al server, risultati, download.

const form = document.getElementById("trip-form");
const dropzone = document.getElementById("dropzone");
const input = document.getElementById("images");
const previews = document.getElementById("previews");
const photoCount = document.getElementById("photo-count");
const statusEl = document.getElementById("status");
const submitBtn = document.getElementById("submit-btn");
const placesSection = document.getElementById("places-section");
const placesEl = document.getElementById("places");
const countryEl = document.getElementById("country");
const itinerarySection = document.getElementById("itinerary-section");
const itineraryEl = document.getElementById("itinerary");
const downloadBtn = document.getElementById("download-btn");
const journeyStory = document.getElementById("journey-story");
const journeyHeading = document.getElementById("journey-heading");
const journeyDescription = document.getElementById("journey-description");

const MAX_IMAGES = window.MAX_IMAGES || 6;
const MAX_IMAGE_MB = 10;
let selectedFiles = [];       // foto scelte finora: si accumulano a ogni aggiunta
let photoUrls = [];           // anteprime, nello stesso ordine di selectedFiles
const urlCache = new Map();   // un solo URL di anteprima per file
let lastResult = null;        // ultimo itinerario generato (per il download)
let busy = false;

// --- Scelta delle foto (clic + drag & drop): si aggiungono a quelle già scelte ----
["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (e) => {
    e.preventDefault();
    e.stopPropagation();
  });
});
["dragenter", "dragover"].forEach((eventName) => {
  dropzone.addEventListener(eventName, () => !busy && dropzone.classList.add("dragover"));
});
["dragleave", "drop"].forEach((eventName) => {
  dropzone.addEventListener(eventName, () => dropzone.classList.remove("dragover"));
});
dropzone.addEventListener("drop", (e) => {
  if (!busy && e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
});

input.addEventListener("change", () => {
  addFiles(input.files);
  input.value = ""; // così si può riscegliere anche un file appena rimosso
});

function addFiles(fileList) {
  const problems = [];
  for (const file of fileList) {
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
  showStatus(problems.join(" "), problems.length > 0);
  renderPreviews();
}

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
    cap.textContent = `${i + 1}. ${selectedFiles[i].name}`;
    cap.title = selectedFiles[i].name;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove-photo";
    remove.textContent = "✕";
    remove.title = "Rimuovi questa foto";
    remove.setAttribute("aria-label", `Rimuovi foto ${i + 1}`);
    remove.disabled = busy;
    remove.addEventListener("click", () => {
      selectedFiles.splice(i, 1);
      showStatus("");
      renderPreviews();
    });
    fig.append(img, remove, cap);
    previews.append(fig);
  });

  photoCount.textContent = selectedFiles.length ? `${selectedFiles.length}/${MAX_IMAGES} foto scelte` : "";
}

// --- Invio del modulo ---------------------------------------------------------
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const files = selectedFiles.slice(0, MAX_IMAGES);
  if (!files.length) return showStatus("Carica almeno una foto.", true);

  const prefs = readPrefs(); // letto prima di disabilitare i campi
  setBusy(true);
  placesSection.hidden = true;
  itinerarySection.hidden = true;

  try {
    // Passo 1: riconoscimento
    setJourneyStage("searching", "Sto esplorando il mondo", "Le tue foto sono in viaggio: stiamo cercando i luoghi che le hanno ispirate.");
    showStatus("1/2 · Gemma sta riconoscendo i luoghi… 🔍");
    const formData = new FormData();
    files.forEach((file) => formData.append("images", file));
    const recognition = await callApi("/api/recognize", { method: "POST", body: formData });
    renderPlaces(recognition);
    const placeNames = (recognition.places || [])
      .map((place) => place.name)
      .filter((name) => name && name !== "Non riconosciuto");
    const destination = [recognition.region, recognition.country].filter(Boolean).join(", ")
      || placeNames.slice(0, 2).join(", ")
      || "La tua destinazione";
    setJourneyStage("found", "Destinazione individuata", destination);

    // Passo 2: itinerario
    showStatus("2/2 · Gemma sta creando l'itinerario (può richiedere fino a un minuto)… ✍️");
    const result = await callApi("/api/itinerary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recognition, prefs }),
    });
    lastResult = result;

    // Il server rende già sicuro l'HTML; DOMPurify è una protezione in più (se il CDN è raggiungibile)
    itineraryEl.innerHTML = window.DOMPurify ? DOMPurify.sanitize(result.html) : result.html;
    itineraryEl.querySelectorAll("h2, h3").forEach((heading) => {
      if (/^giorno\s+\d+\b/i.test(heading.textContent.trim())) heading.prepend("📅 ");
    });

    const detail = `${destination} · ${prefs.days} giorni · ${placeNames.length} ${placeNames.length === 1 ? "luogo riconosciuto" : "luoghi riconosciuti"}`;
    setJourneyStage("result", "Itinerario pronto", detail);

    itinerarySection.hidden = false;
    setTimeout(() => itinerarySection.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
    showStatus("Fatto! Il tuo itinerario è pronto. ✅");
  } catch (err) {
    setJourneyStage("error", "Ricerca interrotta", "Non siamo riusciti a completare questo passaggio: leggi il messaggio sotto il pulsante.");
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
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
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
    notes: f.notes ? f.notes.value.trim() : "", // campo note disattivato per ora
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
      img.alt = place.name || "Luogo";
      img.loading = "lazy";
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
    conf.textContent = `Affidabilità: ${place.confidence || "?"}`;

    body.append(title, where, desc, conf);
    card.append(body);
    placesEl.append(card);
  });
  placesSection.hidden = false;
}

function showStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.className = isError ? "status error" : "status";
}

function setBusy(value) {
  busy = value;
  submitBtn.disabled = value;
  // Niente modifiche a campi e foto mentre Gemma lavora
  form.querySelectorAll("input, select, textarea, .remove-photo").forEach((el) => (el.disabled = value));
  submitBtn.textContent = value ? "Elaborazione in corso... ⏳" : "Crea il mio itinerario ✨";
}

// --- Velocità del globo e dell'aeroplanino ------------------------------------------
// Velocità per ogni fase (1 = normale). Il cambio è graduale: niente scatti.
const MOTION_SPEED = { idle: 1, searching: 3.5, found: 1, result: 1, error: 0.6 };
let motionSpeed = 1;
let motionFrame = null;

function motionAnimations() {
  return [".globe-land-track", ".story-plane", ".story-orbit-two"]
    .flatMap((sel) => [...journeyStory.querySelectorAll(sel)])
    .flatMap((el) => (el.getAnimations ? el.getAnimations() : []));
}

function setMotionSpeed(target, duration = 900) {
  cancelAnimationFrame(motionFrame);
  const start = motionSpeed;
  const t0 = performance.now();
  const step = (now) => {
    const k = Math.min(1, (now - t0) / duration);
    const eased = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2; // accelera e frena dolcemente
    motionSpeed = start + (target - start) * eased;
    // Cambiare playbackRate mantiene la posizione attuale dell'animazione
    motionAnimations().forEach((anim) => (anim.playbackRate = motionSpeed));
    if (k < 1) motionFrame = requestAnimationFrame(step);
  };
  motionFrame = requestAnimationFrame(step);
}

function setJourneyStage(stage, heading, description) {
  const order = ["searching", "found", "result"];
  setMotionSpeed(MOTION_SPEED[stage] ?? 1);
  journeyStory.dataset.stage = stage;
  journeyHeading.textContent = heading;
  journeyDescription.textContent = description;
  journeyStory.querySelectorAll("[data-story-step]").forEach((step) => {
    const stepIndex = order.indexOf(step.dataset.storyStep);
    const currentIndex = order.indexOf(stage);
    step.classList.toggle("is-active", stepIndex === currentIndex);
    step.classList.toggle("is-complete", currentIndex > stepIndex);
  });
}
