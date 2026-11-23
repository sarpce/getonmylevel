import contextlib
import io
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import common
import setup
import agent_operations as agents


class SetupCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.repo = self.base / "repo"
        self.home.mkdir()
        self.repo.mkdir()
        self.env = patch.dict("os.environ", {"CODEX_HOME": str(self.home / ".codex"),
                                               "CLAUDE_CONFIG_DIR": str(self.home / ".claude"),
                                               "HOME": str(self.home)}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.home_patch = patch.object(Path, "home", return_value=self.home)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)

    def run_cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = setup.main(list(args))
        return result, output.getvalue()

    def test_roles_dry_run_supports_each_client_and_scope_without_writes(self):
        for client, expected in (("codex", self.home / ".codex/agents/getonmylevel_designer.toml"),
                                 ("claude", self.home / ".claude/agents/getonmylevel-designer.md"),
                                 ("copilot", self.home / ".copilot/agents/getonmylevel-designer.agent.md")):
            with self.subTest(client=client):
                code, output = self.run_cli("roles", "install", "--client", client, "--roles", "designer", "--dry-run")
                self.assertEqual(code, 0, output)
                self.assertIn(str(expected), output)
                self.assertFalse(expected.exists())
        code, output = self.run_cli("roles", "install", "--scope", "both", "--repo", str(self.repo),
                                    "--roles", "reviewer", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn(str(self.home / ".codex/agents/getonmylevel_reviewer.toml"), output)
        self.assertIn(str(self.repo / ".codex/agents/getonmylevel_reviewer.toml"), output)

    def test_role_install_preserves_settings_unless_explicitly_changed_and_remove_checks_marker(self):
        path = self.home / ".codex/agents/getonmylevel_designer.toml"
        code, output = self.run_cli("roles", "install", "--roles", "designer", "--model", "designer=gpt-x", "--effort", "designer=high", "--yes")
        self.assertEqual(code, 0, output)
        self.assertIn('model = "gpt-x"', path.read_text(encoding="utf-8"))
        code, output = self.run_cli("roles", "update", "--roles", "designer", "--yes")
        self.assertEqual(code, 0, output)
        self.assertIn('model = "gpt-x"', path.read_text(encoding="utf-8"))
        code, _ = self.run_cli("roles", "remove", "--roles", "designer", "--dry-run")
        self.assertEqual(code, 0)
        self.assertTrue(path.exists())
        path.write_text(path.read_text(encoding="utf-8").replace("# getonmylevel-managed-v1", "# hand edited"), encoding="utf-8")
        code, output = self.run_cli("roles", "remove", "--roles", "designer")
        self.assertEqual(code, 1)
        self.assertIn("not marked as managed", output)
        self.assertTrue(path.exists())

    def test_copilot_rejects_effort_and_linked_files(self):
        code, output = self.run_cli("roles", "install", "--client", "copilot", "--roles", "designer", "--effort", "designer=high")
        self.assertEqual(code, 1)
        self.assertIn("does not support reasoning effort", output)
        root = self.home / ".copilot/agents"
        root.mkdir(parents=True)
        link = root / "getonmylevel-designer.agent.md"
        target = self.base / "target"
        target.write_text("keep", encoding="utf-8")
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        code, output = self.run_cli("roles", "update", "--client", "copilot", "--roles", "designer")
        self.assertEqual(code, 1)
        self.assertIn("linked", output)
        self.assertEqual(target.read_text(encoding="utf-8"), "keep")

    def test_global_role_changes_require_yes(self):
        destination = self.home / ".codex/agents/getonmylevel_designer.toml"
        code, output = self.run_cli("roles", "install", "--roles", "designer")
        self.assertEqual(code, 2)
        self.assertIn("global client role configuration", output)
        self.assertFalse(destination.exists())

    def test_role_batch_failure_reports_completed_files(self):
        original_write = agents.write_atomic
        calls = 0

        def fail_second(path, content):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated disk failure")
            original_write(path, content)

        with patch.object(agents, "write_atomic", side_effect=fail_second):
            code, output = self.run_cli("roles", "install", "--roles", "designer", "implementer", "--yes")
        self.assertEqual(code, 1)
        self.assertIn("simulated disk failure", output)
        self.assertIn("Completed before failure", output)
        self.assertTrue((self.home / ".codex/agents/getonmylevel_designer.toml").exists())
        self.assertFalse((self.home / ".codex/agents/getonmylevel_implementer.toml").exists())

    def test_codegraph_and_suggested_confirmation_gates_do_not_execute(self):
        with patch("codegraph_installer.detected_command", return_value="/usr/bin/codegraph"), \
             patch("codegraph_installer.plan_install") as plan, patch("codegraph_installer.install") as install:
            code, output = self.run_cli("codegraph", "setup", "--client", "claude")
            self.assertEqual(code, 2)
            self.assertIn("--yes", output)
            install.assert_not_called()
        with patch("suggested_installers.plan_selected", return_value=([type("P", (), {
                "name": "Example", "details": "pinned source; network", "destination": self.base / "dest", "commands": (("git", "fetch"),)})()], None)), \
             patch("suggested_installers.install_selected") as install:
            code, output = self.run_cli("suggested", "install", "--items", "last30days")
            self.assertEqual(code, 2)
            self.assertIn("git fetch", output)
            install.assert_not_called()

    def test_copilot_suggested_actions_are_rejected_and_status_is_safe(self):
        self.assertEqual(self.run_cli("suggested", "status", "--client", "copilot")[0], 0)
        code, output = self.run_cli("suggested", "install", "--client", "copilot", "--items", "last30days", "--yes")
        self.assertEqual(code, 2)
        self.assertIn("not supported", output)

    def test_codegraph_missing_install_dry_plan_defers_prefix_command(self):
        fake_node, fake_npm_cli = self.base / "node.exe", self.base / "npm-cli.js"
        with patch("codegraph_installer.detected_command", return_value=None), \
             patch("codegraph_installer.platform.system", return_value="Windows"), \
             patch("codegraph_installer._windows_node_npm", return_value=(fake_node, fake_npm_cli)), \
             patch("codegraph_installer._run") as run:
            code, output = self.run_cli("codegraph", "setup", "--client", "copilot", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn("@colbymchenry/codegraph@", output)
        self.assertIn("prefix -g", output)
        self.assertIn("<npm-global-prefix>", output)
        self.assertIn(str(fake_node), output)
        self.assertIn("npm-shim.js|dist/bin/codegraph.js", output)
        self.assertIn("copilot-cli,copilot-vscode", output)
        self.assertIn("No project", output)
        run.assert_not_called()

    def test_shared_agent_operations_keeps_gui_model_discovery_queue(self):
        process = type("Process", (), {"stdin": object(), "stdout": type("Output", (), {"readline": lambda self, _limit: b""})()})()
        with patch.object(agents, "find_codex", return_value="codex"), patch.object(agents.subprocess, "Popen", return_value=process):
            app_server = agents.AppServer()
        self.assertIsInstance(app_server.lines, queue.Queue)

    def test_suggested_removal_requires_yes_and_reports_partial_failures(self):
        planned = type("R", (), {"name": "Example", "destinations": ((self.base / "skill", (1, 2)),)})()
        with patch("suggested_installers.plan_removal", return_value=(planned, None)), \
             patch("suggested_installers.remove_selected") as remove:
            code, output = self.run_cli("suggested", "remove", "--items", "last30days")
            self.assertEqual(code, 2)
            self.assertIn(str(self.base / "skill"), output)
            remove.assert_not_called()
        install_plan = type("P", (), {"name": "Example", "details": "pinned source", "destination": self.base / "dest", "commands": (("git", "fetch"),)})()
        with patch("suggested_installers.plan_selected", return_value=([install_plan], None)), \
             patch("suggested_installers.install_selected", return_value=[("Example", False, "Installer failed; partial changes may remain")]):
            code, output = self.run_cli("suggested", "install", "--items", "last30days", "--yes")
        self.assertEqual(code, 1)
        self.assertIn("partial changes may remain", output)

    def test_cli_modules_import_without_tkinter(self):
        import subprocess
        import sys
        result = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'tools'); import setup; print('ok')"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "ok")


if __name__ == "__main__":
    unittest.main()
