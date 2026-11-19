"""API-level test of /api/assist and /api/logs with the offline mock provider."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from fastapi.testclient import TestClient
except ImportError:  # httpx not installed
    TestClient = None

from app import storage
from model import model as model_module

SNAPSHOT = {
    "sourceUrl": "http://localhost:8000/login",
    "elements": [
        {"id": "el-1", "role": "textbox", "label": "Email", "attributes": {"type": "email"},
         "candidateLocators": [{"strategy": "label", "value": "Email", "matchCount": 1}]},
    ],
}
MOCK_CFG = {"provider": "mock", "fallback_provider": None, "max_field_chars": 200,
            "providers": {"mock": {"model": "mock-grounded-v1"}}}


@unittest.skipIf(TestClient is None, "fastapi test client needs httpx")
class AssistApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [mock.patch.object(storage, "DATA_DIR", Path(self.tmp.name)),
                        mock.patch.object(model_module, "load_model_config", return_value=MOCK_CFG)]
        for p in self.patches:
            p.start()
        model_module._CACHE.clear()
        from app.app import app
        self.client = TestClient(app)
        self.inspection_id = storage.save_inspection(SNAPSHOT)["inspectionId"]

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_assist_returns_structured_grounded_reply_and_logs_it(self):
        r = self.client.post("/api/assist", json={"inspectionId": self.inspection_id,
                                                  "elementIds": ["el-1"], "goal": "Check email"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["grounding"]["ok"])
        self.assertEqual(body["provider"], "mock")
        self.assertIsInstance(body["logId"], int)

        logs = self.client.get("/api/logs", params={"inspectionId": self.inspection_id}).json()
        self.assertEqual(logs["freshCalls"], 1)
        self.assertEqual(logs["calls"][0]["goal"], "Check email")

    def test_unknown_element_rejected(self):
        r = self.client.post("/api/assist", json={"inspectionId": self.inspection_id,
                                                  "elementIds": ["el-99"], "goal": "x"})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
