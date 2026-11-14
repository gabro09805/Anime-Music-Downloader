"use strict";

const form = document.querySelector("#search-form");
const searchButton = document.querySelector("#search-button");
const downloadButton = document.querySelector("#download");
const selectAll = document.querySelector("#select-all");
const results = document.querySelector("#results");
const count = document.querySelector("#count");
const status = document.querySelector("#status");
const errors = document.querySelector("#errors");
const header = document.querySelector("#result-header");
const collator = new Intl.Collator("it", {numeric: true, sensitivity: "base"});
const optionsDialog = document.querySelector("#options-dialog");
const optionsButton = document.querySelector("#options-button");
const optionsForm = document.querySelector("#options-form");
const outputFormat = document.querySelector("#output-format");
const filenameTemplate = document.querySelector("#filename-template");
const animeLanguage = document.querySelector("#anime-language");
const optionsError = document.querySelector("#options-error");
const saveOptions = document.querySelector("#save-options");
const cancelOptions = document.querySelector("#cancel-options");
const storageKey = "animeMusicOutputOptions";
let options = {format: "originale", template: "{artista} - {titolo}", language: "EN"};
let busy = false;
let sortColumn = null;
let sortAscending = true;

const columns = [
  {key:"info", label:"Info", action:true, visible:true},
  {key:"row", label:"Row Number", value:(s, i) => i + 1},
  {key:"annId", label:"ANN ID", value:s => s.details.annId},
  {key:"annSongId", label:"ANN Song ID", value:s => s.id},
  {key:"amqSongId", label:"AMQ Song ID", value:s => s.details.amqSongId},
  {key:"lists", label:"Anime Lists", action:true},
  {key:"season", label:"Season", value:s => s.season, visible:true},
  {key:"year", label:"Anno", value:s => s.year, visible:true},
  {key:"animeType", label:"Anime Type", value:s => s.details.animeType},
  {key:"anime", label:"Anime", value:s => animeName(s), visible:true},
  {key:"broadcast", label:"Broadcast", value:s => broadcast(s.details)},
  {key:"type", label:"Song Type", value:s => s.type, visible:true},
  {key:"performance", label:"Performance", value:s => s.details.songCategory},
  {key:"title", label:"Song Name", value:s => s.title, visible:true},
  {key:"artist", label:"Artist", value:s => s.artist, visible:true},
  {key:"composer", label:"Composer", value:s => s.details.songComposer},
  {key:"arranger", label:"Arranger", value:s => s.details.songArranger},
  {key:"difficulty", label:"Difficulty", value:s => s.details.songDifficulty},
  {key:"length", label:"Length", value:s => s.details.songLength},
  {key:"links", label:"Song Links", action:true},
  {key:"source", label:"Sorgente", value:s => s.source || "Non disponibile", visible:true},
  {key:"play", label:"Play Audio", action:true}
];
const columnsKey = "animeMusicColumns";
const columnOrderKey = "animeMusicColumnOrder";
let visibleColumns = new Set(columns.filter(column => column.visible).map(column => column.key));
let songsByRow = new WeakMap();
try {
  const saved = localStorage.getItem(columnsKey);
  if (saved !== null) {
    const parsed = JSON.parse(saved);
    if (!Array.isArray(parsed) || parsed.some(key => typeof key !== "string" || !columns.some(c => c.key === key))) {
      throw new Error("Elenco colonne non valido.");
    }
    visibleColumns = new Set(parsed);
  }
} catch (error) {
  errors.textContent = `Impossibile leggere le colonne salvate: ${error.message}`;
}
try {
  const saved = localStorage.getItem(columnOrderKey);
  if (saved !== null) {
    const order = JSON.parse(saved);
    if (!Array.isArray(order) || order.some(key => typeof key !== "string") || new Set(order).size !== order.length) {
      throw new Error("Ordine delle colonne non valido.");
    }
    const byKey = new Map(columns.map(column => [column.key, column]));
    const restored = order.map(key => byKey.get(key)).filter(Boolean);
    const included = new Set(restored.map(column => column.key));
    columns.splice(0, columns.length, ...restored, ...columns.filter(column => !included.has(column.key)));
  }
} catch (error) {
  errors.textContent = `Impossibile leggere l'ordine delle colonne: ${error.message}`;
}

