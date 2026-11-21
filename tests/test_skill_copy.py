from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import common
import instruction_integration as integration


class SkillCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.source = self.base / "source"
        self.root = self.base / ".agents" / "skills"
        self.names = common.SKILL_NAMES[:3]
        for name in self.names:
            skill = self.source / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("new " + name, encoding="utf-8")
            (skill / "nested").mkdir()
            (skill / "nested" / "resource.txt").write_text("resource", encoding="utf-8")

    def existing(self, name):
        destination = self.root / name
        destination.mkdir(parents=True)
        (destination / "SKILL.md").write_text("old", encoding="utf-8")
        (destination / "local.txt").write_text("local edits", encoding="utf-8")
        return destination

    def plan(self, names=None):
        return common.preflight_skill_copy(self.source, names or self.names[:1], [self.root])

    def assert_no_staging(self):
        self.assertEqual(list(self.root.glob(".getonmylevel-stage-*")), [])

    def test_fresh_install_copies_full_tree_without_backup(self):
        copies = self.plan()
        self.assertFalse(self.root.exists())
        result = common.copy_skills(copies)
        destination = self.root / self.names[0]
        self.assertEqual(result, common.SkillCopyResult((str(destination),), (), ()))
        self.assertEqual((destination / "SKILL.md").read_text(encoding="utf-8"), "new " + self.names[0])
        self.assertEqual((destination / "nested" / "resource.txt").read_text(encoding="utf-8"), "resource")
        self.assertFalse((self.root.parent / "getonmylevel-backups").exists())
        self.assert_no_staging()

    def test_update_preserves_original_in_unique_backups(self):
        destination = self.existing(self.names[0])
        first = common.copy_skills(self.plan())
        backup, = map(Path, first.backups)
        self.assertEqual(first.updated, (str(destination),))
        self.assertEqual((backup / destination.name / "local.txt").read_text(encoding="utf-8"), "local edits")
        self.assertFalse((destination / "local.txt").exists())
        self.assertEqual((destination / "SKILL.md").read_text(encoding="utf-8"), "new " + destination.name)
        second = common.copy_skills(self.plan())
        self.assertNotEqual(first.backups, second.backups)
        self.assertTrue((backup / destination.name / "local.txt").exists())
        self.assertEqual((Path(second.backups[0]) / destination.name / "SKILL.md").read_text(encoding="utf-8"), "new " + destination.name)
        self.assert_no_staging()

    def test_failed_update_restores_original_and_cleans_staging(self):
        destination = self.existing(self.names[0])
        real_rename = Path.rename

        def fail_staged_move(path, target):
            if path.name == "skill" and path.parent.name.startswith(".getonmylevel-stage-"):
                raise OSError("injected install failure")
            return real_rename(path, target)

        with mock.patch.object(Path, "rename", fail_staged_move):
            with self.assertRaisesRegex(common.SkillCopyError, "injected install failure") as caught:
                common.copy_skills(self.plan())
        self.assertEqual((caught.exception.installed, caught.exception.updated, caught.exception.backups), ((), (), ()))
        self.assertEqual((destination / "local.txt").read_text(encoding="utf-8"), "local edits")
        self.assertEqual(list((self.root.parent / "getonmylevel-backups").iterdir()), [])
        self.assert_no_staging()

    def test_failed_restoration_reports_backup_containing_original(self):
        destination = self.existing(self.names[0])
        real_rename = Path.rename

        def fail_install_and_restore(path, target):
            if Path(target) == destination and path != destination:
                raise OSError("injected rename failure")
            return real_rename(path, target)

        with mock.patch.object(Path, "rename", fail_install_and_restore):
            with self.assertRaisesRegex(common.SkillCopyError, "Could not install update or restore original") as caught:
                common.copy_skills(self.plan())
        backup, = map(Path, caught.exception.backups)
        self.assertIn(str(backup), str(caught.exception))
        self.assertFalse(destination.exists())
        self.assertEqual((backup / destination.name / "local.txt").read_text(encoding="utf-8"), "local edits")
        self.assert_no_staging()

    def test_partial_batch_reports_completed_install_update_and_backup(self):
        updated = self.existing(self.names[1])
        copies = self.plan(self.names)
        real_copytree = common.shutil.copytree

        def fail_third(source, destination, *args, **kwargs):
            if Path(source).name == self.names[2]:
                raise OSError("injected copy failure")
            return real_copytree(source, destination, *args, **kwargs)

        with mock.patch.object(common.shutil, "copytree", side_effect=fail_third):
            with self.assertRaisesRegex(common.SkillCopyError, "injected copy failure") as caught:
                common.copy_skills(copies)
        error = caught.exception
        self.assertEqual(error.installed, (str(self.root / self.names[0]),))
        self.assertEqual(error.updated, (str(updated),))
        backup, = map(Path, error.backups)
        self.assertEqual((backup / updated.name / "local.txt").read_text(encoding="utf-8"), "local edits")
        self.assertFalse((self.root / self.names[2]).exists())
        self.assert_no_staging()

    def test_preflight_rejects_later_invalid_destination_without_writes(self):
        self.root.mkdir(parents=True)
        occupied = self.root / self.names[1]
        occupied.write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.plan(self.names[:2])
        self.assertFalse((self.root / self.names[0]).exists())
        self.assertEqual(occupied.read_text(encoding="utf-8"), "keep")

    def test_destination_appearing_during_staging_is_not_overwritten(self):
        copies = self.plan()
        destination = self.root / self.names[0]
        real_copytree = common.shutil.copytree

        def copy_and_create(source, target, *args, **kwargs):
            result = real_copytree(source, target, *args, **kwargs)
            if Path(source) == copies[0].source:
                destination.mkdir()
                (destination / "owner.txt").write_text("keep", encoding="utf-8")
            return result

        with mock.patch.object(common.shutil, "copytree", side_effect=copy_and_create):
            with self.assertRaisesRegex(common.SkillCopyError, "appeared after preflight"):
                common.copy_skills(copies)
        self.assertEqual((destination / "owner.txt").read_text(encoding="utf-8"), "keep")
        self.assert_no_staging()

    def test_invalid_backup_root_refused_before_update(self):
        destination = self.existing(self.names[0])
        backup_root = self.root.parent / "getonmylevel-backups"
        backup_root.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Backup path exists"):
            self.plan()
        self.assertEqual((destination / "local.txt").read_text(encoding="utf-8"), "local edits")
        self.assertEqual(backup_root.read_text(encoding="utf-8"), "keep")


