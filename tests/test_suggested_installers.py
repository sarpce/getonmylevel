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

    def test_ui_skill_plans_include_reviewed_pins_and_copy_only_effects(self):
        from unittest.mock import patch

        for item_id, commit in (
            ("impeccable", installers.IMPECCABLE_COMMIT),
            ("ui_ux_pro_max", installers.UI_UX_PRO_MAX_COMMIT),
            ("anti_ui_slop", installers.ANTI_UI_SLOP_COMMIT),
        ):
            with self.subTest(item_id=item_id), patch.object(installers, "_git_path", return_value="git"), \
                 patch.object(installers, "_safe_destination", return_value=None), \
                 patch.object(installers, "_skill_destinations", return_value=()):
                plan, error = installers._design_skill_plan(item_id)

            self.assertIsNone(error)
            self.assertIn(commit, plan.confirmation_text)
            self.assertIn("does not execute", plan.confirmation_text)
            self.assertIn("ls-tree", " ".join(plan.commands[-2]))

    def test_selected_skill_tree_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            checkout = root / "checkout"
            checkout.mkdir()
            self.git("init", str(checkout))
            self.git("-C", str(checkout), "config", "user.email", "test@example.invalid")
            self.git("-C", str(checkout), "config", "user.name", "Test")
            (checkout / "skill").mkdir()
            (checkout / "skill" / "SKILL.md").write_text("skill\n", encoding="utf-8")
            link_blob = self.git("-C", str(checkout), "hash-object", "-w", "--stdin", cwd=None)

            self.assertTrue(link_blob)
            self.git("-C", str(checkout), "add", "skill/SKILL.md")
            self.git("-C", str(checkout), "update-index", "--add", "--cacheinfo", f"120000,{link_blob},skill/link")
            self.git("-C", str(checkout), "commit", "-m", "skill")
            commit = self.git("-C", str(checkout), "rev-parse", "HEAD")

            ok, detail = installers._validate_git_tree("git", checkout, commit, ("skill",))

            self.assertFalse(ok)
            self.assertIn("symlink", detail)

    def test_selected_skill_status_and_removal_cover_new_ids(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "skills"
            root.mkdir()
            skill = root / "impeccable"
            skill.mkdir()
            (skill / "SKILL.md").write_text("name: impeccable\n", encoding="utf-8")
            with patch.object(installers, "_skill_roots", return_value=(root,)), \
                 patch.object(installers.shutil, "which", return_value=None):
                self.assertEqual(installers.suggested_status()["impeccable"], (skill,))
                plan, error = installers.plan_removal("impeccable")

            self.assertIsNone(error)
            self.assertEqual(plan.destinations[0][0], skill)

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
        self.assertIn("Not detected on PATH", detail.configure.call_args.kwargs["text"])

    def test_details_distinguish_detection_pin_and_unknown_existing_provenance(self):
        for item in installers.SUGGESTED_ITEMS:
            with self.subTest(item=item.id):
                details = installers.integration_details(item.id, (Path("/detected/copy"),))
                self.assertIn(item.upstream_url, details)
                self.assertIn("Detected", details)
                self.assertIn("version", details.lower())
                self.assertIn("unknown", details.lower())
                self.assertIn("Provenance: unknown", details)
                if item.id == "rtk":
                    self.assertIn("manual installation only", details)
                else:
                    self.assertIn("selected pin", details)
                    self.assertIn("commit", details)
                self.assertIn("Installation effects:", details)

    def test_details_report_unknown_when_status_detection_fails(self):
        details = installers.integration_details("last30days", detection_error="permission denied")
        self.assertIn("Status: Unknown", details)
        self.assertIn("permission denied", details)

    def test_gui_refresh_displays_unknown_after_detection_failure(self):
        from unittest.mock import Mock, patch
        import install_gui
        installer = install_gui.Installer.__new__(install_gui.Installer)
        check, detail, selected = Mock(), Mock(), Mock()
        installer.suggested_labels = {"last30days": (check, detail)}
        installer.suggested_selected = {"last30days": selected}
        installer.suggested_actions = {}
        installer.suggested_busy = False
        installer.suggested_refresh_button = Mock()
        with patch.object(installers, "suggested_status", side_effect=PermissionError("permission denied")):
            installer.refresh_suggested_status()
        self.assertIn("Status unknown", detail.configure.call_args.kwargs["text"])
        self.assertEqual(check.configure.call_args.kwargs["state"], "disabled")
        selected.set.assert_called_with(False)

    def test_refresh_keeps_suggested_install_actions_codex_only(self):
        from unittest.mock import Mock, patch
        import install_gui
        installer = install_gui.Installer.__new__(install_gui.Installer)
        installer.client = type("Variable", (), {"get": lambda self: "claude"})()
        installer.suggested_labels = {}
        installer.suggested_selected = {}
        installer.suggested_actions = {}
        installer.suggested_busy = False
        installer.suggested_refresh_button = Mock()
        for item in installers.SUGGESTED_ITEMS:
            check, detail, selected = Mock(), Mock(), Mock()
            installer.suggested_labels[item.id] = (check, detail)
            installer.suggested_selected[item.id] = selected
        with patch.object(installers, "suggested_status", return_value={
            "rtk": None, **{item.id: () for item in installers.SUGGESTED_ITEMS if item.id != "rtk"}
        }):
            installer.refresh_suggested_status()
        for item_id, (check, _) in installer.suggested_labels.items():
            with self.subTest(item_id=item_id):
                if item_id == "rtk":
                    continue
                self.assertEqual(check.configure.call_args.kwargs["state"], "disabled")


if __name__ == "__main__":
    unittest.main()