function animeName(song) {
  const data = song.details;
  return options.language === "JP" ? data.animeJPName || data.animeENName || "" : data.animeENName || data.animeJPName || "";
}

function broadcast(song) {
  return song.isDub && song.isRebroadcast ? "Dub/Rebroadcast" : song.isDub ? "Dub" : song.isRebroadcast ? "Rebroadcast" : "Normal";
}

function mediaUrl(value) {
  if (typeof value !== "string" || !value.trim()) return "";
  const clean = value.trim();
  if (/^https:\/\//i.test(clean)) {
    try {
      const url = new URL(clean);
      return url.protocol === "https:" && !url.username && !url.password ? url.href : "";
    } catch { return ""; }
  }
  if (clean.includes("..") || /[\/\\]/.test(clean) || clean.includes(":")) return "";
  return `https://nawdist.animemusicquiz.com/${encodeURIComponent(clean)}`;
}

function addLink(container, label, url) {
  if (!url) return;
  const link = document.createElement("a");
  link.textContent = label;
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  container.append(link, document.createTextNode(" "));
}

function listLinks(container, song) {
  const ids = song.details.linked_ids || {};
  const sites = [
    ["ANN", song.details.annId, "https://www.animenewsnetwork.com/encyclopedia/anime.php?id="],
    ["MAL", ids.myanimelist, "https://myanimelist.net/anime/"],
    ["AniDB", ids.anidb, "https://anidb.net/anime/"],
    ["AniList", ids.anilist, "https://anilist.co/anime/"],
    ["Kitsu", ids.kitsu, "https://kitsu.app/anime/"]
  ];
  for (const [label, id, base] of sites) if (Number.isSafeInteger(id) && id > 0) addLink(container, label, base + id);
}

function mediaLinks(container, song) {
  for (const [label, field] of [["720p", "HQ"], ["480p", "MQ"], ["Audio", "audio"]]) {
    addLink(container, label, mediaUrl(song.details[field]));
  }
}

function creditText(person) {
  if (!person || typeof person !== "object") return "";
  const names = Array.isArray(person.names) ? person.names.filter(name => typeof name === "string").join(" / ") : "";
  const groups = Array.isArray(person.groups) ? person.groups.map(creditText).filter(Boolean).join(", ") : "";
  const members = Array.isArray(person.members) ? person.members.map(creditText).filter(Boolean).join(", ") : "";
  return [names, groups && `Gruppi: ${groups}`, members && `Membri: ${members}`].filter(Boolean).join(" — ");
}

function actionButton(label, callback) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "row-action";
  button.textContent = label;
  button.addEventListener("click", callback);
  return button;
}

function playSong(song) {
  const url = mediaUrl(song.details.audio || song.details.MQ || song.details.HQ);
  if (!url) { errors.textContent = "Nessun file riproducibile disponibile."; return; }
  const player = document.querySelector("#audio-player");
  player.hidden = false;
  player.src = url;
  player.play().catch(error => { errors.textContent = `Riproduzione non riuscita: ${error.message}`; });
}

