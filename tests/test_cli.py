import json
import tempfile
import unittest
from pathlib import Path

from model.cli import append_log, read_json


class CliFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_json_with_windows_bom(self):
        path = self.dir / "inspection.json"
        path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"sourceUrl": "http://x"}).encode())
        self.assertEqual(read_json(path)["sourceUrl"], "http://x")

    def test_append_creates_and_extends_list(self):
        path = self.dir / "log.json"
        append_log(path, {"n": 1})
        append_log(path, {"n": 2})
        self.assertEqual(read_json(path), [{"n": 1}, {"n": 2}])

    def test_append_refuses_non_list_file(self):
        path = self.dir / "old.json"
        path.write_text(json.dumps({"provider": "mock", "calls": []}))
        with self.assertRaises(ValueError):
            append_log(path, {"n": 1})
        self.assertEqual(read_json(path)["provider"], "mock")  # left untouched


if __name__ == "__main__":
    unittest.main()
