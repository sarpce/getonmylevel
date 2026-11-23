"""Focused tests for the fixed CodeGraph install/configure command flow."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import codegraph_installer
import install_gui


class CodeGraphInstallTests(unittest.TestCase):
    class Variable:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    def test_codegraph_only_selection_skips_repository_scope_validation(self):
        installer = install_gui.Installer.__new__(install_gui.Installer)
        installer.selected = {"getonmylevel-context": self.Variable(False)}
        installer.codegraph_selected = self.Variable(True)
        installer.scope = self.Variable("repo")
        installer.repo_path = self.Variable("")
        plan = codegraph_installer.CodeGraphPlan(("codegraph",), None, "existing")
        with patch.object(codegraph_installer, "plan_install", return_value=plan), \
             patch.object(install_gui.common, "skill_roots", side_effect=AssertionError("skill scope is irrelevant")):
            names, roots, copies, instructions, selected_plan = installer.selections()
        self.assertEqual(names, [])
        self.assertEqual((roots, copies, instructions), ([], [], []))
        self.assertIs(selected_plan, plan)

    def test_context_selection_does_not_plan_codegraph_for_either_client(self):
        for client in ("codex", "claude"):
            with self.subTest(client=client):
                installer = install_gui.Installer.__new__(install_gui.Installer)
                installer.client = self.Variable(client)
                installer.selected = {"getonmylevel-context": self.Variable(True)}
                installer.codegraph_selected = self.Variable(False)
                installer.scope = self.Variable("user")
                with patch.object(codegraph_installer, "plan_install", side_effect=AssertionError("unexpected CodeGraph prerequisite check")), \
                     patch.object(install_gui.common, "skill_roots", return_value=[]), \
                     patch.object(install_gui.common, "preflight_skill_copy", return_value=[]), \
                     patch.object(install_gui.instruction_integration, "plan_instruction_updates", return_value=[]):
                    names, _, _, _, plan = installer.selections()
                self.assertEqual(names, ["getonmylevel-context"])
                self.assertIsNone(plan)

    def test_client_switch_keeps_independent_codegraph_choices_enabled(self):
        installer = install_gui.Installer.__new__(install_gui.Installer)
        installer.client = self.Variable("claude")
        installer.codegraph_selected = self.Variable(True)
        installer.codegraph_by_client = {"codex": True, "claude": False}
        installer.codegraph_check = Mock()
        installer.suggested_checks = []
        installer.suggested_button = Mock()
        installer.suggested_refresh_button = Mock()
        installer.refresh_preview = Mock()
        installer.client_changed()
        self.assertFalse(installer.codegraph_selected.get())
        installer.client.set("codex")
        installer.client_changed()
        self.assertTrue(installer.codegraph_selected.get())
        installer.codegraph_check.configure.assert_called_with(state="normal")

    def test_explicit_codegraph_plan_targets_each_client(self):
        for client in ("codex", "claude", "copilot"):
            with self.subTest(client=client):
                installer = install_gui.Installer.__new__(install_gui.Installer)
                installer.client = self.Variable(client)
                installer.selected = {"getonmylevel-context": self.Variable(False)}
                installer.codegraph_selected = self.Variable(True)
                plan = codegraph_installer.CodeGraphPlan(("codegraph",), None, "existing", client=client)
                with patch.object(codegraph_installer, "plan_install", return_value=plan) as planner:
                    self.assertIs(installer.selections()[-1], plan)
                planner.assert_called_once_with(client)
                if client == "copilot":
                    self.assertIn("--target=copilot-cli,copilot-vscode", plan.commands[-1])
                else:
                    self.assertIn(f"--target={client}", plan.commands[-1])

    def test_copilot_codegraph_configuration_targets_cli_and_vscode_together(self):
        self.assertEqual(codegraph_installer.install_args("copilot"),
                         ("install", "--target=copilot-cli,copilot-vscode", "--location=global", "--yes"))

    def test_codegraph_only_preview_and_confirmation_describe_actual_actions(self):
        for client in ("codex", "claude"):
            with self.subTest(client=client):
                installer = install_gui.Installer.__new__(install_gui.Installer)
                installer.client = self.Variable(client)
                installer.selected = {"getonmylevel-context": self.Variable(False)}
                installer.codegraph_selected = self.Variable(True)
                installer.preview = Mock()
                installer.install_busy = False
                plan = codegraph_installer.CodeGraphPlan(("codegraph",), None, "existing", client=client)
                with patch.object(codegraph_installer, "plan_install", return_value=plan), \
                     patch.object(install_gui.messagebox, "askyesno", return_value=False) as confirm:
                    installer.refresh_preview()
                    installer.install()
                preview = installer.preview.insert.call_args.args[1]
                confirmation = confirm.call_args.args[1]
                for text in (preview, confirmation):
                    self.assertIn(f"--target={client}", text)
                    self.assertIn("MCP configuration and managed instructions", text)
                    self.assertIn("No project", text)
                    self.assertNotIn("read these skills", text)
                self.assertNotIn("npm install", preview)

    def test_configuration_uses_fixed_global_codex_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            cli = Path(directory) / "codegraph"
            cli.touch()
            plan = codegraph_installer.CodeGraphPlan((str(cli),), None, "existing")
            with patch.object(codegraph_installer, "_run", return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
                result = codegraph_installer.install(plan)
        self.assertIn("configured for Codex globally", result)
        self.assertEqual(run.call_args.args[0], (str(cli), *codegraph_installer.INSTALL_ARGS))

    def test_failed_package_install_does_not_configure_codex(self):
        plan = codegraph_installer.CodeGraphPlan(("node", "space path/codegraph.js"),
                                                 ("node", "npm-cli.js", "install", "-g", codegraph_installer.PINNED_PACKAGE),
                                                 "install")
        with patch.object(codegraph_installer, "_run", return_value=subprocess.CompletedProcess([], 1, "", "install failed")) as run:
            with self.assertRaisesRegex(RuntimeError, "status 1"):
                codegraph_installer.install(plan)
        run.assert_called_once_with(plan.npm_install)

    def test_missing_cli_after_install_does_not_configure_codex(self):
        plan = codegraph_installer.CodeGraphPlan(("node", "missing/codegraph.js"), ("npm", "install"), "install")
        completed = subprocess.CompletedProcess([], 0, "", "")
        with patch.object(codegraph_installer, "_run", return_value=completed) as run:
            with self.assertRaisesRegex(RuntimeError, "Codex was not configured"):
                codegraph_installer.install(plan)
        run.assert_called_once_with(plan.npm_install)

    def test_plan_lists_install_before_global_configuration(self):
        plan = codegraph_installer.CodeGraphPlan(("node", "npm prefix/codegraph.js"),
                                                 ("node", "npm-cli.js", "install", "-g", codegraph_installer.PACKAGE),
                                                 "missing")
        self.assertEqual(plan.commands, (plan.npm_install,
                                         (*plan.executable, *codegraph_installer.INSTALL_ARGS)))

    def test_new_install_uses_exact_selected_package_version(self):
        with patch.object(codegraph_installer.shutil, "which", return_value=None), \
             patch.object(codegraph_installer, "_windows_node_npm", return_value=(Path("node"), Path("npm-cli.js"))), \
             patch.object(codegraph_installer, "_prefix", return_value=Path("C:/npm")):
            plan = codegraph_installer.plan_install()
        self.assertIn(codegraph_installer.PINNED_PACKAGE, plan.npm_install)
        self.assertIn(codegraph_installer.PINNED_PACKAGE, plan.details)


if __name__ == "__main__":
    unittest.main()
