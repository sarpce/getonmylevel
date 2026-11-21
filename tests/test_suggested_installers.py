"""Tests for pinned optional installer behavior without external installers."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import suggested_installers as installers


class PinnedInstallerTests(unittest.TestCase):
    def git(self, *args, cwd=None):
        return subprocess.run(("git", *args), cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()

    def test_local_pinned_fetch_checks_out_exact_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            self.git("init", str(source))
            self.git("-C", str(source), "config", "user.email", "test@example.invalid")
            self.git("-C", str(source), "config", "user.name", "Test")
            (source / "payload.txt").write_text("selected\n", encoding="utf-8")
            self.git("-C", str(source), "add", "payload.txt")
            self.git("-C", str(source), "commit", "-m", "selected")
            selected = self.git("-C", str(source), "rev-parse", "HEAD")
            (source / "payload.txt").write_text("moving head\n", encoding="utf-8")
            self.git("-C", str(source), "commit", "-am", "later")
            checkout = root / "checkout"

            ok, detail = installers._clone("git", str(source), selected, checkout)

            self.assertTrue(ok, detail)
            self.assertEqual(self.git("-C", str(checkout), "rev-parse", "HEAD"), selected)
            self.assertEqual((checkout / "payload.txt").read_text(encoding="utf-8"), "selected\n")

    def test_failed_pinned_fetch_prevents_checkout_contents(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            source.mkdir()
            self.git("init", str(source))
            checkout = Path(temp) / "checkout"
            ok, detail = installers._clone("git", str(source), "0" * 40, checkout)
            self.assertFalse(ok)
            self.assertFalse((checkout / "SKILL.md").exists())
            self.assertTrue(detail)

    def test_rtk_plan_refuses_floating_manager_install(self):
        from unittest.mock import patch
        with patch.object(installers.shutil, "which", return_value=None):
            plan, error = installers._rtk_plan("Windows", manager_path="winget")
        self.assertIsNone(plan)
        self.assertIn("moving package versions", error)

    def test_confirmation_displays_selected_commit_and_installer_effect(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp, patch.object(installers, "_git_path", return_value="git"), \
             patch.object(installers, "_safe_destination", return_value=None), \
             patch.object(installers, "_skill_destinations", return_value=()), \
             patch.object(installers, "_cli_destination", return_value=Path(temp) / "cli-anything"), \
             patch.object(installers.shutil, "which", return_value="bash"):
            plan, error = installers._cli_plan("Linux")
        self.assertIsNone(error)
        self.assertIn(installers.CLI_ANYTHING_COMMIT, plan.confirmation_text)
        self.assertIn("executing its installer with your privileges", plan.confirmation_text)

    def test_rtk_absent_status_explains_manual_only_installation(self):
        from unittest.mock import Mock, patch
        import install_gui
        installer = install_gui.Installer.__new__(install_gui.Installer)
        check, detail, selected = Mock(), Mock(), Mock()
        selected.get.return_value = False
        installer.suggested_labels = {"rtk": (check, detail)}
        installer.suggested_selected = {"rtk": selected}
        installer.suggested_actions = {}
        installer.suggested_busy = False
        installer.suggested_refresh_button = Mock()
        with patch.object(installers, "suggested_status", return_value={"rtk": None, "last30days": (), "cli_anything": ()}):
            installer.refresh_suggested_status()
        self.assertIn("manual installation only", check.configure.call_args.kwargs["text"])
        self.assertEqual(check.configure.call_args.kwargs["state"], "disabled")
        self.assertIn("package-manager versions move", detail.configure.call_args.kwargs["text"])
        self.assertIn(installers.RTK_INSTALL_URL, detail.configure.call_args.kwargs["text"])


if __name__ == "__main__":
    unittest.main()
