"""Phase 1 API and static web interface."""
from flask import Flask, jsonify

app = Flask(__name__, static_folder="web", static_url_path="/web")


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.post("/api/inspect")
def inspect():
    # TODO (Person 2): Validate URL, call the separate inspector process,
    # persist its snapshot, and return the saved inspection.
    return jsonify(error="Live inspection is pending. Use Load sample to develop the UI."), 501


@app.post("/api/assist")
def assist():
    # TODO (Person 2): Validate inspectionId, elementIds and goal. Load the
    # snapshot, resolve selected IDs against it, and call model.suggest.
    return jsonify(error="Live model integration is pending."), 501
