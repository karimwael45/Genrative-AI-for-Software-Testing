"""API-level tests of /api/inspect (scope) and /api/inspections/{id} with a mocked runner."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from fastapi.testclient import TestClient
except ImportError:  # httpx not installed
    TestClient = None

from app import storage

RUNNER_OUTPUT = {
    "sourceUrl": "http://localhost:8000/login",
    "inspectionTimeMs": 120.0,
    "elements": [
        {"id": "el-1", "role": "textbox", "label": "Email", "attributes": {"type": "email"},
         "candidateLocators": [{"strategy": "label", "value": "Email", "matchCount": 1}]},
    ],
}


@unittest.skipIf(TestClient is None, "fastapi test client needs httpx")
class InspectionApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patch = mock.patch.object(storage, "DATA_DIR", Path(self.tmp.name))
        self.patch.start()
        from app.app import app
        self.client = TestClient(app)

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_inspect_forwards_and_stores_scope(self):
        scope = {"selector": "#login-form", "types": ["input"]}
        with mock.patch("app.app.run_inspection", return_value=dict(RUNNER_OUTPUT)) as run:
            r = self.client.post("/api/inspect", json={"url": RUNNER_OUTPUT["sourceUrl"], "scope": scope})
        self.assertEqual(r.status_code, 200, r.text)
        run.assert_called_once_with(RUNNER_OUTPUT["sourceUrl"], scope)
        self.assertEqual(r.json()["scope"], scope)

    def test_inspect_without_scope(self):
        with mock.patch("app.app.run_inspection", return_value=dict(RUNNER_OUTPUT)) as run:
            r = self.client.post("/api/inspect", json={"url": RUNNER_OUTPUT["sourceUrl"]})
        self.assertEqual(r.status_code, 200, r.text)
        run.assert_called_once_with(RUNNER_OUTPUT["sourceUrl"], None)
        self.assertNotIn("scope", r.json())

    def test_get_stored_inspection(self):
        saved = storage.save_inspection(RUNNER_OUTPUT)
        r = self.client.get(f"/api/inspections/{saved['inspectionId']}")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), saved)

    def test_get_unknown_inspection_returns_404(self):
        r = self.client.get("/api/inspections/00000000-0000-0000-0000-000000000000")
        self.assertEqual(r.status_code, 404)

    def test_get_malformed_id_returns_404(self):
        r = self.client.get("/api/inspections/not-a-uuid")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
