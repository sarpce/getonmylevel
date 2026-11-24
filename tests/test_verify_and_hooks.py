from __future__ import annotations

import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "getonmylevel-verify" / "scripts"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(SCRIPTS))

import common  # noqa: E402
import find_checks  # noqa: E402
import hook_operations  # noqa: E402
import stop_check  # noqa: E402

HAS_GIT = shutil.which("git") is not None


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", "-c", "core.autocrlf=false", *args],
                   cwd=root, check=True, capture_output=True)


@unittest.skipUnless(HAS_GIT, "git is required")
class FindChecksTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve() / "repo"
        self.state = Path(temp.name).resolve() / "state"
        (self.root / "tests").mkdir(parents=True)
        (self.root / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (self.root / "tests" / "test_calc.py").write_text(
            "import sys, unittest\nsys.path.insert(0, '.')\nimport calc\n\n"
            "class T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(calc.add(2, 2), 4)\n",
            encoding="utf-8")
        _git(self.root, "init", "-q")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", "init")

    def break_calc(self, body="return a - b"):
        (self.root / "calc.py").write_text(f"def add(a, b):\n    {body}\n", encoding="utf-8")

    def test_changed_python_file_maps_to_its_test_and_full_suite_is_listed_only(self):
        self.break_calc()
        files = find_checks.changed_files(self.root)
        self.assertEqual(files, [self.root / "calc.py"])
        checks = find_checks.find_checks(self.root, files)
        targeted = [c.display(self.root) for c in checks if c.scope == "targeted"]
        self.assertEqual(targeted[0], "python syntax [built in]")
        self.assertIn("-p test_calc.py", targeted[1])
        self.assertTrue(any(c.scope == "full" for c in checks))
        passed, failed, skipped = find_checks.run_checks(self.root, checks)
        self.assertEqual((len(passed), len(failed), skipped), (1, 1, []))
        self.assertIn("AssertionError", failed[0][1])

    def test_syntax_errors_are_caught_without_running_tests(self):
        self.break_calc("return a +")
        checks = find_checks.find_checks(self.root, find_checks.changed_files(self.root))
        _passed, failed, _skipped = find_checks.run_checks(self.root, checks[:1])
        self.assertIn("calc.py:2", failed[0][1])

    def test_override_file_replaces_detection_and_empty_file_disables(self):
        (self.root / ".getonmylevel-checks").write_text("# project checks\nexit 3\n", encoding="utf-8")
        checks = find_checks.find_checks(self.root, [self.root / "calc.py"])
        self.assertEqual([c.command for c in checks], ["exit 3"])
        _passed, failed, _skipped = find_checks.run_checks(self.root, checks)
        self.assertEqual(len(failed), 1)
        (self.root / ".getonmylevel-checks").write_text("# off\n", encoding="utf-8")
        self.assertEqual(find_checks.find_checks(self.root, [self.root / "calc.py"]), [])

    def test_caches_from_running_checks_are_not_changes(self):
        (self.root / "tests" / "__pycache__").mkdir()
        (self.root / "tests" / "__pycache__" / "test_calc.cpython-312.pyc").write_bytes(b"\0")
        self.assertEqual(find_checks.changed_files(self.root), [])

    def test_missing_command_is_reported_as_not_run(self):
        check = find_checks.Check("missing", ["definitely-not-a-real-command-xyz"], self.root)
        passed, failed, skipped = find_checks.run_checks(self.root, [check])
        self.assertEqual((passed, failed), ([], []))
        self.assertEqual(skipped[0][1], "command not found")

    def run_hook(self, **event):
        event.setdefault("cwd", str(self.root))
        event.setdefault("session_id", "test-session")
        stderr = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(event))), mock.patch.object(sys, "stderr", stderr), \
             mock.patch.object(stop_check.tempfile, "gettempdir", return_value=str(self.state)):
            return stop_check.main(), stderr.getvalue()

    def test_stop_hook_blocks_once_on_failure_then_waits_for_a_change(self):
        self.assertEqual(self.run_hook(), (0, ""))  # no changes
        self.break_calc()
        code, message = self.run_hook()
        self.assertEqual(code, 2)
        self.assertIn("FAILED", message)
        self.assertIn("tell the user", message)
        self.assertEqual(self.run_hook(), (0, ""))  # unchanged tree is not re-run
        self.break_calc("return a * b + 0")
        self.assertEqual(self.run_hook(stop_hook_active=True), (0, ""))  # never blocks twice in a row
        self.break_calc("return a + b  # fixed")
        self.assertEqual(self.run_hook(), (0, ""))

    def test_stop_hook_never_traps_the_session(self):
        with mock.patch.object(sys, "stdin", io.StringIO("not json")):
            self.assertEqual(stop_check.main(), 0)
        with mock.patch.object(stop_check.find_checks, "find_checks", side_effect=RuntimeError("boom")):
            self.break_calc()
            self.assertEqual(self.run_hook()[0], 0)
        with mock.patch.dict(os.environ, {"GETONMYLEVEL_VERIFY_HOOK": "off"}):
            self.assertEqual(self.run_hook(session_id="other")[0], 0)


class HookInstallTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.config = Path(temp.name) / "claude"
        script = self.config / "skills" / "getonmylevel-verify" / "scripts" / "stop_check.py"
        script.parent.mkdir(parents=True)
        script.write_text("", encoding="utf-8")
        env = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.config)})
        env.start()
        self.addCleanup(env.stop)
        self.settings = self.config / "settings.json"

    def test_install_preserves_other_settings_is_idempotent_and_removes_cleanly(self):
        original = {"model": "opus", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "notify"}]}],
                                               "PostToolUse": [{"matcher": "Edit", "hooks": []}]}}
        self.settings.write_text(json.dumps(original), encoding="utf-8")
        plan = hook_operations.plan("install")
        self.assertEqual(plan.action, "Install")
        hook_operations.apply(plan)
        data = json.loads(self.settings.read_text(encoding="utf-8"))
        self.assertEqual(data["model"], "opus")
        self.assertEqual(data["hooks"]["Stop"][0], original["hooks"]["Stop"][0])
        self.assertIn("stop_check.py", data["hooks"]["Stop"][1]["hooks"][0]["command"])
        self.assertEqual(hook_operations.plan("install").action, "Already current")
        self.assertTrue(hook_operations.status().startswith("Installed"))
        hook_operations.apply(hook_operations.plan("remove"))
        self.assertEqual(json.loads(self.settings.read_text(encoding="utf-8")), original)
        self.assertEqual(hook_operations.plan("remove").action, "Not installed")

    def test_invalid_settings_changed_settings_and_missing_skill_are_refused(self):
        self.settings.write_text("{not json", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not valid JSON"):
            hook_operations.plan("install")
        self.settings.write_text("{}", encoding="utf-8")
        plan = hook_operations.plan("install")
        self.settings.write_text('{"changed": true}', encoding="utf-8")
        with self.assertRaisesRegex(OSError, "changed since preview"):
            hook_operations.apply(plan)
        (self.config / "skills" / "getonmylevel-verify" / "scripts" / "stop_check.py").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "Install the getonmylevel-verify skill"):
            hook_operations.plan("install")

    def test_setup_cli_requires_yes(self):
        import setup
        with mock.patch.object(sys, "stdout", io.StringIO()), mock.patch.object(sys, "stderr", io.StringIO()) as err:
            self.assertEqual(setup.main(["hooks", "install"]), 2)
        self.assertIn("without --yes", err.getvalue())
        self.assertFalse(self.settings.exists())
        with mock.patch.object(sys, "stdout", io.StringIO()):
            self.assertEqual(setup.main(["hooks", "install", "--yes"]), 0)
        self.assertTrue(self.settings.exists())


class MultiClientHookTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        for patcher in (mock.patch.object(Path, "home", return_value=self.home),
                        mock.patch.dict(os.environ, {"CODEX_HOME": str(self.home / ".codex"),
                                                     "CLAUDE_CONFIG_DIR": str(self.home / ".claude")})):
            patcher.start()
            self.addCleanup(patcher.stop)
        os.environ.pop("COPILOT_HOME", None)
        for client in common.CLIENTS:
            script = common.skill_roots("user", None, client)[0] / "getonmylevel-verify" / "scripts" / "stop_check.py"
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text("", encoding="utf-8")

    def test_each_client_gets_its_native_hook_and_removal_is_clean(self):
        expected = {"codex": self.home / ".codex" / "hooks.json",
                    "copilot": self.home / ".copilot" / "hooks" / "getonmylevel-verify.json",
                    "opencode": self.home / ".config" / "opencode" / "plugins" / "getonmylevel-verify.js"}
        for client, path in expected.items():
            with self.subTest(client=client):
                plan = hook_operations.plan("install", client)
                self.assertEqual(plan.path, path)
                hook_operations.apply(plan)
                text = path.read_text(encoding="utf-8")
                if client == "codex":
                    self.assertIn("stop_check.py", json.loads(text)["hooks"]["Stop"][0]["hooks"][0]["command"])
                    self.assertTrue(any("/hooks" in note for note in plan.notes))
                elif client == "copilot":
                    data = json.loads(text)
                    self.assertEqual(set(data), {"version", "hooks"})
                    hook = data["hooks"]["agentStop"][0]
                    self.assertTrue(hook["bash"].endswith("--format json"))
                    self.assertTrue(hook["powershell"].startswith("& "))
                else:
                    self.assertIn("ctx.session.prompt", text)
                    self.assertIn('"session.idle"', text)
                self.assertEqual(hook_operations.plan("install", client).action, "Already current")
                self.assertEqual(hook_operations.status(client).split(":")[0], "Installed")
                hook_operations.apply(hook_operations.plan("remove", client))
                if client == "codex":
                    self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {})
                else:
                    self.assertFalse(path.exists())

    def test_owned_hook_files_written_by_someone_else_are_refused(self):
        path = hook_operations.settings_path("copilot")
        path.parent.mkdir(parents=True)
        path.write_text('{"version": 1, "hooks": {}}', encoding="utf-8")
        for action in ("install", "remove"):
            with self.assertRaisesRegex(ValueError, "not written by getonmylevel"):
                hook_operations.plan(action, "copilot")


@unittest.skipUnless(HAS_GIT, "git is required")
class JsonFormatTests(FindChecksTests):
    """Copilot CLI and OpenCode get a JSON block decision instead of exit 2."""

    def test_json_format_blocks_on_stdout_and_accepts_camel_case_payload(self):
        self.break_calc()
        event = {"sessionId": "copilot-1", "cwd": str(self.root), "stop_hook_active": False}
        out = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(event))), mock.patch.object(sys, "stdout", out), \
             mock.patch.object(stop_check.tempfile, "gettempdir", return_value=str(self.state)):
            self.assertEqual(stop_check.main(["--format", "json"]), 0)
        decision = json.loads(out.getvalue())
        self.assertEqual(decision["decision"], "block")
        self.assertIn("FAILED", decision["reason"])


class DocumentationTests(unittest.TestCase):
    def test_readme_links_each_bundled_skill_and_shows_the_real_block(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for name in common.SKILL_NAMES:
            self.assertIn(f"(skills/{name}/SKILL.md)", readme)
        import instruction_integration
        with mock.patch.dict(os.environ, {key: value for key, value in os.environ.items() if key != "CLAUDE_CONFIG_DIR"}, clear=True):
            block = instruction_integration._block(list(common.SKILL_NAMES), "user", "\n", "claude")
        self.assertIn(block, readme.replace("\r\n", "\n"))


if __name__ == "__main__":
    unittest.main()
