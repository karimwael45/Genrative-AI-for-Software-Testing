"""Ordered provider fallback, mock labelling, caching rules, and the CLI evidence guard."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from model import cli
from model import model as model_module
from model import providers
from model.providers import ProviderError, ProviderResult

ELEMENTS = [{"id": "el-1", "role": "textbox", "label": "Email", "attributes": {},
             "candidateLocators": []}]
BASE = {"provider": "groq", "max_field_chars": 200,
        "providers": {"mock": {"model": "mock-grounded-v1"}}}
REPLY = json.dumps({"summary": "s", "nextAction": {"description": "d", "elementIds": ["el-1"]}})


def failing(reason):
    def run(system, user, cfg):
        raise ProviderError(reason)
    return run


def answering(name):
    def run(system, user, cfg):
        return ProviderResult(REPLY, name, f"{name}-model", 10, 5, False, 7.0)
    return run


class OrderTests(unittest.TestCase):
    def test_main_then_fallbacks_without_duplicates(self):
        cfg = {"provider": "groq", "fallbacks": ["ollama", "mock", "groq"]}
        self.assertEqual(providers.provider_order(cfg), ["groq", "ollama", "mock"])

    def test_legacy_single_fallback_still_works(self):
        self.assertEqual(providers.provider_order({"provider": "groq", "fallback_provider": "mock"}),
                         ["groq", "mock"])

    def test_empty_list_disables_fallbacks(self):
        self.assertEqual(providers.provider_order({"provider": "groq", "fallbacks": []}), ["groq"])


class ChainTests(unittest.TestCase):
    def test_second_level_answers_and_failures_are_recorded(self):
        table = {"groq": failing("no key"), "ollama": failing("not running"), "mock": answering("mock")}
        with mock.patch.dict(providers.PROVIDERS, table):
            result = providers.complete("s", "u", dict(BASE, fallbacks=["ollama", "mock"]))
        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.failed_before, ["groq: no key", "ollama: not running"])

    def test_ollama_answers_before_mock_is_needed(self):
        table = {"groq": failing("429"), "ollama": answering("ollama"), "mock": answering("mock")}
        with mock.patch.dict(providers.PROVIDERS, table):
            result = providers.complete("s", "u", dict(BASE, fallbacks=["ollama", "mock"]))
        self.assertEqual(result.provider, "ollama")
        self.assertEqual(len(result.failed_before), 1)

    def test_main_provider_answering_leaves_no_failures(self):
        with mock.patch.dict(providers.PROVIDERS, {"groq": answering("groq")}):
            self.assertEqual(providers.complete("s", "u", dict(BASE, fallbacks=["ollama"])).failed_before, [])

    def test_everything_failing_raises(self):
        table = {"groq": failing("a"), "ollama": failing("b")}
        with mock.patch.dict(providers.PROVIDERS, table), self.assertRaises(ProviderError):
            providers.complete("s", "u", dict(BASE, fallbacks=["ollama"]))


class SuggestTests(unittest.TestCase):
    def setUp(self):
        model_module._CACHE.clear()

    def run_suggest(self, name, failed_before=()):
        result = ProviderResult(REPLY, name, f"{name}-model", 10, 5, False, 7.0, list(failed_before))
        with mock.patch.object(model_module, "load_model_config", return_value=BASE), \
             mock.patch.object(model_module, "complete", return_value=result) as complete:
            return model_module.suggest("goal", "http://x", ELEMENTS), complete

    def test_mock_reply_is_labelled(self):
        out, _ = self.run_suggest("mock")
        self.assertIn("[MOCK reply", out["message"])

    def test_real_provider_reply_is_not_labelled(self):
        out, _ = self.run_suggest("groq")
        self.assertNotIn("MOCK", out["message"])
        self.assertFalse(out["fallbackUsed"])

    def test_fallback_reply_is_flagged_with_reason(self):
        out, _ = self.run_suggest("ollama", ["groq: HTTP 401"])
        self.assertTrue(out["fallbackUsed"])
        self.assertIn("groq: HTTP 401", out["fallbackReason"])
        self.assertIn("fallback provider 'ollama'", out["message"])

    def test_fallback_reply_is_not_cached(self):
        self.run_suggest("mock", ["groq: down"])
        out, complete = self.run_suggest("groq")  # main provider is back: must be asked again
        complete.assert_called_once()
        self.assertFalse(out["cached"])

    def test_cached_copy_does_not_inherit_the_callers_log_id(self):
        first, _ = self.run_suggest("groq")
        first["logId"] = 1  # what app.py does after saving the log
        with mock.patch.object(model_module, "load_model_config", return_value=BASE):
            second = model_module.suggest("goal", "http://x", ELEMENTS)
        self.assertTrue(second["cached"])
        self.assertNotIn("logId", second)

    def test_provider_argument_forces_one_provider_without_fallbacks(self):
        result = ProviderResult(REPLY, "ollama", "m", 1, 1, False, 1.0)
        cfg = dict(BASE, fallbacks=["ollama", "mock"])
        with mock.patch.object(model_module, "load_model_config", return_value=cfg), \
             mock.patch.object(model_module, "complete", return_value=result) as complete:
            model_module.suggest("goal", "http://x", ELEMENTS, provider="ollama")
        used = complete.call_args.args[2]
        self.assertEqual((used["provider"], used["fallbacks"]), ("ollama", []))


class CliGuardTests(unittest.TestCase):
    def run_cli(self, provider_name, *extra):
        fake = {"message": "m", "provider": provider_name, "model": "x", "inputTokens": 1,
                "outputTokens": 1, "tokenCountsEstimated": False, "responseTimeMs": 1.0, "cached": False,
                "grounding": {"ok": True, "unknownElementIds": []}, "fallbackUsed": False,
                "fallbackReason": None}
        with tempfile.TemporaryDirectory() as tmp:
            save = Path(tmp) / "log.json"
            argv = ["cli", "--goal", "g", "--ids", "el-1", "--save", str(save), *extra]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(cli, "suggest", return_value=fake), \
                 mock.patch.object(cli, "load_model_config", return_value=BASE):
                code = cli.main()
            return code, save.exists()

    def test_refuses_to_save_mock_reply(self):
        code, saved = self.run_cli("mock")
        self.assertEqual((code, saved), (1, False))

    def test_allow_mock_flag_saves_scratch_file(self):
        code, saved = self.run_cli("mock", "--allow-mock")
        self.assertEqual((code, saved), (0, True))

    def test_real_reply_is_saved(self):
        code, saved = self.run_cli("groq")
        self.assertEqual((code, saved), (0, True))


if __name__ == "__main__":
    unittest.main()
