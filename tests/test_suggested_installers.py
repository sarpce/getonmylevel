"""Tests for pinned optional installer behavior without external installers."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

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

    def test_ui_ux_pro_max_confirmation_discloses_client_adaptation(self):
        from unittest.mock import patch
        for client, expected in (("codex", "upstream Claude plugin-root examples"),
                                 ("claude", "CLAUDE_PLUGIN_ROOT")):
            with self.subTest(client=client), patch.object(installers, "_git_path", return_value="git"), \
                 patch.object(installers, "_safe_destination", return_value=None), \
                 patch.object(installers, "_skill_roots", return_value=(Path("/user/skills"),)), \
                 patch.object(installers, "_skill_destinations", return_value=()):
                plan, error = installers._design_skill_plan("ui_ux_pro_max", client)
            self.assertIsNone(error)
            self.assertIn(expected, plan.confirmation_text)

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
            with patch.object(installers, "_skill_roots", side_effect=lambda client="codex": (root,) if client == "codex" else (root.parent / "claude-skills",)), \
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

    def test_refresh_enables_safe_claude_skill_actions_and_disables_cli_anything(self):
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
                self.assertEqual(check.configure.call_args.kwargs["state"], "disabled" if item_id == "cli_anything" else "normal")

    def test_claude_custom_config_root_is_selected_and_codex_removal_stays_distinct(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "claude-config"
            codex = Path(temp) / "codex-skills"
            claude_root = config / "skills"
            codex.mkdir(parents=True)
            claude_root.mkdir(parents=True)
            cskill = claude_root / "last30days"
            xskill = codex / "last30days"
            for skill in (cskill, xskill):
                skill.mkdir()
                (skill / "SKILL.md").write_text("skill", encoding="utf-8")
            with patch.dict("os.environ", {"CLAUDE_CONFIG_DIR": str(config)}), \
                 patch.object(installers, "_skill_roots", side_effect=lambda client="codex": (claude_root,) if client == "claude" else (codex,)):
                self.assertEqual(installers.suggested_status("claude")["last30days"], (cskill,))
                plan, error = installers.plan_removal("last30days", "claude")
                self.assertIsNone(error)
                self.assertEqual(plan.destinations[0][0], cskill)
                result = installers.remove_selected([plan])
            self.assertTrue(result[0][1])
            self.assertTrue(xskill.exists())

    def test_pinned_plan_uses_claude_destination_and_impeccable_source(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp, patch.object(installers, "_git_path", return_value="git"), \
             patch.object(installers, "_safe_destination", return_value=None), \
             patch.object(installers, "_skill_roots", return_value=(Path(temp) / "skills",)), \
             patch.object(installers, "_skill_destinations", return_value=()):
            plan, error = installers._design_skill_plan("impeccable", "claude")
        self.assertIsNone(error)
        self.assertEqual(plan.destination, Path(temp) / "skills" / "impeccable")
        self.assertIn(".claude/skills/impeccable", plan.data)
        self.assertEqual(plan.data[3:6], ("SKILL.md", "reference", "scripts"))
        self.assertEqual(plan.client, "claude")

    def test_claude_marketplace_registration_blocks_skill_removal_and_bad_registry_fails_closed(self):
        import json
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp)
            plugin_dir = config / "plugins"
            plugin_dir.mkdir()
            registry = plugin_dir / "installed_plugins.json"
            registry.write_text(json.dumps({"plugins": {"last30days@last30days-skill": [{"scope": "user"}]}}), encoding="utf-8")
            with patch.dict("os.environ", {"CLAUDE_CONFIG_DIR": str(config)}):
                self.assertTrue(installers.suggested_status("claude")["last30days"])
                plan, error = installers.plan_removal("last30days", "claude")
                self.assertIsNone(plan)
                self.assertIn("/plugin", error)
                registry.write_text("not json", encoding="utf-8")
                with self.assertRaises(ValueError):
                    installers.suggested_status("claude")

    def test_status_retains_both_claude_skill_and_marketplace_registration(self):
        from unittest.mock import patch
        skill = Path("/claude/skills/last30days")
        registry = Path("/claude/plugins/installed_plugins.json")
        with patch.object(installers, "_skill_destinations", return_value=(skill,)), \
             patch.object(installers, "_claude_plugin_status", return_value={"last30days": str(registry)}), \
             patch.object(installers.shutil, "which", return_value=None):
            status = installers.suggested_status("claude")
            details = installers.integration_details("last30days", status["last30days"], client="claude")
        self.assertEqual(status["last30days"], (skill, registry))
        self.assertIn("Detected skill copy", details)
        self.assertIn("marketplace plugin registration", details)

    def test_removal_refuses_aliased_client_roots(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "shared"
            root.mkdir()
            skill = root / "last30days"
            skill.mkdir()
            (skill / "SKILL.md").write_text("skill", encoding="utf-8")
            with patch.object(installers, "_skill_roots", return_value=(root,)), \
                 patch.object(installers, "_skill_destinations", return_value=(skill,)):
                plan, error = installers.plan_removal("last30days", "claude")
        self.assertIsNone(plan)
        self.assertIn("same physical path", error)

    def test_plugin_appearing_after_last30_planning_blocks_execution(self):
        from unittest.mock import patch
        destination = Path("/claude/skills/last30days")
        plan = installers.SuggestedInstallPlan("last30days", "Last 30 Days", destination, "details", (), data=("git",), client="claude")
        with patch.object(installers, "_claude_plugin_status", return_value={"last30days": "/claude/plugins/installed_plugins.json"}), \
             patch.object(installers, "_ensure_no_alternate_install") as alternate, \
             patch.object(installers, "_safe_destination") as safe:
            ok, detail = installers._install_last30(plan)
        self.assertFalse(ok)
        self.assertIn("appeared after planning", detail)
        alternate.assert_not_called()
        safe.assert_not_called()

    def test_plugin_appearing_after_design_planning_blocks_execution(self):
        from unittest.mock import patch
        destination = Path("/claude/skills/impeccable")
        plan = installers.SuggestedInstallPlan("impeccable", "Impeccable", destination, "details", (),
                                               data=("git", installers.IMPECCABLE_COMMIT,
                                                     ".claude/skills/impeccable", "SKILL.md", "reference", "scripts", "agents"),
                                               client="claude")
        with patch.object(installers, "_claude_plugin_status", return_value={"impeccable": "/claude/plugins/installed_plugins.json"}), \
             patch.object(installers, "_ensure_no_alternate_install") as alternate, \
             patch.object(installers, "_safe_destination") as safe:
            ok, detail = installers._design_skill_installer(plan)
        self.assertFalse(ok)
        self.assertIn("appeared after planning", detail)
        alternate.assert_not_called()
        safe.assert_not_called()

    def test_plugin_appearing_after_removal_planning_blocks_execution(self):
        from unittest.mock import patch
        skill = Path("/claude/skills/last30days")
        plan = installers.SuggestedRemovalPlan("last30days", "Last 30 Days", ((skill, (1, 2)),), client="claude")
        with patch.object(installers, "_skill_roots", side_effect=lambda client="codex": (Path("/codex/skills"),) if client == "codex" else (Path("/claude/skills"),)), \
             patch.object(installers, "_claude_plugin_status", return_value={"last30days": "/claude/plugins/installed_plugins.json"}), \
             patch.object(installers.shutil, "rmtree") as remove:
            result = installers.remove_selected([plan])
        self.assertFalse(result[0][1])
        self.assertIn("marketplace plugin is registered", result[0][2])
        remove.assert_not_called()

    def test_details_are_client_specific_for_cli_and_skill_adaptations(self):
        codex_cli = installers.integration_details("cli_anything", client="codex")
        claude_cli = installers.integration_details("cli_anything", client="claude")
        codex_uipro = installers.integration_details("ui_ux_pro_max", client="codex")
        claude_uipro = installers.integration_details("ui_ux_pro_max", client="claude")
        self.assertIn("destination:", codex_cli)
        self.assertIn("executes its upstream installer", codex_cli)
        self.assertIn("none by this GUI", claude_cli)
        self.assertIn("No automatic action is offered", claude_cli)
        self.assertIn("Claude skill examples", codex_uipro)
        self.assertIn("replaces Claude plugin-root paths", claude_uipro)

    def test_distinct_client_copies_do_not_block_install_planning(self):
        from unittest.mock import patch
        codex_skill = Path("/codex/skills/last30days")
        with patch.object(installers, "_git_path", return_value="git"), \
             patch.object(installers, "_skill_roots", side_effect=lambda client="codex": (Path("/codex/skills"),) if client == "codex" else (Path("/claude/skills"),)), \
             patch.object(installers, "_skill_destinations", side_effect=lambda item, client="codex": (codex_skill,) if client == "codex" else ()), \
             patch.object(installers, "_safe_destination", return_value=None):
            plan, error = installers._last30_plan("claude")
        self.assertIsNone(error)
        self.assertEqual(plan.destination, Path("/claude/skills/last30days"))

    def test_gui_keeps_codex_cli_anything_enabled_and_clears_selection_on_client_change(self):
        from unittest.mock import Mock, patch
        import install_gui
        installer = install_gui.Installer.__new__(install_gui.Installer)
        installer.client = type("Variable", (), {"get": lambda self: "codex"})()
        installer.suggested_labels = {}
        installer.suggested_selected = {}
        installer.suggested_actions = {}
        installer.suggested_busy = False
        installer.suggested_refresh_button = Mock()
        for item in installers.SUGGESTED_ITEMS:
            check, detail, selected = Mock(), Mock(), Mock()
            installer.suggested_labels[item.id] = (check, detail)
            installer.suggested_selected[item.id] = selected
        with patch.object(installers, "suggested_status", return_value={"rtk": None, **{item.id: () for item in installers.SUGGESTED_ITEMS if item.id != "rtk"}}):
            installer.refresh_suggested_status()
        self.assertEqual(installer.suggested_labels["cli_anything"][0].configure.call_args.kwargs["state"], "normal")
        installed = Path("/codex/skills/cli-anything")
        with patch.object(installers, "suggested_status", return_value={"rtk": None, "cli_anything": (installed,),
                      **{item.id: () for item in installers.SUGGESTED_ITEMS if item.id not in ("rtk", "cli_anything")}}):
            installer.refresh_suggested_status()
        self.assertEqual(installer.suggested_labels["cli_anything"][0].configure.call_args.kwargs["state"], "normal")
        installer.load_activation = Mock()
        installer.refresh_skill_status = Mock()
        installer.codegraph_by_client = {"codex": False}
        installer.codegraph_selected = Mock()
        installer.codegraph_check = Mock()
        installer.codegraph_description = Mock()
        installer.suggested_button = Mock()
        installer.refresh_preview = Mock()
        installer.refresh_codegraph_status = Mock()
        for variable in installer.suggested_selected.values():
            variable.set.reset_mock()
        installer.client_changed()
        for variable in installer.suggested_selected.values():
            variable.set.assert_called_with(False)


if __name__ == "__main__":
    unittest.main()

class OpenCodeSuggestedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        home_patch = patch.object(Path, "home", return_value=self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)
        env = patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.base / "elsewhere-claude")}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        git = patch.object(installers, "_git_path", return_value="/usr/bin/git")
        git.start()
        self.addCleanup(git.stop)
        self.own_root = self.home / ".config" / "opencode" / "skills"

    def make_copy(self, root: Path, name: str) -> Path:
        copy = root / name
        copy.mkdir(parents=True, exist_ok=True)
        (copy / "SKILL.md").write_text("skill", encoding="utf-8")
        return copy

    def test_opencode_destinations_for_all_four_skills_are_opencode_owned(self):
        ids = ["last30days", "impeccable", "ui_ux_pro_max", "anti_ui_slop"]
        plans, error = installers.plan_selected(ids, "opencode")
        self.assertIsNone(error)
        self.assertEqual(sorted(plan.id for plan in plans), sorted(ids))
        for plan in plans:
            with self.subTest(item=plan.id):
                self.assertEqual(plan.destination.parent, self.own_root)
        impeccable = next(plan for plan in plans if plan.id == "impeccable")
        self.assertEqual(impeccable.data[2], ".opencode/skills/impeccable")
        self.assertEqual(impeccable.data[3:6], ("SKILL.md", "reference", "scripts"))
        ui_ux = next(plan for plan in plans if plan.id == "ui_ux_pro_max")
        self.assertIn("Its OpenCode skill path", ui_ux.details)
        details = installers.integration_details("ui_ux_pro_max", client="opencode")
        self.assertIn("OpenCode", details)

    def test_opencode_refuses_last30_when_claude_or_agents_copy_exists(self):
        import shutil

        for label, root in (("claude", self.home / ".claude" / "skills"), ("agents", self.home / ".agents" / "skills")):
            with self.subTest(copy=label):
                copy = self.make_copy(root, "last30days")
                plan, error = installers._last30_plan("opencode")
                self.assertIsNone(plan)
                self.assertIn("Already installed", error)
                self.assertIn("OpenCode also discovers", error)
                shutil.rmtree(copy)

    def test_opencode_status_and_removal_ignore_other_client_copies(self):
        own = self.make_copy(self.own_root, "last30days")
        self.make_copy(self.home / ".claude" / "skills", "last30days")
        self.assertEqual(installers.suggested_status("opencode")["last30days"], (own,))
        plan, error = installers.plan_removal("last30days", "opencode")
        self.assertIsNone(error)
        self.assertEqual(tuple(path for path, _identity in plan.destinations), (own,))

    def test_opencode_root_aliasing_blocks_removal_in_every_direction(self):
        self.make_copy(self.own_root, "last30days")
        with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.home / ".config" / "opencode")}):
            plan, error = installers.plan_removal("last30days", "opencode")
            self.assertIsNone(plan)
            self.assertIn("OpenCode and Claude skill roots", error)
            self.assertIn("same physical path", error)
            plan, error = installers.plan_removal("last30days", "claude")
            self.assertIsNone(plan)
            self.assertIn("same physical path", error)
            removal = installers.SuggestedRemovalPlan("last30days", "Last 30 Days research skill", (), client="opencode")
            results = installers.remove_selected([removal])
        self.assertFalse(results[0][1])
        self.assertIn("same physical path", results[0][2])

    def test_codex_install_notes_an_existing_opencode_copy(self):
        self.make_copy(self.own_root, "last30days")
        plan, error = installers._last30_plan("codex")
        self.assertIsNone(error)
        self.assertIn("OpenCode also discovers", plan.details)

    def test_opencode_cli_anything_and_status_text_are_manual(self):
        plans, error = installers.plan_selected(["cli_anything"], "opencode")
        self.assertIsNone(plans)
        self.assertIn("OpenCode", error)
        self.assertIn("manual", error)
        details = installers.integration_details("cli_anything", client="opencode")
        self.assertIn("OpenCode action unavailable", details)

    def test_gui_refresh_for_opencode_disables_only_cli_anything(self):
        from unittest.mock import Mock
        import install_gui

        installer = install_gui.Installer.__new__(install_gui.Installer)
        installer.client = type("Variable", (), {"get": lambda self: "opencode"})()
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
                self.assertEqual(check.configure.call_args.kwargs["state"],
                                 "disabled" if item_id == "cli_anything" else "normal")
