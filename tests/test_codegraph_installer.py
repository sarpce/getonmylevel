"""Focused tests for the fixed CodeGraph install/configure command flow."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import codegraph_installer
import install_gui


class CodeGraphInstallTests(unittest.TestCase):
    class Variable:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

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
                                                 ("node", "npm-cli.js", "install", "-g", codegraph_installer.PACKAGE),
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


if __name__ == "__main__":
    unittest.main()
