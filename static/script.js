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
    formData.append("days", prefs.days); // serve per capire se i luoghi stanno in un unico viaggio
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

    renderItinerary(result.html);

    const detail = `${destination} · ${prefs.days} ${prefs.days === "1" ? "giorno" : "giorni"} · ${placeNames.length} ${placeNames.length === 1 ? "luogo riconosciuto" : "luoghi riconosciuti"}`;
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

// --- Itinerario a card -----------------------------------------------------------
// Il server manda l'HTML dell'itinerario (stesso contenuto del file .md). Qui lo
// dividiamo per sezioni "##" e lo trasformiamo in card. Si spostano solo nodi già
// sanificati: nessun testo del modello passa da innerHTML costruito a mano.

const SLOT_ICONS = { mattina: "🌅", pomeriggio: "☀️", sera: "🌙" };
const SECTION_TYPES = [
  { test: /^il tuo viaggio/, type: "summary" },
  { test: /^luoghi riconosciuti/, type: "skip" }, // già mostrati sopra, nella sezione dei luoghi
  { test: /^panoramica/, type: "overview", icon: "🧭" },
  { test: /^dove dormire/, type: "info", icon: "🏨" },
  { test: /^come spostarsi/, type: "info", icon: "🚆" },
  { test: /^budget/, type: "budget", icon: "💶" },
  { test: /^consigli/, type: "info", icon: "💡" },
  { test: /^fonti/, type: "info", icon: "🔗" },
];
const SUMMARY_ICONS = { durata: "🗓️", budget: "💶", scopo: "🎯", persone: "👥" };
const SEASON_ICONS = { primavera: "🌸", estate: "☀️", autunno: "🍂", inverno: "❄️" };

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function iconSpan(icon) {
  const span = el("span", "itin-icon", icon);
  span.setAttribute("aria-hidden", "true");
  return span;
}

function renderItinerary(html) {
  const tpl = document.createElement("template");
  tpl.innerHTML = window.DOMPurify ? DOMPurify.sanitize(html) : html; // HTML già reso sicuro dal server
  const nodes = [...tpl.content.children];

  // Il "---" finale separa la nota "orari indicativi"; altri "---" scritti dal modello si ignorano
  const lastHr = nodes.map((n) => n.tagName).lastIndexOf("HR");
  const hasH2After = lastHr >= 0 && nodes.slice(lastHr).some((n) => n.tagName === "H2");
  const outro = lastHr >= 0 && !hasH2After ? nodes.slice(lastHr + 1) : [];
  const main = (lastHr >= 0 && !hasH2After ? nodes.slice(0, lastHr) : nodes).filter((n) => n.tagName !== "HR");

  const intro = [];
  const sections = [];
  for (const node of main) {
    if (node.tagName === "H2") sections.push({ heading: node, body: [] });
    else if (sections.length) sections.at(-1).body.push(node);
    else intro.push(node);
  }

  // Formato inatteso: mostriamo l'HTML così com'è
  if (!sections.length) {
    itineraryEl.replaceChildren(tpl.content);
    return;
  }

  const header = el("header", "itin-header");
  const days = [];
  const others = [];
  let overview = null;

  for (const node of intro) {
    if (node.tagName === "H1") {
      header.append(el("p", "itin-title", node.textContent.replace(/^Itinerario:\s*/i, "")));
    } else if (node.tagName === "BLOCKQUOTE") {
      header.append(el("p", "itin-meta", node.textContent.trim()));
    }
  }

  for (const section of sections) {
    const title = section.heading.textContent.trim();
    const dayMatch = title.match(/^giorno\s*(\d+)\s*[–—:\-.]?\s*(.*)$/i);
    if (dayMatch) {
      days.push(buildDayCard(Number(dayMatch[1]), dayMatch[2] || "", section.body));
      continue;
    }
    const kind = SECTION_TYPES.find((s) => s.test.test(title.toLowerCase())) || { type: "info", icon: "📌" };
    if (kind.type === "skip") continue;
    if (kind.type === "summary") {
      header.append(...buildSummary(section.body));
      continue;
    }
    const card = buildInfoCard(title, kind, section.body);
    if (kind.type === "overview") overview = card;
    else others.push(card);
  }

  const parts = [header];
  if (days.length > 1) parts.push(buildDayNav(days));
  if (overview) parts.push(overview);
  if (days.length) {
    const list = el("div", "day-list");
    list.append(...days);
    parts.push(list);
  }
  if (others.length) {
    const grid = el("div", "itin-grid");
    grid.append(...others);
    parts.push(grid);
  }
  if (outro.length) {
    const note = el("p", "itin-disclaimer");
    note.append(iconSpan("ℹ️"), " ", outro.map((n) => n.textContent.trim()).join(" "));
    parts.push(note);
  }
  itineraryEl.replaceChildren(...parts);
}

// "Il tuo viaggio" (tabella Voce | Scelta) → pillole con icona + eventuale riga delle note
function buildSummary(body) {
  const chips = el("ul", "itin-chips");
  chips.setAttribute("aria-label", "Le tue scelte");
  let notes = null;
  for (const row of body.flatMap((n) => [...n.querySelectorAll("tbody tr")])) {
    const [label, value] = [...row.cells].map((c) => c.textContent.trim());
    if (!label || !value) continue;
    const key = label.toLowerCase();
    if (key === "note") {
      notes = el("p", "itin-notes");
      notes.append(iconSpan("📝"), " ", el("strong", null, "Note: "), value);
      continue;
    }
    const icon = key === "periodo" ? SEASON_ICONS[value.toLowerCase()] || "📅" : SUMMARY_ICONS[key] || "•";
    const chip = el("li", "itin-chip");
    chip.append(iconSpan(icon), el("span", "visually-hidden", `${label}: `), value);
    if (key === "persone") chip.lastChild.textContent = `${value} ${value === "1" ? "persona" : "persone"}`;
    chip.title = label;
    chips.append(chip);
  }
  return notes ? [chips, notes] : [chips];
}

