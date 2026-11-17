import unittest
from runner.runner_main import validate_url
from model.validation import resolve_elements

class BoundaryTests(unittest.TestCase):
    def test_unapproved_origin_rejected(self):
        with self.assertRaises(ValueError):
            validate_url("https://example.org/login")

    def test_unknown_selected_id_rejected(self):
        with self.assertRaises(ValueError):
            resolve_elements({"elements": [{"id": "el-1"}]}, ["invented"])

if __name__ == "__main__":
    unittest.main()
