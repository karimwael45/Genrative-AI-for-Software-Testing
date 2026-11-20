# 1. Component diagram

Source: [`docs/diagrams/component.mmd`](../diagrams/component.mmd). Colours show ownership: P1 blue, P2 green, P3 amber, P4 purple. The red dashed box is the isolated runner process.

```mermaid
flowchart LR
  Tester(["Tester (human)<br/>goal, element selection,<br/>clarifications, approvals"])

  subgraph UI["Web UI [P2]"]
    Web["web/index.html, app.js<br/>findings table, goal box,<br/>model response + usage"]
  end

  subgraph Backend["FastAPI backend [P4]"]
    API["app/app.py<br/>/api/inspect, /api/inspections/{id},<br/>/api/assist, /api/logs"]
    Schemas["app/schemas.py<br/>Pydantic contract checks"]
    Client["app/runner_client.py<br/>allowlist check, timeout,<br/>restricted cwd + env"]
  end

  subgraph Store["Storage [P4]"]
    DB[("app/storage.py<br/>SQLite data/assistant.sqlite3<br/>inspections, logs,<br/>artifact_versions")]
  end

  subgraph Model["Model module [P3]"]
    M["model/model.py<br/>grounded prompt, cache"]
    V["model/validation.py<br/>ID resolution, grounding"]
    P["model/providers.py<br/>token + time logging"]
  end

  LLM(["LLM provider<br/>Groq gpt-oss-20b (default),<br/>Gemini or local Ollama"])

  subgraph Runner["ISOLATED RUNNER PROCESS"]
    RM["runner/runner_main.py<br/>JSON in / JSON out,<br/>origin check"]
    INS["runner/inspector.py<br/>runner/locators.py"]
    CH["Chromium (headed)<br/>Playwright"]
  end

  Site(["Target website<br/>allowlisted origins only"])

  Tester <--> Web
  Web <-->|"HTTP / JSON"| API
  API --> Schemas
  API --> Client
  API <--> DB
  API <--> M
  M --> V
  M --> P
  P <-->|"prompt / response"| LLM
  Client <-->|"JSON over stdin / stdout<br/>(no Playwright import in backend)"| RM
  RM --> INS --> CH
  CH <--> Site

  classDef p1 fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a
  classDef p2 fill:#dcfce7,stroke:#15803d,color:#14532d
  classDef p3 fill:#fef3c7,stroke:#b45309,color:#78350f
  classDef p4 fill:#ede9fe,stroke:#6d28d9,color:#4c1d95
  classDef ext fill:#f3f4f6,stroke:#6b7280,color:#111827
  class RM,INS,CH p1
  class Web p2
  class M,V,P p3
  class API,Schemas,Client,DB p4
  class Tester,LLM,Site ext
  style Runner fill:#fff5f5,stroke:#dc2626,stroke-width:2px,stroke-dasharray:6 4
```

## Components

| Component | Files | Owner | Responsibility |
|---|---|---|---|
| Web UI | `web/index.html`, `web/app.js`, `web/style.css` | P2 | URL input, findings table linked to the source URL, element selection, goal box, model response with usage. |
| FastAPI backend | `app/app.py` | P4 | The only entry point. Orchestrates runner, storage and model; maps errors to HTTP codes (400, 404, 501, 503, 504). |
| Contract checks | `app/schemas.py` | P4 | Pydantic models for every request and stored record (see `contracts/api.md`). Runner output is validated before it is saved. |
| Runner client | `app/runner_client.py` | P4 | Allowlist check, spawns the runner as a separate process with a timeout, restricted working folder and minimal environment. |
| Storage | `app/storage.py` | P4 | SQLite: inspections, model-call logs, artifact versions. See [storage design](04-storage-design.md). |
| Runner | `runner/runner_main.py`, `runner/inspector.py`, `runner/locators.py` | P1 | Separate process. Reads one JSON request on stdin, opens headed Chromium, returns elements and ranked locators with match counts on stdout. |
| Model module | `model/model.py`, `model/validation.py`, `model/providers.py` | P3 | Builds the grounded prompt, calls the provider, checks output grounding, records tokens and time. |
| LLM provider | external / local | P3 | Groq `openai/gpt-oss-20b` by default; Gemini or local Ollama as alternatives. |

## Boundaries

- **Isolation boundary.** The backend never imports Playwright or `runner/` code. It exchanges only JSON with the runner over stdin/stdout. A crash, hang or timeout in the browser cannot take down the API.
- **Trust boundary.** Everything read from the target page (labels, text, attributes) is untrusted. It is validated by schema, truncated, and placed inside a delimited untrusted-data block before reaching the model.
- **Secrets boundary.** API keys live only in a local, git-ignored `.env`. The runner process does not receive them (environment allowlist in `runner_client.py`).
