const byId = (id) => document.getElementById(id);
const urlField = byId("url");
const goalField = byId("goal");
const elements = byId("elements");
const inspectButton = byId("inspect-button");
const reinspectButton = byId("reinspect-button");
const sampleButton = byId("sample");
const scopeTypes = byId("scope-types");
const scopeSelector = byId("scope-selector");
const suggestButton = byId("suggest");
const clarificationForm = byId("clarification-form");
const answerField = byId("clarification-answer");
const refineButton = byId("refine");
const callLog = byId("call-log");
const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
const logTime = new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "medium" });

let liveInspectionId = null;
let pending = null;
let suggestionRequest = null;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function formatTime(ms) {
  return Number.isFinite(ms) ? number.format(ms) + " ms" : "—";
}

function formatTokens(count) {
  return count == null ? "Unavailable" : number.format(count);
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
  reinspectButton.disabled = Boolean(pending) || !liveInspectionId;
  byId("inspection-scope").disabled = Boolean(pending);
  urlField.readOnly = goalField.readOnly = byId("element-picker").disabled = Boolean(pending);
  answerField.readOnly = Boolean(pending);
  suggestButton.disabled = Boolean(pending) || !liveInspectionId || count === 0 || !hasGoal;
  refineButton.disabled = Boolean(pending) || !suggestionRequest || clarificationForm.hidden || !answerField.value.trim();
  inspectButton.textContent = pending === "inspect" ? "Inspecting…" : "Inspect page";
  reinspectButton.textContent = pending === "reinspect" ? "Re-inspecting…" : "Re-inspect";
  sampleButton.textContent = pending === "sample" ? "Loading sample…" : "Load sample";
  suggestButton.textContent = pending === "assist" ? "Requesting suggestion…" : "Suggest next step";
  refineButton.textContent = pending === "refine" ? "Refining…" : "Refine suggestion";

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
  row.dataset.elementId = item.id;
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

function highlightCitedRows(ids) {
  for (const row of elements.querySelectorAll(".element-row")) {
    row.classList.toggle("is-cited", ids.has(row.dataset.elementId));
  }
}

function clearSuggestion() {
  suggestionRequest = null;
  byId("result").hidden = true;
  clarificationForm.hidden = true;
  answerField.value = "";
  highlightCitedRows(new Set());
  showStatus("assistant-status");
  showStatus("clarification-status");
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

function loadInspection(task, payload) {
  const sample = task === "sample";
  const repeat = task === "reinspect";
  const waitingMessage = sample ? "Loading sample…" : repeat ? "Re-inspecting page…" : "Inspecting page…";
  const successMessage = sample ? "Sample inspection loaded." : repeat ? "Re-inspection complete." : "Inspection complete.";
  return runTask(task, "inspection-status", waitingMessage, async () => {
    const data = sample
      ? await readJson("/web/sample-inspection.json")
      : await readJson("/api/inspect", payload);
    showInspection(data, sample);
    showStatus("inspection-status", successMessage, "success");
  });
}

function resultBlock(heading, ...content) {
  const block = element("div", null, "result-block");
  block.append(element("h4", heading), ...content);
  return block;
}

function resultList(items) {
  const list = element("ul");
  for (const item of items) list.append(item);
  return list;
}

function showSuggestion(data, request) {
  if (typeof data.message !== "string" || typeof data.model !== "string") {
    throw new Error("The server returned an incomplete suggestion.");
  }

  const blocks = [];
  const summary = data.summary?.trim();
  const observations = data.observations ?? [];
  const action = data.nextAction?.description?.trim();
  const actionIds = data.nextAction?.elementIds ?? [];
  const assumptions = (data.assumptions ?? []).filter((assumption) => assumption.trim());
  const question = data.clarification?.trim();

  if (summary) blocks.push(resultBlock("Summary", element("p", summary)));
  if (observations.length) {
    const items = observations.map(({ elementId, note }) => {
      const item = element("li");
      item.append(element("code", elementId));
      if (note) item.append(element("span", " — " + note));
      return item;
    });
    blocks.push(resultBlock("Observations", resultList(items)));
  }
  if (action || actionIds.length) {
    const block = resultBlock("Next action");
    if (action) block.append(element("p", action));
    if (actionIds.length) block.append(element("p", "Element IDs: " + actionIds.join(", "), "citation-text"));
    blocks.push(block);
  }
  if (assumptions.length) {
    blocks.push(resultBlock("Assumptions", resultList(assumptions.map((text) => element("li", text)))));
  }
  if (data.message.trim() && (data.outputValid === false || (!blocks.length && !question))) {
    blocks.push(resultBlock("Model reply", element("p", data.message)));
  }

  const citedIds = new Set([
    ...(data.grounding?.referencedElementIds ?? []),
    ...observations.map((observation) => observation.elementId),
    ...actionIds,
  ]);
  const selected = new Set(request.elementIds);
  const citedSelectedIds = new Set([...citedIds].filter((id) => selected.has(id)));
  if (citedSelectedIds.size) {
    blocks.push(element("p", "Cited elements: " + [...citedSelectedIds].join(", "), "citation-text"));
  }
  highlightCitedRows(citedSelectedIds);
  byId("suggestion-blocks").replaceChildren(...blocks);
  byId("suggestion-blocks").hidden = !blocks.length;

  const unknownIds = data.grounding?.unknownElementIds ?? [];
  byId("grounding-warning").hidden = data.grounding?.ok !== false && !unknownIds.length;
  byId("grounding-message").textContent = unknownIds.length
    ? "The model cited elements that were not selected: " + unknownIds.join(", ")
    : "The grounding check flagged the model’s citations.";
  byId("provider-badge").textContent = [data.provider, data.model].filter(Boolean).join(" · ");
  byId("mock-warning").hidden = data.provider !== "mock";
  byId("fallback-warning").hidden = !data.fallbackUsed;
  byId("fallback-reason").textContent = data.fallbackReason ?? "";

  byId("clarification-question").textContent = question ?? "";
  clarificationForm.hidden = !question;
  answerField.value = "";
  showStatus("clarification-status");

  byId("model-name").textContent = data.model;
  byId("response-time").textContent = formatTime(data.responseTimeMs);
  byId("input-tokens").textContent = formatTokens(data.inputTokens);
  byId("output-tokens").textContent = formatTokens(data.outputTokens);
  byId("token-estimate").hidden = !data.tokenCountsEstimated;
  byId("cached-reply").hidden = !data.cached;
  suggestionRequest = request;
  byId("result").hidden = false;
}

async function loadCallLog() {
  const request = suggestionRequest;
  if (!request) return;

  byId("log-content").hidden = true;
  showStatus("log-status", "Loading call log…");
  try {
    const data = await readJson("/api/logs?inspectionId=" + encodeURIComponent(request.inspectionId));
    if (suggestionRequest !== request) return;
    const rows = data.calls.slice(-10).reverse().map((call) => {
      const time = Date.parse(call.loggedAt);
      const row = element("tr");
      const responseTime = formatTime(call.responseTimeMs);
      row.append(
        element("td", Number.isFinite(time) ? logTime.format(time) : "—"),
        element("td", call.provider ?? "—"),
        element("td", call.model ?? "—"),
        element("td", call.cached ? responseTime + " (cached)" : responseTime),
        element("td", formatTokens(call.inputTokens)),
        element("td", formatTokens(call.outputTokens)),
      );
      return row;
    });
    byId("log-rows").replaceChildren(...rows);
    byId("log-average").textContent = formatTime(data.averageResponseTimeMs);
    byId("log-content").hidden = !rows.length;
    showStatus("log-status", rows.length ? "" : "No calls recorded for this inspection.");
  } catch {
    if (suggestionRequest === request) showStatus("log-status", "Could not load the call log.", "error");
  }
}

function requestSuggestion(payload, refining = false) {
  return runTask(
    refining ? "refine" : "assist",
    refining ? "clarification-status" : "assistant-status",
    refining ? "Refining suggestion…" : "Waiting for the model…",
    async () => {
      showSuggestion(await readJson("/api/assist", payload), payload);
      showStatus("assistant-status", refining ? "Refined suggestion ready." : "Suggestion ready.", "success");
      if (refining) byId("result-heading").focus();
      if (callLog.open) loadCallLog();
    },
  );
}

sampleButton.addEventListener("click", () => loadInspection("sample"));

urlField.addEventListener("input", () => urlField.setCustomValidity(""));
byId("inspect").addEventListener("submit", (event) => {
  event.preventDefault();
  const url = urlField.value.trim();
  if (!/^https?:\/\//i.test(url)) {
    urlField.setCustomValidity("Enter a demo URL beginning with http:// or https://.");
    urlField.reportValidity();
    return;
  }
  const scope = {
    types: Array.from(scopeTypes.querySelectorAll("input:checked"), (checkbox) => checkbox.value),
    selector: scopeSelector.value.trim() || null,
  };
  const task = event.submitter === reinspectButton ? "reinspect" : "inspect";
  loadInspection(task, { url, scope });
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
  requestSuggestion(payload);
});

answerField.addEventListener("input", updateControls);
clarificationForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (refineButton.disabled) return;
  requestSuggestion({ ...suggestionRequest, clarificationAnswer: answerField.value }, true);
});

callLog.addEventListener("toggle", () => {
  if (callLog.open) loadCallLog();
});

updateControls();
