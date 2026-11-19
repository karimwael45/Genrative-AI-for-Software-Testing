# Shared API contracts

GET / serves the UI. GET /web/sample-inspection.json serves a synthetic fixture.
POST /api/inspect accepts {"url":"http://localhost:8000/login"} and returns an inspection matching sample-inspection.json with a stored UUID.
POST /api/assist accepts inspectionId, elementIds (nonempty array), goal, and optional clarificationAnswer (the tester's reply to the previous clarification question); returns the response shape in sample-model-call.json. The original fields (message, model, inputTokens, outputTokens, responseTimeMs, tokenCountsEstimated) are unchanged; the structured fields (summary, observations, nextAction, clarification, assumptions, grounding, provider, cached, outputValid, logId) are additive. Every call is stored in the logs table.
GET /api/logs[?inspectionId=...] returns {calls, freshCalls, averageResponseTimeMs}; cached (reused) results are excluded from the average.
Errors use a non-2xx status and {"error":"message"}. Request validation uses 422; missing inspections 404; timeout 504; model stub 501; model provider unavailable or rate limited 503.
The worker accepts one JSON object with url on stdin and emits one inspection or error JSON object on stdout. Worker errors exit nonzero.
Canonical field models are in app/schemas.py. Samples are synthetic, not demo evidence.