function showInfo(song) {
  const data = song.details;
  document.querySelector("#info-title").textContent = song.title || "Dettagli traccia";
  const content = document.querySelector("#info-content");
  content.replaceChildren();
  const groups = [
    ["Anime", [["English", data.animeENName], ["Japanese", data.animeJPName],
      ["Alt Title", Array.isArray(data.animeAltName) ? data.animeAltName.join(", ") : ""],
      ["Season", song.season], ["Type", data.animeType], ["Category", data.animeCategory], ["ANN ID", data.annId]]],
    ["Song", [["Song Type", song.type], ["Artist", song.artist], ["Composer", data.songComposer],
      ["Arranger", data.songArranger], ["Difficulty", data.songDifficulty], ["Broadcast", broadcast(data)],
      ["Performance", data.songCategory], ["ANN Song ID", song.id], ["AMQ Song ID", data.amqSongId], ["Length (s)", data.songLength]]]
  ];
  for (const [title, fields] of groups) {
    const group = document.createElement("div"); group.className = "info-group";
    const heading = document.createElement("h3"); heading.textContent = title; group.appendChild(heading);
    const list = document.createElement("dl"); group.appendChild(list);
    for (const [label, value] of fields) {
      const dt = document.createElement("dt"); dt.textContent = label;
      const dd = document.createElement("dd"); dd.textContent = value === null || value === undefined || value === "" ? "—" : String(value);
      list.append(dt, dd);
    }
    content.appendChild(group);
  }
  for (const [title, build] of [["Anime Lists", listLinks], ["Links", mediaLinks]]) {
    const group = document.createElement("div"); group.className = "info-group";
    const heading = document.createElement("h3"); heading.textContent = title;
    const links = document.createElement("p"); build(links, song);
    if (!links.hasChildNodes()) links.textContent = "—";
    group.append(heading, links);
    content.appendChild(group);
  }
  for (const [title, key] of [["Artists", "artists"], ["Composers", "composers"], ["Arrangers", "arrangers"]]) {
    const group = document.createElement("div"); group.className = "info-group";
    const heading = document.createElement("h3"); heading.textContent = title;
    const text = document.createElement("p");
    text.textContent = Array.isArray(data[key]) ? data[key].map(creditText).filter(Boolean).join("; ") || "—" : "—";
    group.append(heading, text);
    content.appendChild(group);
  }
  document.querySelector("#info-dialog").showModal();
}
document.querySelector("#close-info").addEventListener("click", () => document.querySelector("#info-dialog").close());
document.querySelector("#audio-player").addEventListener("error", () => {
  errors.textContent = "Impossibile riprodurre il file audio nel browser.";
});

function buildRow(song, index) {
  const row = document.createElement("tr");
  songsByRow.set(row, song);
  const td = document.createElement("td");
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox"; checkbox.value = song.id;
  checkbox.dataset.available = String(Number.isSafeInteger(song.id) && song.id > 0 && Boolean(song.source));
  checkbox.dataset.title = song.title || "Senza titolo";
  checkbox.disabled = true;
  checkbox.setAttribute("aria-label", `Seleziona ${checkbox.dataset.title}`);
  checkbox.addEventListener("change", updateSelection);
  td.appendChild(checkbox); row.appendChild(td);
  for (const column of columns) {
    const item = document.createElement("td");
    item.hidden = !visibleColumns.has(column.key);
    item.dataset.columnKey = column.key;
    if (column.value) {
      const value = column.value(song, index);
      item.dataset.sortValue = value === null || value === undefined ? "" : String(value);
      item.textContent = item.dataset.sortValue || "—";
    } else if (column.key === "info") item.appendChild(actionButton("Info", () => showInfo(song)));
    else if (column.key === "play") {
      if (song.source) item.appendChild(actionButton("▶", () => playSong(song)));
      else item.textContent = "—";
    } else {
      if (column.key === "lists") listLinks(item, song);
      if (column.key === "links") mediaLinks(item, song);
      if (!item.hasChildNodes()) item.textContent = "—";
    }
    row.appendChild(item);
  }
  return row;
}

function updateAnimeNames() {
  for (const row of results.rows) {
    const item = row.querySelector('[data-column-key="anime"]');
    const name = animeName(songsByRow.get(row));
    item.dataset.sortValue = name; item.textContent = name || "—";
  }
  if (sortColumn === "anime") resetSort();
}

function applyColumns() {
  for (const [index, column] of columns.entries()) {
    header.cells[index + 1].hidden = !visibleColumns.has(column.key);
    for (const row of results.rows) row.cells[index + 1].hidden = !visibleColumns.has(column.key);
  }
  document.querySelector("#columns-button").textContent = `Colonne (${visibleColumns.size}/${columns.length})`;
}

const columnOptions = document.querySelector("#column-options");
const columnOrderError = document.querySelector("#column-order-error");
const columnHeaders = new Map();
const columnControls = new Map();

