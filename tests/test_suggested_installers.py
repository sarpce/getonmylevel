"""Tests for evidence-gated suggested skills without network access."""

import dataclasses
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import common  # noqa: E402
import suggested_installers as installers  # noqa: E402


def git(*args, cwd=None):
    return subprocess.run(("git", "-c", "core.autocrlf=false", *args), cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


class PinnedCloneTests(unittest.TestCase):
    def test_local_pinned_fetch_checks_out_exact_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            git("init", str(source))
            git("-C", str(source), "config", "user.email", "test@example.invalid")
            git("-C", str(source), "config", "user.name", "Test")
            (source / "payload.txt").write_text("selected\n", encoding="utf-8")
            git("-C", str(source), "add", "payload.txt")
            git("-C", str(source), "commit", "-m", "selected")
            selected = git("-C", str(source), "rev-parse", "HEAD")
            (source / "payload.txt").write_text("moving head\n", encoding="utf-8")
            git("-C", str(source), "commit", "-am", "later")
            checkout = root / "checkout"
            ok, detail = installers._clone("git", str(source), selected, checkout)
            self.assertTrue(ok, detail)
            self.assertEqual(git("-C", str(checkout), "rev-parse", "HEAD"), selected)
            self.assertEqual((checkout / "payload.txt").read_text(encoding="utf-8"), "selected\n")

    def test_failed_pinned_fetch_reports_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            source.mkdir()
            git("init", str(source))
            ok, detail = installers._clone("git", str(source), "0" * 40, Path(temp) / "checkout")
            self.assertFalse(ok)
            self.assertTrue(detail)


class SuggestedSkillTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        self.home = base / "home"
        self.home.mkdir()
        # Local upstream with the same layout as the pinned repository.
        self.upstream = base / "upstream"
        skill = self.upstream / "skills" / "golang-spf13-viper"
        (skill / "references").mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: golang-spf13-viper\ndescription: test\n---\nbody\n", encoding="utf-8")
        (skill / "references" / "env.md").write_text("ref\n", encoding="utf-8")
        (self.upstream / "LICENSE").write_text("MIT License\n", encoding="utf-8")
        git("init", "-q", str(self.upstream))
        git("-C", str(self.upstream), "add", "-A")
        git("-C", str(self.upstream), "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "skill")
        commit = git("-C", str(self.upstream), "rev-parse", "HEAD")
        local = dataclasses.replace(installers._BY_ID["go_viper"], repo=str(self.upstream), commit=commit)
        for patcher in (mock.patch.dict(installers._BY_ID, {"go_viper": local}),
                        mock.patch.object(Path, "home", return_value=self.home),
                        mock.patch.dict(os.environ, {"CODEX_HOME": str(self.home / ".codex"),
                                                     "CLAUDE_CONFIG_DIR": str(self.home / ".claude")})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_every_suggestion_records_its_evidence_and_bloat_is_gone(self):
        ids = {item.id for item in installers.SUGGESTED_ITEMS}
        self.assertEqual(ids, {"go_viper", "go_testify"})
        for item in installers.SUGGESTED_ITEMS:
            self.assertTrue(item.evidence)
            self.assertRegex(item.commit, r"^[0-9a-f]{40}$")
        self.assertTrue({"impeccable", "ui_ux_pro_max", "anti_ui_slop", "last30days", "cli_anything"} <= set(installers.RETIRED_ITEMS))

    def test_install_and_remove_for_every_client(self):
        for client in common.CLIENTS:
            with self.subTest(client=client):
                plans, error = installers.plan_selected(["go_viper"], client)
                self.assertIsNone(error)
                (name, ok, detail), = installers.install_selected(plans)
                self.assertTrue(ok, detail)
                destination = common.skill_roots("user", None, client)[0] / "golang-spf13-viper"
                self.assertTrue((destination / "references" / "env.md").is_file())
                self.assertEqual((destination / "LICENSE.upstream").read_text(encoding="utf-8"), "MIT License\n")
                self.assertEqual(installers.suggested_status(client)["go_viper"], (destination,))
                removal, error = installers.plan_removal("go_viper", client)
                self.assertIsNone(error)
                (_name, ok, detail), = installers.remove_selected([removal])
                self.assertTrue(ok, detail)
                self.assertFalse(destination.exists())
                self.assertTrue(any((destination.parent.parent / "getonmylevel-backups").iterdir()))

    def test_opencode_refuses_a_second_copy_it_would_also_discover(self):
        plans, _ = installers.plan_selected(["go_viper"], "claude")
        installers.install_selected(plans)
        plans, error = installers.plan_selected(["go_viper"], "opencode")
        self.assertIsNone(plans)
        self.assertIn("already present", error)

    def test_retired_suggestions_can_still_be_removed(self):
        old = common.skill_roots("user", None, "claude")[0] / "impeccable"
        old.mkdir(parents=True)
        (old / "SKILL.md").write_text("old", encoding="utf-8")
        self.assertEqual(installers.retired_status("claude"), {"impeccable": (old,)})
        plan, error = installers.plan_removal("impeccable", "claude")
        self.assertIsNone(error)
        installers.remove_selected([plan])
        self.assertFalse(old.exists())

    def test_setup_cli_supports_copilot_and_requires_yes(self):
        import setup
        with mock.patch.object(sys, "stdout", io.StringIO()) as out:
            self.assertEqual(setup.main(["suggested", "status", "--client", "copilot"]), 0)
        self.assertIn("Go: spf13/viper", out.getvalue())
        with mock.patch.object(sys, "stdout", io.StringIO()), mock.patch.object(sys, "stderr", io.StringIO()) as err:
            self.assertEqual(setup.main(["suggested", "install", "--client", "copilot", "--items", "go_viper"]), 2)
        self.assertIn("--yes", err.getvalue())
        self.assertFalse((self.home / ".copilot" / "skills" / "golang-spf13-viper").exists())


if __name__ == "__main__":
    unittest.main()