class SkillScopeTests(unittest.TestCase):
    def test_scope_and_claude_instruction_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home, repo, config = (base / name for name in ("home", "repo", "claude-config"))
            for path in (home, repo, config):
                path.mkdir()
            with mock.patch.object(Path, "home", return_value=home), mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(config)}, clear=True):
                for client, user, project in (("codex", home / ".agents" / "skills", repo / ".agents" / "skills"),
                                               ("claude", config / "skills", repo / ".claude" / "skills")):
                    with self.subTest(client=client):
                        self.assertEqual(common.skill_roots("user", None, client), [user])
                        self.assertEqual(common.skill_roots("repo", repo, client), [project])
                        self.assertEqual(common.skill_roots("both", repo, client), [user, project])
                plans = integration.plan_instruction_updates("both", repo, common.SKILL_NAMES[:1], "claude")
                self.assertEqual([p.path for p in plans], [config / "CLAUDE.md", repo / "CLAUDE.md"])
                integration.write_instruction_updates(plans, client="claude")
                self.assertIn(f"{config}/skills/{common.SKILL_NAMES[0]}/SKILL.md", plans[0].path.read_text(encoding="utf-8"))
                self.assertIn(".claude/skills/", plans[1].path.read_text(encoding="utf-8"))
            with mock.patch.object(Path, "home", return_value=home), mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(common.skill_roots("user", None, "claude"), [home / ".claude" / "skills"])
                self.assertEqual(integration.plan_instruction_updates("user", None, common.SKILL_NAMES[:1], "claude")[0].path, home / ".claude" / "CLAUDE.md")

    def test_invalid_and_duplicate_scopes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            with mock.patch.object(Path, "home", return_value=home), mock.patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, "same destination"):
                    common.skill_roots("both", home, "claude")
                with self.assertRaises(ValueError):
                    common.skill_roots("repo", home / "missing")
                with self.assertRaises(ValueError):
                    common.skill_roots("invalid", None)
                with self.assertRaises(ValueError):
                    common.skill_roots("user", None, "unknown")


if __name__ == "__main__":
    unittest.main()

