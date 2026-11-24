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
import agents_gui


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
        for client, expected in (("codex", self.home / ".codex/agents/getonmylevel_reviewer.toml"),
                                 ("claude", self.home / ".claude/agents/getonmylevel-reviewer.md"),
                                 ("copilot", self.home / ".copilot/agents/getonmylevel-reviewer.agent.md")):
            with self.subTest(client=client):
                code, output = self.run_cli("roles", "install", "--client", client, "--roles", "reviewer", "--dry-run")
                self.assertEqual(code, 0, output)
                self.assertIn(str(expected), output)
                self.assertFalse(expected.exists())
        code, output = self.run_cli("roles", "install", "--scope", "both", "--repo", str(self.repo),
                                    "--roles", "reviewer", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn(str(self.home / ".codex/agents/getonmylevel_reviewer.toml"), output)
        self.assertIn(str(self.repo / ".codex/agents/getonmylevel_reviewer.toml"), output)

    def test_role_install_preserves_settings_unless_explicitly_changed_and_remove_checks_marker(self):
        path = self.home / ".codex/agents/getonmylevel_reviewer.toml"
        code, output = self.run_cli("roles", "install", "--roles", "reviewer", "--model", "reviewer=gpt-x", "--effort", "reviewer=high", "--yes")
        self.assertEqual(code, 0, output)
        self.assertIn('model = "gpt-x"', path.read_text(encoding="utf-8"))
        code, output = self.run_cli("roles", "update", "--roles", "reviewer", "--yes")
        self.assertEqual(code, 0, output)
        self.assertIn('model = "gpt-x"', path.read_text(encoding="utf-8"))
        code, _ = self.run_cli("roles", "remove", "--roles", "reviewer", "--dry-run")
        self.assertEqual(code, 0)
        self.assertTrue(path.exists())
        path.write_text(path.read_text(encoding="utf-8").replace("# getonmylevel-managed-v1", "# hand edited"), encoding="utf-8")
        code, output = self.run_cli("roles", "remove", "--roles", "reviewer")
        self.assertEqual(code, 1)
        self.assertIn("not marked as managed", output)
        self.assertTrue(path.exists())

    def test_copilot_rejects_effort_and_linked_files(self):
        code, output = self.run_cli("roles", "install", "--client", "copilot", "--roles", "reviewer", "--effort", "reviewer=high")
        self.assertEqual(code, 1)
        self.assertIn("does not support reasoning effort", output)
        root = self.home / ".copilot/agents"
        root.mkdir(parents=True)
        link = root / "getonmylevel-reviewer.agent.md"
        target = self.base / "target"
        target.write_text("keep", encoding="utf-8")
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        code, output = self.run_cli("roles", "update", "--client", "copilot", "--roles", "reviewer")
        self.assertEqual(code, 1)
        self.assertIn("linked", output)
        self.assertEqual(target.read_text(encoding="utf-8"), "keep")

    def test_claude_model_and_effort_are_independent_and_inherit_is_explicit(self):
        code, output = self.run_cli("roles", "install", "--client", "claude", "--roles", "reviewer", "--model",
                                    "reviewer=claude-sonnet-future-2026-01", "--effort", "reviewer=xhigh", "--yes")
        self.assertEqual(code, 0, output)
        path = self.home / ".claude/agents/getonmylevel-reviewer.md"
        content = path.read_text(encoding="utf-8")
        self.assertIn('model: "claude-sonnet-future-2026-01"', content)
        self.assertIn('effort: "xhigh"', content)

        code, output = self.run_cli("roles", "update", "--client", "claude", "--roles", "reviewer", "--model",
                                    "reviewer=inherit", "--yes")
        self.assertEqual(code, 0, output)
        content = path.read_text(encoding="utf-8")
        self.assertIn('model: "inherit"', content)
        self.assertIn('effort: "xhigh"', content)
        code, output = self.run_cli("roles", "update", "--client", "claude", "--roles", "reviewer", "--model",
                                    "reviewer=", "--effort", "reviewer=", "--yes")
        self.assertEqual(code, 0, output)
        content = path.read_text(encoding="utf-8")
        self.assertNotIn("model:", content)
        self.assertNotIn("effort:", content)

    def test_claude_invalid_effort_does_not_write_and_remove_remains_available(self):
        code, output = self.run_cli("roles", "install", "--client", "claude", "--roles", "reviewer", "--effort",
                                    "reviewer=ultracode", "--yes")
        self.assertEqual(code, 1)
        self.assertIn("Unsupported Claude Code effort", output)
        path = self.home / ".claude/agents/getonmylevel-reviewer.md"
        self.assertFalse(path.exists())

        code, output = self.run_cli("roles", "install", "--client", "claude", "--roles", "reviewer", "--effort",
                                    "reviewer=high", "--yes")
        self.assertEqual(code, 0, output)
        code, output = self.run_cli("roles", "update", "--client", "claude", "--roles", "reviewer", "--effort",
                                    "reviewer=ultracode", "--yes")
        self.assertEqual(code, 1)
        self.assertIn('effort: "high"', path.read_text(encoding="utf-8"))
        code, output = self.run_cli("roles", "remove", "--client", "claude", "--roles", "reviewer", "--yes")
        self.assertEqual(code, 0, output)
        self.assertFalse(path.exists())

    def test_claude_dry_run_uses_same_effort_validation(self):
        code, output = self.run_cli("roles", "install", "--client", "claude", "--roles", "reviewer", "--effort",
                                    "reviewer=invalid", "--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("Unsupported Claude Code effort", output)
        self.assertFalse((self.home / ".claude/agents/getonmylevel-reviewer.md").exists())

    def test_claude_update_refuses_unmanaged_and_user_modified_files(self):
        code, output = self.run_cli("roles", "install", "--client", "claude", "--roles", "reviewer", "--yes")
        self.assertEqual(code, 0, output)
        path = self.home / ".claude/agents/getonmylevel-reviewer.md"
        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace("<!-- getonmylevel-managed-v1 -->", "<!-- user content -->"), encoding="utf-8")
        code, output = self.run_cli("roles", "update", "--client", "claude", "--roles", "reviewer", "--model",
                                    "reviewer=inherit", "--yes")
        self.assertEqual(code, 1)
        self.assertIn("edited outside model/effort settings", output)
        self.assertIn("<!-- user content -->", path.read_text(encoding="utf-8"))

        path.write_text("user-authored agent\n", encoding="utf-8")
        code, output = self.run_cli("roles", "update", "--client", "claude", "--roles", "reviewer", "--yes")
        self.assertEqual(code, 1)
        self.assertIn("not a Claude Code agent managed", output)
        self.assertEqual(path.read_text(encoding="utf-8"), "user-authored agent\n")

    def test_claude_plan_refuses_destination_changes_before_write_or_remove(self):
        new_plan = agents.role_plan("claude", "global", None, ["reviewer"], {"reviewer": "sonnet"})
        path = self.home / ".claude/agents/getonmylevel-reviewer.md"
        path.parent.mkdir(parents=True)
        path.write_text("created after preview\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed since planning"):
            agents.perform_role_plan(new_plan, "claude", "install")
        self.assertEqual(path.read_text(encoding="utf-8"), "created after preview\n")

        path.unlink()
        initial = agents.role_plan("claude", "global", None, ["reviewer"], {"reviewer": "sonnet"})
        agents.perform_role_plan(initial, "claude", "install")
        update = agents.role_plan("claude", "global", None, ["reviewer"], {"reviewer": "opus"})
        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace('model: "sonnet"', 'model: "haiku"'), encoding="utf-8")
        changed = path.read_text(encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed since planning"):
            agents.perform_role_plan(update, "claude", "update")
        self.assertEqual(path.read_text(encoding="utf-8"), changed)

        removal = agents.role_plan("claude", "global", None, ["reviewer"], action="remove")
        path.write_text(changed.replace('model: "haiku"', 'model: "opus"'), encoding="utf-8")
        changed_again = path.read_text(encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed since planning"):
            agents.perform_role_plan(removal, "claude", "remove")
        self.assertEqual(path.read_text(encoding="utf-8"), changed_again)

    def test_claude_gui_preserves_conflicting_scope_values_until_explicit_selection(self):
        initial = agents.role_plan("claude", "both", self.repo, ["reviewer"], {"reviewer": "sonnet"})
        agents.perform_role_plan(initial, "claude", "install")
        global_path = self.home / ".claude/agents/getonmylevel-reviewer.md"
        repo_path = self.repo / ".claude/agents/getonmylevel-reviewer.md"
        global_update = agents.role_plan("claude", "global", None, ["reviewer"], {"reviewer": "opus"})
        agents.perform_role_plan(global_update, "claude", "update")

        gui = agents_gui.AgentConfigurator.__new__(agents_gui.AgentConfigurator)
        gui.client = type("Value", (), {"get": lambda self: "claude"})()
        gui.scope = type("Value", (), {"get": lambda self: "both"})()
        repo_value = str(self.repo)
        gui.repo_path = type("Value", (), {"get": lambda self: repo_value})()
        gui.selected_roles = lambda: ["reviewer"]
        gui.templates = agents.load_templates()
        gui.model_vars = {"reviewer": type("Value", (), {"get": lambda self: ""})()}
        gui.effort_vars = {"reviewer": type("Value", (), {"get": lambda self: ""})()}
        gui.dirty_fields = {"claude": set()}
        _roles, _roots, _templates, entries = gui.plan()
        content_by_path = {path: content for _role, path, content in entries}
        self.assertIn('model: "opus"', content_by_path[global_path])
        self.assertIn('model: "sonnet"', content_by_path[repo_path])

        gui.model_vars["reviewer"] = type("Value", (), {"get": lambda self: "haiku"})()
        gui.dirty_fields["claude"].add(("reviewer", "model"))
        _roles, _roots, _templates, entries = gui.plan()
        self.assertTrue(all('model: "haiku"' in content for _role, _path, content in entries))

    def test_global_role_changes_require_yes(self):
        destination = self.home / ".codex/agents/getonmylevel_reviewer.toml"
        code, output = self.run_cli("roles", "install", "--roles", "reviewer")
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
            code, output = self.run_cli("roles", "install", "--roles", "reviewer", "--scope", "both", "--repo", str(self.repo), "--yes")
        self.assertEqual(code, 1)
        self.assertIn("simulated disk failure", output)
        self.assertIn("Completed before failure", output)
        self.assertTrue((self.home / ".codex/agents/getonmylevel_reviewer.toml").exists())
        self.assertFalse((self.repo / ".codex/agents/getonmylevel_reviewer.toml").exists())

    def test_retired_roles_are_remove_only_and_old_files_still_update(self):
        retired = agents.RETIRED_TEMPLATE_ROOT
        for role in ("designer", "implementer", "tester"):
            with self.subTest(role=role):
                code, output = self.run_cli("roles", "install", "--client", "claude", "--roles", role, "--dry-run")
                self.assertEqual(code, 1)
                self.assertIn("retired", output)
                template = agents._load_template(retired / f"getonmylevel_{role}.toml")
                path = self.home / f".claude/agents/getonmylevel-{role}.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(agents.render_claude_agent(agents.claude_expected(role, template), "sonnet", ""), encoding="utf-8")
                code, output = self.run_cli("roles", "remove", "--client", "claude", "--roles", role, "--yes")
                self.assertEqual(code, 0, output)
                self.assertFalse(path.exists())
        old_reviewer = agents._load_template(retired / "getonmylevel_reviewer.toml")
        path = self.home / ".codex/agents/getonmylevel_reviewer.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(agents.render_agent(old_reviewer, "gpt-x", "high"), encoding="utf-8")
        code, output = self.run_cli("roles", "update", "--roles", "reviewer", "--yes")
        self.assertEqual(code, 0, output)
        text = path.read_text(encoding="utf-8")
        self.assertIn(agents.load_templates()["reviewer"]["description"], text)
        self.assertIn('model = "gpt-x"', text)
        self.assertIn('model_reasoning_effort = "high"', text)

    def test_suggested_confirmation_gate_does_not_execute(self):
        with patch("suggested_installers.plan_selected", return_value=([type("P", (), {
                "name": "Example", "details": "pinned source; network", "destination": self.base / "dest", "commands": (("git", "fetch"),)})()], None)), \
             patch("suggested_installers.install_selected") as install:
            code, output = self.run_cli("suggested", "install", "--items", "go_viper")
            self.assertEqual(code, 2)
            self.assertIn("git fetch", output)
            install.assert_not_called()

    def test_copilot_suggestions_work_and_retired_items_are_not_installed(self):
        self.assertEqual(self.run_cli("suggested", "status", "--client", "copilot")[0], 0)
        code, output = self.run_cli("suggested", "install", "--client", "copilot", "--items", "last30days", "--yes")
        self.assertEqual(code, 1)
        self.assertIn("no longer suggested", output)

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

class OpenCodeSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.repo = self.base / "repo"
        self.home.mkdir()
        self.repo.mkdir()
        env = patch.dict("os.environ", {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.base / "xdg"),
                                        "OPENCODE_CONFIG_DIR": str(self.base / "opencode-config")}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        home_patch = patch.object(Path, "home", return_value=self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)

    def run_cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = setup.main(list(args))
        return result, output.getvalue()

    def test_opencode_roles_dry_run_global_and_repo_without_effort_line(self):
        code, output = self.run_cli("roles", "install", "--client", "opencode", "--roles", "reviewer", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn(str(self.home / ".config/opencode/agents/getonmylevel-reviewer.md"), output)
        self.assertNotIn("effort:", output)
        self.assertFalse((self.home / ".config").exists())
        code, output = self.run_cli("roles", "install", "--client", "opencode", "--scope", "both", "--repo", str(self.repo),
                                    "--roles", "reviewer", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn(str(self.repo / ".opencode/agents/getonmylevel-reviewer.md"), output)
        self.assertNotIn("effort:", output)

    def test_opencode_roles_reject_effort_and_preserve_model_on_update(self):
        code, output = self.run_cli("roles", "install", "--client", "opencode", "--roles", "reviewer",
                                    "--effort", "reviewer=high", "--yes")
        self.assertEqual(code, 1, output)
        self.assertIn("does not support a separate reasoning effort", output)
        self.assertIn("#variant", output)
        path = self.home / ".config/opencode/agents/getonmylevel-reviewer.md"
        self.assertFalse(path.exists())

        code, output = self.run_cli("roles", "install", "--client", "opencode", "--roles", "reviewer",
                                    "--model", "reviewer=anthropic/claude-x#high", "--yes")
        self.assertEqual(code, 0, output)
        self.assertIn('model: "anthropic/claude-x#high"', path.read_text(encoding="utf-8"))
        code, output = self.run_cli("roles", "update", "--client", "opencode", "--roles", "reviewer", "--yes")
        self.assertEqual(code, 0, output)
        self.assertIn('model: "anthropic/claude-x#high"', path.read_text(encoding="utf-8"))
        code, output = self.run_cli("roles", "update", "--client", "opencode", "--roles", "reviewer",
                                    "--model", "reviewer=", "--yes")
        self.assertEqual(code, 0, output)
        self.assertNotIn("model:", path.read_text(encoding="utf-8"))

    def test_opencode_roles_refuse_hand_edited_and_linked_files(self):
        import os

        code, output = self.run_cli("roles", "install", "--client", "opencode", "--roles", "reviewer", "--yes")
        self.assertEqual(code, 0, output)
        path = self.home / ".config/opencode/agents/getonmylevel-reviewer.md"
        path.write_text(path.read_text(encoding="utf-8") + "\nhand edit\n", encoding="utf-8")
        code, output = self.run_cli("roles", "update", "--client", "opencode", "--roles", "reviewer", "--yes")
        self.assertEqual(code, 1, output)
        self.assertIn("edited", output)

        path.unlink()
        target = self.base / "target.md"
        target.write_text("outside", encoding="utf-8")
        try:
            os.symlink(target, path)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"File symlinks unavailable: {exc}")
        code, output = self.run_cli("roles", "install", "--client", "opencode", "--roles", "reviewer", "--yes")
        self.assertEqual(code, 1, output)
        self.assertIn("linked", output)

    def test_opencode_suggested_status_and_manual_only_actions(self):
        code, output = self.run_cli("suggested", "status", "--client", "opencode")
        self.assertEqual(code, 0, output)
        code, output = self.run_cli("suggested", "install", "--client", "opencode", "--items", "cli_anything", "--dry-run")
        self.assertEqual(code, 1, output)
        self.assertIn("no longer suggested", output)
