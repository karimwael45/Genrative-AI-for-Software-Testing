# Shared API contracts

GET / serves the UI. GET /web/sample-inspection.json serves a synthetic fixture.
POST /api/inspect accepts {"url":"http://localhost:8000/login"} and an optional "scope": {"selector": "#login-form" or null, "types": ["button","input"]} to refine the inspection; returns an inspection matching sample-inspection.json with a stored UUID and an inspectedAt UTC timestamp set by the backend when it is saved. The scope is forwarded to the worker and stored with the inspection.
GET /api/inspections/{inspectionId} returns a stored inspection without re-running the worker; unknown or malformed IDs return 404.
POST /api/assist accepts inspectionId, elementIds (nonempty array), goal, and optional clarificationAnswer (the tester's reply to the previous clarification question); returns the response shape in sample-model-call.json. The original fields (message, model, inputTokens, outputTokens, responseTimeMs, tokenCountsEstimated) are unchanged; the structured fields (summary, observations, nextAction, clarification, assumptions, grounding, provider, cached, outputValid, fallbackUsed, fallbackReason, logId) are additive. Every call is stored in the logs table.
GET /api/logs[?inspectionId=...] returns {calls, freshCalls, averageResponseTimeMs}; cached (reused) results are excluded from the average.
Errors use a non-2xx status and {"error":"message"}. Request validation uses 422; missing inspections 404; timeout 504; model stub 501; model provider unavailable or rate limited 503.
The worker accepts one JSON object with url (and optional scope) on stdin and emits one inspection or error JSON object on stdout. Worker errors exit nonzero.
Canonical field models are in app/schemas.py. Samples are synthetic, not demo evidence.

## Inspection fields (final naming: camelCase)
- Inspection: inspectionId, sourceUrl, inspectedAt, scope, inspectionTimeMs (browser time), elements.
- Element (required): id, role, label, attributes, candidateLocators. Optional: tag, labelSource (e.g. "aria-label", "label[for]", "placeholder"), text.
- Locator: strategy, value, optional name, matchCount (>= 0, measured on the live page), unique. If the worker omits unique, the backend sets it to matchCount == 1.
- Element IDs must be unique within an inspection; worker output with duplicate IDs or a negative matchCount is rejected with 400 and not stored.
- Fields not listed here are dropped before storage. Agree on new fields in this file and app/schemas.py first.
