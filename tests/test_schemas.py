"""Schema tests: locator uniqueness, element ID checks, optional fields and the contract sample."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pydantic import ValidationError

from app import storage
from app.schemas import Inspection, Locator

try:
    from fastapi.testclient import TestClient
except ImportError:  # httpx not installed
    TestClient = None

ROOT = Path(__file__).resolve().parents[1]


def element(element_id="el-1", **extra):
    return {"id": element_id, "role": "button", "label": "Sign in", "attributes": {},
            "candidateLocators": [{"strategy": "role", "value": "button", "matchCount": 1}], **extra}


class LocatorTests(unittest.TestCase):
    def test_unique_derived_from_match_count(self):
        self.assertTrue(Locator(strategy="css", value="#a", matchCount=1).unique)
        self.assertFalse(Locator(strategy="css", value=".a", matchCount=3).unique)
        self.assertIsNone(Locator(strategy="css", value=".a").unique)

    def test_unique_sent_by_runner_is_kept(self):
        self.assertFalse(Locator(strategy="css", value="#a", matchCount=1, unique=False).unique)

    def test_negative_match_count_rejected(self):
        with self.assertRaises(ValidationError):
            Locator(strategy="css", value="#a", matchCount=-1)


class InspectionTests(unittest.TestCase):
    def test_duplicate_element_ids_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            Inspection.model_validate({"sourceUrl": "http://x", "elements": [element(), element()]})
        self.assertIn("el-1", str(ctx.exception))

    def test_optional_fields_kept_unknown_fields_dropped(self):
        data = Inspection.model_validate({"sourceUrl": "http://x", "elements": [
            element(tag="button", labelSource="text", text="Sign in", screenshot="a.png")]}).model_dump()
        el = data["elements"][0]
        self.assertEqual((el["tag"], el["labelSource"], el["text"]), ("button", "text", "Sign in"))
        self.assertNotIn("screenshot", el)

    def test_contract_samples_are_valid(self):
        for path in ("contracts/sample-inspection.json", "web/sample-inspection.json"):
            with self.subTest(path=path):
                Inspection.model_validate(json.loads((ROOT / path).read_text(encoding="utf-8")))


@unittest.skipIf(TestClient is None, "fastapi test client needs httpx")
class InspectApiValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(storage, "DATA_DIR", Path(self.tmp.name))
        self.patch.start()
        from app.app import app
        self.client = TestClient(app)

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def inspect(self, runner_output):
        with mock.patch("app.app.run_inspection", return_value=runner_output):
            return self.client.post("/api/inspect", json={"url": "http://localhost:8000/login"})

    def test_unique_flag_returned_and_stored(self):
        r = self.inspect({"sourceUrl": "http://localhost:8000/login", "elements": [element(tag="button")]})
        self.assertEqual(r.status_code, 200, r.text)
        el = r.json()["elements"][0]
        self.assertTrue(el["candidateLocators"][0]["unique"])
        self.assertEqual(el["tag"], "button")
        stored = storage.load_inspection(r.json()["inspectionId"])
        self.assertTrue(stored["elements"][0]["candidateLocators"][0]["unique"])

    def test_bad_runner_output_rejected_and_not_stored(self):
        r = self.inspect({"sourceUrl": "http://localhost:8000/login", "elements": [element(), element()]})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(storage.list_inspections(), [])


if __name__ == "__main__":
    unittest.main()