function buildDayNav(days) {
  const nav = el("nav", "day-nav");
  nav.setAttribute("aria-label", "Vai al giorno");
  const list = el("ul");
  for (const day of days) {
    const li = el("li");
    const link = el("a", null, `G${day.dataset.day}`);
    link.href = `#${day.id}`;
    link.setAttribute("aria-label", `Giorno ${day.dataset.day}: ${day.dataset.title}`);
    link.title = day.dataset.title;
    link.addEventListener("click", (e) => {
      e.preventDefault();
      day.scrollIntoView({ behavior: "smooth", block: "start" });
      day.focus({ preventScroll: true });
    });
    li.append(link);
    list.append(li);
  }
  nav.append(list);
  return nav;
}

function buildDayCard(number, title, body) {
  const card = el("article", "itin-card day-card");
  card.id = `giorno-${number}`;
  card.tabIndex = -1; // può ricevere il focus dalla barra dei giorni
  card.dataset.day = number;
  card.dataset.title = title || `Giorno ${number}`;

  const head = el("header", "day-head");
  const heading = el("h3", null);
  heading.id = `giorno-${number}-titolo`;
  heading.append(el("span", "day-badge", `Giorno ${number}`), el("span", "day-title", title));
  card.setAttribute("aria-labelledby", heading.id);
  head.append(heading);
  card.append(head);

  // Divide il giorno in fasce (### Mattina / Pomeriggio / Sera)
  const slots = [];
  const loose = [];
  for (const node of body) {
    if (node.tagName === "H3") slots.push({ label: node.textContent.trim(), nodes: [] });
    else if (slots.length) slots.at(-1).nodes.push(node);
    else loose.push(node);
  }

  const container = el("div", slots.length ? "day-slots" : "day-body");
  if (loose.length) {
    const intro = el("div", "day-intro");
    intro.append(...loose);
    container.append(intro);
  }
  for (const slot of slots) {
    const key = slot.label.toLowerCase();
    const box = el("section", `slot slot-${SLOT_ICONS[key] ? key : "altro"}`);
    const h = el("h4");
    h.append(iconSpan(SLOT_ICONS[key] || "📍"), " ", slot.label);
    box.append(h, ...slot.nodes);
    container.append(box);
  }
  card.append(container);

  const moves = extractMoves(container);
  if (moves.length) {
    const foot = el("footer", "day-moves");
    foot.append(iconSpan("🚆"), el("strong", null, "Spostamenti"));
    const list = el("ul");
    moves.forEach((m) => {
      const li = el("li");
      li.append(m);
      list.append(li);
    });
    foot.append(list);
    card.append(foot);
  }
  return card;
}

// Sposta le frasi "Spostamento: ..." scritte dal modello in fondo alla card
function extractMoves(container) {
  const moves = [];
  for (let guard = 0; guard < 10; guard++) {
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    let found = null;
    let index = -1;
    while (walker.nextNode()) {
      index = walker.currentNode.data.search(/Spostament[oi]\s*:/i);
      if (index !== -1) { found = walker.currentNode; break; }
    }
    if (!found) break;
    const block = found.parentElement.closest("p, li");
    if (!block) break;
    const rest = found.splitText(index);
    let start = rest;
    while (start.parentNode !== block) start = start.parentNode;
    const frag = document.createDocumentFragment();
    for (let cur = start; cur; ) {
      const next = cur.nextSibling;
      frag.append(cur);
      cur = next;
    }
    // Toglie l'etichetta "Spostamento:" (anche se era in grassetto)
    const first = document.createTreeWalker(frag, NodeFilter.SHOW_TEXT);
    while (first.nextNode()) {
      const t = first.currentNode;
      if (/Spostament[oi]\s*:/i.test(t.data)) { t.data = t.data.replace(/^\s*Spostament[oi]\s*:\s*/i, ""); break; }
    }
    if (!block.textContent.trim()) block.remove();
    if (frag.textContent.trim()) moves.push(frag);
  }
  return moves;
}

function buildInfoCard(title, kind, body) {
  const card = el("section", `itin-card info-card info-${kind.type}`);
  const heading = el("h3");
  heading.append(iconSpan(kind.icon), " ", title);
  const id = `sezione-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  heading.id = id;
  card.setAttribute("aria-labelledby", id);
  card.append(heading);

  for (const node of body) {
    if (node.tagName === "TABLE") {
      // Tabella scorrevole anche da tastiera; la riga "Totale" viene evidenziata
      const wrap = el("div", "table-scroll");
      wrap.tabIndex = 0;
      wrap.setAttribute("role", "region");
      wrap.setAttribute("aria-label", title);
      node.querySelectorAll("tbody tr").forEach((tr) => {
        if (/totale/i.test(tr.cells[0]?.textContent || "")) tr.classList.add("total-row");
      });
      wrap.append(node);
      card.append(wrap);
    } else {
      card.append(node);
    }
  }
  return card;
}

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
    notes: f.notes ? f.notes.value.trim() : "",
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