function moveColumn(key, direction) {
  const index = columns.findIndex(column => column.key === key);
  const target = index + direction;
  if (target < 0 || target >= columns.length) return;
  const next = [...columns];
  [next[index], next[target]] = [next[target], next[index]];
  try {
    localStorage.setItem(columnOrderKey, JSON.stringify(next.map(column => column.key)));
  } catch (error) {
    columnOrderError.textContent = `Impossibile salvare l'ordine delle colonne: ${error.message}`;
    return;
  }
  columnOrderError.textContent = "";
  columns.splice(0, columns.length, ...next);
  for (const column of columns) {
    header.appendChild(columnHeaders.get(column.key));
    columnOptions.appendChild(columnControls.get(column.key).row);
  }
  for (const row of results.rows) {
    const cells = new Map([...row.cells].slice(1).map(item => [item.dataset.columnKey, item]));
    for (const column of columns) row.appendChild(cells.get(column.key));
  }
  updateMoveButtons();
  applyColumns();
  const controls = columnControls.get(key);
  const button = direction < 0 ? controls.up : controls.down;
  (button.disabled ? (direction < 0 ? controls.down : controls.up) : button).focus();
}

function updateMoveButtons() {
  columns.forEach((column, index) => {
    const controls = columnControls.get(column.key);
    controls.up.disabled = index === 0;
    controls.down.disabled = index === columns.length - 1;
  });
}

for (const column of columns) {
  const th = document.createElement("th");
  if (column.value) {
    const button = actionButton(column.label, () => sortResults(column.key));
    button.className = "sort"; button.dataset.column = column.key; th.appendChild(button);
  } else th.textContent = column.label;
  header.appendChild(th);
  columnHeaders.set(column.key, th);
  const row = document.createElement("div"); row.className = "column-option";
  const label = document.createElement("label");
  const checkbox = document.createElement("input"); checkbox.type = "checkbox"; checkbox.checked = visibleColumns.has(column.key);
  checkbox.addEventListener("change", () => {
    const next = new Set(visibleColumns);
    if (checkbox.checked) next.add(column.key); else next.delete(column.key);
    try {
      localStorage.setItem(columnsKey, JSON.stringify([...next]));
      visibleColumns = next;
      applyColumns();
    } catch (error) {
      checkbox.checked = visibleColumns.has(column.key);
      errors.textContent = `Impossibile salvare le colonne: ${error.message}`;
    }
  });
  label.append(checkbox, document.createTextNode(column.label));
  const up = actionButton("↑", () => moveColumn(column.key, -1));
  const down = actionButton("↓", () => moveColumn(column.key, 1));
  up.setAttribute("aria-label", `Sposta ${column.label} verso l'alto`);
  down.setAttribute("aria-label", `Sposta ${column.label} verso il basso`);
  row.append(label, up, down);
  columnOptions.appendChild(row);
  columnControls.set(column.key, {row, up, down});
}
updateMoveButtons();
applyColumns();
document.querySelector("#columns-button").addEventListener("click", () => document.querySelector("#columns-dialog").showModal());
document.querySelector("#close-columns").addEventListener("click", () => document.querySelector("#columns-dialog").close());

