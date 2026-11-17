# Shared API contracts

GET / serves the UI. GET /web/sample-inspection.json serves a synthetic fixture.
POST /api/inspect accepts {"url":"http://localhost:8000/login"} and returns an inspection matching sample-inspection.json with a stored UUID.
POST /api/assist accepts inspectionId, elementIds (nonempty array), and goal; returns the response shape in sample-model-call.json.
Errors use a non-2xx status and {"error":"message"}. Request validation uses 422; missing inspections 404; timeout 504; model stub 501.
The worker accepts one JSON object with url on stdin and emits one inspection or error JSON object on stdout. Worker errors exit nonzero.
Canonical field models are in app/schemas.py. Samples are synthetic, not demo evidence.
