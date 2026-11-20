"""Runner client tests: allowlist, restricted process setup and output parsing.

subprocess.run is mocked, so no browser or runner process is started.
"""
import json
import os
import subprocess
import unittest
from unittest import mock

from app import runner_client

URL = "http://localhost:8000/login"
SETTINGS = {"allowed_origins": ["http://localhost:8000"], "runner_timeout_seconds": 30, "max_elements": 2}
INSPECTION = {"sourceUrl": URL, "elements": []}


def completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class RunnerClientTests(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(runner_client, "load_settings", return_value=SETTINGS)
        patch.start()
        self.addCleanup(patch.stop)

    def run_with(self, result, url=URL, scope=None):
        with mock.patch.object(runner_client.subprocess, "run", return_value=result) as run:
            return runner_client.run_inspection(url, scope), run

    def test_unapproved_origin_rejected_without_starting_runner(self):
        with mock.patch.object(runner_client.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                runner_client.run_inspection("https://example.org/login")
        run.assert_not_called()

    def test_bad_scheme_and_credentials_rejected(self):
        for url in ("file:///etc/passwd", "ftp://localhost:8000/", "http://user:pw@localhost:8000/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                runner_client.check_allowed_url(url, SETTINGS)

    def test_runner_started_in_work_dir_without_secrets(self):
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": "secret", "PATH": os.environ.get("PATH", "")}):
            payload, run = self.run_with(completed(json.dumps(INSPECTION)), scope={"types": ["input"]})
        self.assertEqual(payload, INSPECTION)
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["cwd"], runner_client.WORK_DIR)
        self.assertNotIn("GROQ_API_KEY", kwargs["env"])
        self.assertEqual(kwargs["env"]["PYTHONPATH"], str(runner_client.ROOT))
        self.assertEqual(json.loads(kwargs["input"]), {"url": URL, "scope": {"types": ["input"]}})

    def test_empty_output_gives_clear_error_with_stderr(self):
        with self.assertRaises(ValueError) as ctx:
            self.run_with(completed("", "Traceback: boom", returncode=1))
        self.assertIn("no valid JSON", str(ctx.exception))
        self.assertIn("boom", str(ctx.exception))

    def test_runner_error_message_passed_through(self):
        with self.assertRaises(ValueError) as ctx:
            self.run_with(completed(json.dumps({"error": "Implement headed Playwright inspection"}), returncode=1))
        self.assertEqual(str(ctx.exception), "Implement headed Playwright inspection")

    def test_element_limit_enforced(self):
        too_many = {"sourceUrl": URL, "elements": [{}, {}, {}]}
        with self.assertRaises(ValueError):
            self.run_with(completed(json.dumps(too_many)))

    def test_timeout_propagates(self):
        with mock.patch.object(runner_client.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired(cmd="runner", timeout=30)):
            with self.assertRaises(subprocess.TimeoutExpired):
                runner_client.run_inspection(URL)


if __name__ == "__main__":
    unittest.main()