const advanced = document.querySelector("#advanced");
document.querySelector("#advanced-button").addEventListener("click", event => {
  advanced.hidden = !advanced.hidden;
  event.currentTarget.setAttribute("aria-expanded", String(!advanced.hidden));
  event.currentTarget.textContent = advanced.hidden ? "Ricerca avanzata" : "Ricerca semplice";
});
advanced.addEventListener("keydown", event => {
  if (event.key === "Enter" && event.target.tagName === "INPUT" && event.target.type !== "checkbox") {
    event.preventDefault();
    form.requestSubmit();
  }
});
const fieldContainer = document.querySelector("#advanced-fields");
for (const name of ["Anime", "Titolo", "Artista", "Compositore"]) {
  const label = document.createElement("label"); label.textContent = name;
  const input = document.createElement("input"); input.type = "search"; input.maxLength = 500; input.dataset.field = name;
  const select = document.createElement("select"); select.dataset.match = name;
  for (const [value, text] of [["partial","Partial Match"], ["exact","Exact Match"], ["partial_case","Partial + Case"], ["exact_case","Exact + Case"]]) {
    const option = document.createElement("option"); option.value = value; option.textContent = text; select.appendChild(option);
  }
  label.append(input, select); fieldContainer.appendChild(label);
}
const filterDefs = [
  ["song_types", "Song Type", [["opening","OP"],["ending","ED"],["insert","INS"]]],
  ["broadcasts", "Broadcast", [["normal","Normal"],["dub","Dubs"],["rebroadcast","Rebroadcasts"]]],
  ["song_categories", "Performance", [["standard","Standard"],["character","Character"],["chanting","Chanting"],["instrumental","Instrumental"]]],
  ["anime_types", "Anime Type", [["tv","TV"],["movie","Movie"],["ova","OVA"],["ona","ONA"],["special","Special"],["other","Other"]]]
];
for (const [group, title, values] of filterDefs) {
  const fieldset = document.createElement("fieldset");
  const legend = document.createElement("legend"); legend.textContent = title; fieldset.appendChild(legend);
  for (const [value, text] of values) {
    const label = document.createElement("label");
    const input = document.createElement("input"); input.type = "checkbox"; input.checked = true; input.value = value; input.dataset.filter = group;
    label.append(input, document.createTextNode(text)); fieldset.appendChild(label);
  }
  document.querySelector("#filter-groups").appendChild(fieldset);
}
function searchPayload() {
  if (advanced.hidden) return {query: document.querySelector("#query").value, category: document.querySelector("#category").value};
  const fields = {};
  for (const input of fieldContainer.querySelectorAll("input")) {
    fields[input.dataset.field] = {text: input.value, mode: fieldContainer.querySelector(`select[data-match="${input.dataset.field}"]`).value};
  }
  const filters = {};
  for (const [group] of filterDefs) {
    filters[group] = [...document.querySelectorAll(`input[data-filter="${group}"]:checked`)].map(input => input.value);
  }
  if (filters.song_categories.includes("standard")) filters.song_categories.push("other");
  filters.season = document.querySelector("#season-range").value;
  filters.difficulty = document.querySelector("#difficulty-range").value;
  const maxOther = document.querySelector("#max-other");
  const groupSize = document.querySelector("#group-size");
  if (!maxOther.value || !maxOther.validity.valid || !groupSize.value || !groupSize.validity.valid) {
    throw new Error("Il numero di artisti e membri deve essere un intero tra 0 e 99.");
  }
  return {advanced: {fields, filters, and_logic: document.querySelector("#and-logic").checked,
    arrangement: document.querySelector("#arrangement").checked, include_no_links: document.querySelector("#include-no-links").checked,
    ignore_duplicate: document.querySelector("#ignore-duplicate").checked,
    max_other_artist: Number(maxOther.value), group_granularity: Number(groupSize.value)}};
}

try {
  const saved = localStorage.getItem(storageKey);
  if (saved !== null) {
    const parsed = JSON.parse(saved);
    if (!parsed || typeof parsed.format !== "string" || typeof parsed.template !== "string" ||
        !["originale", "mp3", "aac"].includes(parsed.format)) {
      throw new Error("Impostazioni salvate non valide.");
    }
    options = {...options, ...parsed, language: parsed.language === "JP" ? "JP" : "EN"};
  }
} catch (error) {
  errors.textContent = `Impossibile leggere le opzioni salvate; vengono usate quelle predefinite: ${error.message}`;
}

optionsButton.addEventListener("click", () => {
  outputFormat.value = options.format;
  filenameTemplate.value = options.template;
  animeLanguage.value = options.language;
  optionsError.textContent = "";
  optionsDialog.showModal();
});

