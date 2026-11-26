"""Wire-shape admission checks; no SDK dependency and no model calls."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import tempfile

REPO = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("kaggle_request_shape", REPO / "scripts/audit-kaggle-request-shape.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class RequestShapeTests(unittest.TestCase):
    def body(self, content="", phase="discovery"):
        return {"model": audit.MODEL, "messages": [{"role": "user", "content": content}],
                "temperature": 0.0, "seed": 108 if phase == "confirmation" else 107, "max_tokens": 64}

    def test_text_and_empty_string_require_exact_preservation(self):
        for text in ("", " ", "Answer with only 42.", "中文\ntext"):
            self.assertEqual(audit.inspect_request(self.body(text), text, "discovery"), [])
        for value in (None, " ", [], "scaffold"):
            body = self.body(); body["messages"][0]["content"] = value
            self.assertIn("candidate_text_not_preserved", audit.inspect_request(body, "", "discovery"))
        for messages in ([], [{"role": "system", "content": ""}], [{"role": "user", "content": ""}, {"role": "user", "content": "extra"}]):
            body = self.body(); body["messages"] = messages
            self.assertIn("candidate_text_not_preserved", audit.inspect_request(body, "", "discovery"))

    def test_disabled_temperature_is_not_claimed_as_deterministic(self):
        for value in (None, False, "0", 1):
            body = self.body(); body["temperature"] = value
            self.assertIn("requested_temperature_zero_not_preserved", audit.inspect_request(body, "", "discovery"))
        body = self.body(); del body["temperature"]
        self.assertIn("requested_temperature_zero_not_preserved", audit.inspect_request(body, "", "discovery"))

    def test_confirmation_seed_output_bound_and_model_are_checked(self):
        self.assertEqual(audit.inspect_request(self.body(phase="confirmation"), "", "confirmation"), [])
        cases = [("seed", 107, "phase_seed_not_preserved"),
                 ("seed", True, "phase_seed_not_preserved"),
                 ("max_tokens", 65, "output_bound_not_preserved"),
                 ("model", "different", "model_identity_not_preserved")]
        for field, value, error in cases:
            body = self.body(phase="confirmation"); body[field] = value
            self.assertIn(error, audit.inspect_request(body, "", "confirmation"))


    def test_child_receives_only_a_temporary_home_and_no_inherited_secrets(self):
        child = SimpleNamespace(returncode=0, stdout=json.dumps({"status": "blocked"}))
        with patch.object(audit.subprocess, "run", return_value=child) as launch, \
             patch.object(audit.subprocess, "check_output", side_effect=["0" * 40, ""]):
            report = audit.run_audit()
        self.assertEqual(report["sourceCommit"], "0" * 40)
        self.assertFalse(report["sourceDirty"])
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(set(launch.call_args.kwargs["env"]), {"HOME", "PATH", "LANG"})
        self.assertEqual(launch.call_args.kwargs["cwd"], launch.call_args.kwargs["env"]["HOME"])
        self.assertIn("-I", launch.call_args.args[0])
        self.assertIn("-B", launch.call_args.args[0])

    def test_child_failure_does_not_retry_or_read_git(self):
        child = SimpleNamespace(returncode=1, stdout="", stderr="audit failure")
        with patch.object(audit.subprocess, "run", return_value=child) as launch, \
             patch.object(audit.subprocess, "check_output") as git:
            with self.assertRaises(RuntimeError):
                audit.run_audit()
        self.assertEqual(launch.call_count, 1)
        git.assert_not_called()

    def test_existing_receipt_stops_before_sdk_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "receipt.json"
            path.write_text("original evidence")
            with patch.object(audit.sys, "argv", ["audit", "--output", str(path)]), \
                 patch.object(audit, "run_audit") as run, \
                 patch.object(audit.sys, "stderr"):
                with self.assertRaises(SystemExit):
                    audit.main()
            run.assert_not_called()
            self.assertEqual(path.read_text(), "original evidence")

if __name__ == "__main__":
    unittest.main()
