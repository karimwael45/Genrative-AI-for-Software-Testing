const byId = (id) => document.getElementById(id);
let inspection;

async function readJson(url, payload) {
  const options = payload === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

function showInspection(data, isSample = false) {
  inspection = isSample ? undefined : data;
  byId("suggest").disabled = isSample || data.elements.length === 0;
  byId("source").textContent = data.sourceUrl;
  byId("result").textContent = "";
  byId("elements").replaceChildren();
  for (const element of data.elements) {
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = element.id;
    const label = document.createElement("label");
    label.append(checkbox, ` ${element.role} · ${element.label || "Unlabeled"}`);
    const evidence = document.createElement("pre");
    evidence.textContent = JSON.stringify({
      attributes: element.attributes,
      candidateLocators: element.candidateLocators,
    }, null, 2);
    byId("elements").append(label, evidence);
  }
  byId("status").textContent = isSample ? "Sample data for UI development." :
    `Found ${data.elements.length} elements.`;
}

async function showErrors(action) {
  try {
    await action();
  } catch (error) {
    byId("status").textContent = error.message;
  }
}

byId("sample").addEventListener("click", () => showErrors(async () => {
  showInspection(await readJson("/web/sample-inspection.json"), true);
}));

byId("inspect").addEventListener("submit", (event) => {
  event.preventDefault();
  showErrors(async () => {
    byId("status").textContent = "Inspecting page…";
    showInspection(await readJson("/api/inspect", { url: byId("url").value }));
  });
});

byId("assist").addEventListener("submit", (event) => {
  event.preventDefault();
  showErrors(async () => {
    const elementIds = [...document.querySelectorAll("#elements input:checked")]
      .map((checkbox) => checkbox.value);
    if (!elementIds.length) throw new Error("Select at least one element.");
    byId("status").textContent = "Waiting for the model…";
    const response = await readJson("/api/assist", {
      inspectionId: inspection.inspectionId,
      elementIds,
      goal: byId("goal").value.trim(),
    });
    byId("result").textContent = JSON.stringify(response, null, 2);
    byId("status").textContent = "Suggestion ready.";
  });
});