cancelOptions.addEventListener("click", () => optionsDialog.close());
optionsDialog.addEventListener("cancel", event => {
  if (saveOptions.disabled) event.preventDefault();
});
optionsForm.addEventListener("submit", async event => {
  event.preventDefault();
  const next = {format: outputFormat.value, template: filenameTemplate.value, language: animeLanguage.value};
  saveOptions.disabled = true;
  cancelOptions.disabled = true;
  optionsError.textContent = "";
  try {
    await post("/api/options/validate", next);
    localStorage.setItem(storageKey, JSON.stringify(next));
    options = next;
    updateAnimeNames();
    optionsDialog.close();
  } catch (error) {
    optionsError.textContent = `Impossibile salvare le opzioni: ${error.message}`;
  } finally {
    saveOptions.disabled = false;
    cancelOptions.disabled = false;
  }
});

function resetSort() {
  sortColumn = null;
  sortAscending = true;
  header.querySelectorAll(".sort").forEach(button => button.parentElement.removeAttribute("aria-sort"));
}

function sortResults(column) {
  sortAscending = sortColumn === column ? !sortAscending : true;
  sortColumn = column;
  header.querySelectorAll(".sort").forEach(button => {
    if (button.dataset.column === column) {
      button.parentElement.setAttribute("aria-sort", sortAscending ? "ascending" : "descending");
    } else {
      button.parentElement.removeAttribute("aria-sort");
    }
  });
  const index = columns.findIndex(item => item.key === column) + 1;
  const rows = [...results.rows];
  rows.sort((a, b) => {
    const left = a.cells[index].dataset.sortValue;
    const right = b.cells[index].dataset.sortValue;
    if (!left || !right) return left ? -1 : right ? 1 : 0;
    return collator.compare(left, right) * (sortAscending ? 1 : -1);
  });
  results.append(...rows);
}

function choices() {
  return [...results.querySelectorAll('input[type="checkbox"]:not(:disabled)')];
}

function updateSelection() {
  const boxes = choices();
  const selected = boxes.filter(box => box.checked).length;
  selectAll.checked = boxes.length > 0 && selected === boxes.length;
  selectAll.indeterminate = selected > 0 && selected < boxes.length;
  downloadButton.disabled = busy || selected === 0;
  downloadButton.textContent = selected ? `Scarica selezionati (${selected})` : "Scarica selezionati";
}

function setBusy(value) {
  busy = value;
  searchButton.disabled = value;
  optionsButton.disabled = value;
  selectAll.disabled = value;
  results.querySelectorAll('input[type="checkbox"]').forEach(box => {
    box.disabled = value || box.dataset.available !== "true";
  });
  updateSelection();
}

async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Errore HTTP ${response.status}`);
  return data;
}

function cell(row, value) {
  const td = document.createElement("td");
  td.dataset.sortValue = value || "";
  td.textContent = value || "—";
  row.appendChild(td);
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (busy) return;
  setBusy(true);
  status.textContent = "Ricerca in corso...";
  errors.textContent = "";
  try {
    const data = await post("/api/search", {
      ...searchPayload()
    });
    results.replaceChildren();
    resetSort();
    data.songs.forEach((song, index) => results.appendChild(buildRow(song, index)));
    count.textContent = `${data.songs.length} risultati`;
    status.textContent = data.songs.length ? "Seleziona le tracce da scaricare." : "Nessun risultato trovato.";
  } catch (error) {
    status.textContent = "Ricerca non riuscita.";
    errors.textContent = error.message;
  } finally {
    setBusy(false);
  }
});

selectAll.addEventListener("change", () => {
  choices().forEach(box => { box.checked = selectAll.checked; });
  updateSelection();
});

downloadButton.addEventListener("click", async () => {
  if (busy) return;
  const selected = choices().filter(box => box.checked);
  setBusy(true);
  errors.textContent = "";
  const failures = [];
  let completed = 0;
  for (const [index, box] of selected.entries()) {
    status.textContent = `Download ${index + 1}/${selected.length}: ${box.dataset.title}`;
    try {
      await post("/api/download", {id: Number(box.value), ...options});
      box.checked = false;
      completed++;
    } catch (error) {
      failures.push(`${box.dataset.title}: ${error.message}`);
    }
  }
  status.textContent = `Download completati: ${completed}/${selected.length}.`;
  errors.textContent = failures.join("\n");
  setBusy(false);
});
