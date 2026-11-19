const byId = (id) => document.getElementById(id);
const urlField = byId("url");
const goalField = byId("goal");
const elements = byId("elements");
const inspectButton = byId("inspect-button");
const sampleButton = byId("sample");
const suggestButton = byId("suggest");
const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });

let liveInspectionId = null;
let pending = null;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function formatTime(ms) {
  return Number.isFinite(ms) ? number.format(ms) + " ms" : "—";
}

function selectedIds() {
  return Array.from(elements.querySelectorAll("input:checked"), (checkbox) => checkbox.value);
}

function showStatus(id, message = "", tone = "") {
  const status = byId(id);
  status.dataset.tone = tone;
  status.textContent = message;
}

function updateControls() {
  const count = selectedIds().length;
  const hasGoal = Boolean(goalField.value.trim());
  const selection = byId("selection-count");
  selection.textContent = number.format(count) + " selected";
  selection.dataset.active = count > 0;

  inspectButton.disabled = sampleButton.disabled = Boolean(pending);
  urlField.readOnly = goalField.readOnly = byId("element-picker").disabled = Boolean(pending);
  suggestButton.disabled = Boolean(pending) || !liveInspectionId || count === 0 || !hasGoal;
  inspectButton.textContent = pending === "inspect" ? "Inspecting…" : "Inspect page";
  sampleButton.textContent = pending === "sample" ? "Loading sample…" : "Load sample";
  suggestButton.textContent = pending === "assist" ? "Requesting suggestion…" : "Suggest next step";

  let hint = "";
  if (!liveInspectionId) hint = "Run a live inspection to enable suggestions.";
  else if (!elements.children.length) hint = "Inspect a page with selectable elements.";
  else if (!count) hint = "Select one or more inspected elements.";
  else if (!hasGoal) hint = "Enter a testing goal.";
  byId("selection-hint").textContent = hint;
  byId("selection-hint").hidden = !hint;
}

async function readJson(url, payload) {
  const options = payload === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };

  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new Error("Could not reach the server. Check the connection and try again.");
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const message = typeof data?.error === "string" && data.error;
    throw new Error(message || "Request failed (HTTP " + response.status + "). Try again.");
  }
  if (!data || typeof data !== "object") {
    throw new Error("The server returned an unreadable response.");
  }
  return data;
}

async function runTask(task, statusId, waitingMessage, action) {
  if (pending) return;
  pending = task;
  updateControls();
  showStatus(statusId, waitingMessage);
  try {
    await action();
  } catch (error) {
    showStatus(statusId, error.message, "error");
  } finally {
    pending = null;
    updateControls();
  }
}

function renderEvidence(item) {
  const evidence = element("div", null, "evidence");
  const locators = element("div");
  const attributes = element("div");
  locators.append(element("h4", "Candidate locators"));
  attributes.append(element("h4", "Observed attributes"));

  if (item.candidateLocators.length) {
    const list = element("ul");
    for (const locator of item.candidateLocators) {
      const entry = element("li");
      const matches = locator.matchCount;
      const matchLabel = matches == null ? "Unmeasured" : number.format(matches) + (matches === 1 ? " match" : " matches");
      const meta = element("span", locator.strategy + " · " + matchLabel, "locator-meta");
      if (matches != null) meta.dataset.matches = matches;
      const value = locator.name ? locator.value + " " + JSON.stringify(locator.name) : locator.value;
      entry.append(element("code", value), meta);
      list.append(entry);
    }
    locators.append(list);
  } else {
    locators.append(element("p", "No locator candidates."));
  }

  const entries = Object.entries(item.attributes);
  if (entries.length) {
    const list = element("dl");
    for (const [key, value] of entries) {
      const entry = element("div");
      const description = element("dd");
      description.append(element("code", typeof value === "string" ? value : JSON.stringify(value)));
      entry.append(element("dt", key), description);
      list.append(entry);
    }
    attributes.append(list);
  } else {
    attributes.append(element("p", "No attributes captured."));
  }

  evidence.append(locators, attributes);
  return evidence;
}

function renderElement(item, index) {
  const name = item.label || "Unlabeled " + item.role;
  const entry = element("li");
  const row = element("div", null, "element-row");
  const choice = element("label", null, "element-choice");
  const checkbox = element("input");
  checkbox.type = "checkbox";
  checkbox.value = item.id;
  const caption = element("span");
  caption.append(element("strong", name), element("small", item.role + " · " + item.id));
  choice.append(checkbox, caption);

  const evidence = renderEvidence(item);
  evidence.id = "evidence-" + index;
  evidence.hidden = true;
  const toggle = element("button", "Evidence", "evidence-toggle");
  toggle.type = "button";
  toggle.setAttribute("aria-label", "Evidence for " + name + " (" + item.id + ")");
  toggle.setAttribute("aria-controls", evidence.id);
  toggle.setAttribute("aria-expanded", "false");
  toggle.addEventListener("click", () => {
    evidence.hidden = !evidence.hidden;
    toggle.setAttribute("aria-expanded", String(!evidence.hidden));
  });
  row.append(choice, toggle);
  entry.append(row, evidence);
  return entry;
}

function clearSuggestion() {
  byId("result").hidden = true;
  showStatus("assistant-status");
}

function showInspection(data, sample) {
  if (!Array.isArray(data.elements) || typeof data.sourceUrl !== "string" || (!sample && !data.inspectionId)) {
    throw new Error("The server returned an incomplete inspection.");
  }
  const rows = data.elements.map(renderElement);
  const count = rows.length;
  const locatorCount = data.elements.reduce((total, item) => total + item.candidateLocators.length, 0);

  liveInspectionId = sample ? null : data.inspectionId;
  elements.replaceChildren(...rows);
  byId("snapshot").hidden = false;
  byId("snapshot-kind").textContent = sample ? "Sample" : "Live";
  byId("snapshot-kind").dataset.kind = sample ? "sample" : "live";
  byId("source").textContent = data.sourceUrl;
  byId("element-count").textContent = number.format(count);
  byId("locator-count").textContent = number.format(locatorCount);
  byId("inspection-time").textContent = formatTime(data.inspectionTimeMs);
  byId("element-picker").hidden = count === 0;
  byId("element-empty").hidden = count !== 0;
  byId("empty-heading").textContent = "No elements found";
  byId("empty-text").textContent = "The inspection returned no interactive elements for this page.";
  clearSuggestion();
}

function loadInspection(url) {
  const sample = url === undefined;
  return runTask(sample ? "sample" : "inspect", "inspection-status",
    sample ? "Loading sample…" : "Inspecting page…", async () => {
      const data = sample
        ? await readJson("/web/sample-inspection.json")
        : await readJson("/api/inspect", { url });
      showInspection(data, sample);
      showStatus("inspection-status", sample ? "Sample inspection loaded." : "Inspection complete.", "success");
    });
}

function showSuggestion(data) {
  if (typeof data.message !== "string" || typeof data.model !== "string") {
    throw new Error("The server returned an incomplete suggestion.");
  }
  byId("suggestion-text").textContent = data.message;
  byId("model-name").textContent = data.model;
  byId("response-time").textContent = formatTime(data.responseTimeMs);
  byId("input-tokens").textContent = data.inputTokens == null ? "Unavailable" : number.format(data.inputTokens);
  byId("output-tokens").textContent = data.outputTokens == null ? "Unavailable" : number.format(data.outputTokens);
  const hasTokenCounts = data.inputTokens != null || data.outputTokens != null;
  byId("token-estimate").hidden = !data.tokenCountsEstimated || !hasTokenCounts;
  byId("result").hidden = false;
}

sampleButton.addEventListener("click", () => loadInspection());

urlField.addEventListener("input", () => urlField.setCustomValidity(""));
byId("inspect").addEventListener("submit", (event) => {
  event.preventDefault();
  const url = urlField.value.trim();
  if (!/^https?:\/\//i.test(url)) {
    urlField.setCustomValidity("Enter a demo URL beginning with http:// or https://.");
    urlField.reportValidity();
    return;
  }
  loadInspection(url);
});

function updateSelection() {
  clearSuggestion();
  updateControls();
}

elements.addEventListener("change", updateSelection);
goalField.addEventListener("input", updateSelection);
byId("assist").addEventListener("submit", (event) => {
  event.preventDefault();
  if (suggestButton.disabled) return;

  const payload = {
    inspectionId: liveInspectionId,
    elementIds: selectedIds(),
    goal: goalField.value.trim(),
  };
  clearSuggestion();
  runTask("assist", "assistant-status", "Waiting for the model…", async () => {
    showSuggestion(await readJson("/api/assist", payload));
    showStatus("assistant-status", "Suggestion ready.", "success");
  });
});

updateControls();
