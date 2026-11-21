from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import common
import instruction_integration as integration
import install_gui
import agents_gui


SKILLS = list(common.SKILL_NAMES)


class InstructionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.codex = self.root / "codex"
        self.repo = self.root / "repo"
        self.codex.mkdir()
        self.repo.mkdir()
        self.env = mock.patch.dict(os.environ, {"CODEX_HOME": str(self.codex)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_scope_paths_and_override_precedence(self):
        (self.codex / "AGENTS.override.md").write_text("custom", encoding="utf-8")
        (self.repo / "AGENTS.override.md").write_text("", encoding="utf-8")
        user, = integration.plan_instruction_updates("user", None, SKILLS[:1])
        repo, = integration.plan_instruction_updates("repo", self.repo, SKILLS[:1])
        both = integration.plan_instruction_updates("both", self.repo, SKILLS[:1])
        self.assertEqual(user.path, self.codex / "AGENTS.override.md")
        self.assertEqual(repo.path, self.repo / "AGENTS.md")
        self.assertEqual([p.path for p in both], [user.path, repo.path])

    def test_instructions_are_idempotent_and_accumulate_subset(self):
        first = integration.plan_instruction_updates("user", None, SKILLS[:1])
        integration.write_instruction_updates(first)
        second = integration.plan_instruction_updates("user", None, SKILLS[1:2])
        integration.write_instruction_updates(second)
        content = (self.codex / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(SKILLS[0], content)
        self.assertIn(SKILLS[1], content)
        current = integration.plan_instruction_updates("user", None, SKILLS[:1])
        self.assertEqual(current[0].action, "Already current")
        before = current[0].path.read_bytes()
        self.assertEqual(integration.write_instruction_updates(current), [])
        self.assertEqual(current[0].path.read_bytes(), before)

    def test_direct_work_default_is_generated_for_both_clients_and_scopes(self):
        required = ("straightforward software changes directly", "agent-based work",
                    "independent review and testing", "each disabled unless selected", "higher-priority")
        for client in ("codex", "claude"):
            for scope in ("user", "repo"):
                with self.subTest(client=client, scope=scope):
                    block = integration._block(SKILLS[:1], scope, "\n", client)
                    for phrase in required:
                        self.assertIn(phrase, block)

    def test_previous_managed_blocks_upgrade_and_remain_removable_for_clients_and_scopes(self):
        claude = self.root / "claude"
        claude.mkdir()
        for client in ("codex", "claude"):
            for scope in ("user", "repo"):
                with self.subTest(client=client, scope=scope):
                    env_name = "CLAUDE_CONFIG_DIR" if client == "claude" else "CODEX_HOME"
                    user_root = claude if client == "claude" else self.codex
                    root = user_root if scope == "user" else self.repo
                    filename = "CLAUDE.md" if client == "claude" else "AGENTS.md"
                    path = root / filename
                    with mock.patch.dict(os.environ, {env_name: str(user_root)}):
                        path.write_text("Before\n" + integration._previous_block(SKILLS[:1], scope, "\n", client) + "\nAfter\n", encoding="utf-8")
                        plan, = integration.plan_instruction_updates(scope, self.repo if scope == "repo" else None, SKILLS[:1], client)
                        self.assertEqual(plan.action, "Update")
                        integration.write_instruction_updates([plan], client)
                        updated = path.read_text(encoding="utf-8")
                        self.assertIn("straightforward software changes directly", updated)
                        self.assertTrue(updated.startswith("Before\n"))
                        self.assertTrue(updated.endswith("\nAfter\n"))
                        self.assertEqual(integration.plan_instruction_updates(scope, self.repo if scope == "repo" else None, SKILLS[:1], client)[0].action, "Already current")
                        removal, = integration.plan_instruction_removals(scope, self.repo if scope == "repo" else None, client)
                        integration.write_instruction_removals([removal], client)
                        self.assertEqual(path.read_text(encoding="utf-8"), "Before\nAfter\n")

    def test_older_legacy_managed_block_upgrades(self):
        path = self.codex / "AGENTS.md"
        path.write_text(integration._legacy_block(SKILLS[:1], "user", "\n"), encoding="utf-8")
        plan, = integration.plan_instruction_updates("user", None, SKILLS[:1])
        self.assertEqual(plan.action, "Update")
        integration.write_instruction_updates([plan])
        self.assertIn("straightforward software changes directly", path.read_text(encoding="utf-8"))

    def test_legacy_claude_block_upgrades(self):
        claude = self.root / "claude"
        claude.mkdir()
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude)}):
            path = claude / "CLAUDE.md"
            path.write_text(integration._previous_block(SKILLS[:1], "user", "\n", "claude"), encoding="utf-8")
            plan, = integration.plan_instruction_updates("user", None, SKILLS[:1], "claude")
            self.assertEqual(plan.action, "Update")
            integration.write_instruction_updates([plan], "claude")
            self.assertIn("straightforward software changes directly", path.read_text(encoding="utf-8"))

    def test_clipboard_selector_uses_direct_default_and_keeps_review_choices(self):
        class Clipboard:
            def __init__(self):
                self.value = ""

            def clipboard_clear(self):
                pass

            def clipboard_append(self, value):
                self.value = value

        gui = agents_gui.AgentConfigurator.__new__(agents_gui.AgentConfigurator)
        gui.preference = mock.Mock()
        gui.preference.get.return_value = "Ask"
        gui.root = Clipboard()
        with mock.patch.object(agents_gui.messagebox, "showinfo"):
            gui.copy_selector()
        copied = gui.root.value.casefold()
        for phrase in ("without an up-front workflow choice", "agent-based work", "independent review and testing",
                       "For the skill-selection choice, use a choice interface",
                       "each disabled unless selected",
                       "wait for the selection before dependent work"):
            self.assertIn(phrase.casefold(), copied)
        self.assertNotIn("choose simple or agent-based", copied)

    def test_discovery_skill_adds_instruction_to_existing_block(self):
        path = self.codex / "AGENTS.md"
        original = integration._block(SKILLS[:1], "user", "\n")
        path.write_text("Before\n" + original + "\nAfter\n", encoding="utf-8")
        plan, = integration.plan_instruction_updates("user", None, ["getonmylevel-skill-discovery"])
        integration.write_instruction_updates([plan])
        content = path.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("Before\n"))
        self.assertTrue(content.endswith("\nAfter\n"))
        self.assertIn("review the available skills", content)
        self.assertIn(".agents/skills", content)
        self.assertIn(".skills", content)
        self.assertEqual(integration.plan_instruction_updates("user", None, SKILLS[:1])[0].action, "Already current")
        removal, = integration.plan_instruction_removals("user", None)
        integration.write_instruction_removals([removal])
        self.assertEqual(path.read_text(encoding="utf-8"), "Before\nAfter\n")

    def test_preserves_bom_crlf_and_text_around_block(self):
        path = self.codex / "AGENTS.md"
        original = b"\xef\xbb\xbf# Intro\r\nKeep me\r\n"
        path.write_bytes(original)
        plan, = integration.plan_instruction_updates("user", None, SKILLS[:1])
        integration.write_instruction_updates([plan])
        updated = path.read_bytes()
        self.assertTrue(updated.startswith(b"\xef\xbb\xbf# Intro\r\nKeep me\r\n"))
        self.assertIn(b"\r\n<!-- getonmylevel-skills:begin -->\r\n", updated)
        trailing = path.read_bytes() + b"\r\nTrailing\r\n"
        path.write_bytes(trailing)
        plan, = integration.plan_instruction_updates("user", None, SKILLS[:1])
        self.assertEqual(plan.proposed, trailing)

    def test_invalid_managed_blocks_are_rejected(self):
        path = self.codex / "AGENTS.md"
        invalid_blocks = [
            "<!-- getonmylevel-skills:begin -->\n<!-- getonmylevel-skills:begin -->\n<!-- getonmylevel-skills:end -->",
            "<!-- getonmylevel-skills:begin -->",
            "<!-- getonmylevel-skills:end -->\n<!-- getonmylevel-skills:begin -->",
            "<!-- getonmylevel-skills:begin -->\nmanual edit\n<!-- getonmylevel-skills:end -->",
            "<!-- getonmylevel-skills:begin -->\n## getonmylevel skills\n\nBy default, at the start of each conversation, read the following installed skill instructions and follow them as relevant to the task:\n- `~/.agents/skills/unknown/SKILL.md`\n\nHonor explicit user changes to this preference and higher-priority instructions.\n<!-- getonmylevel-skills:end -->",
        ]
        for text in invalid_blocks:
            path.write_text(text, encoding="utf-8")
            before = path.read_bytes()
            with self.subTest(text=text), self.assertRaises(ValueError):
                integration.plan_instruction_updates("user", None, SKILLS[:1])
            self.assertEqual(path.read_bytes(), before)

    def test_change_after_plan_is_refused(self):
        plan, = integration.plan_instruction_updates("user", None, SKILLS[:1])
        plan.path.write_text("changed", encoding="utf-8")
        with self.assertRaises(integration.InstructionWriteError):
            integration.write_instruction_updates([plan])
        self.assertEqual(plan.path.read_text(encoding="utf-8"), "changed")

    def test_linked_instruction_file_is_refused_when_supported(self):
        target = self.root / "target.md"
        target.write_text("target", encoding="utf-8")
        link = self.codex / "AGENTS.md"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is unavailable")
        with self.assertRaises(ValueError):
            integration.plan_instruction_updates("user", None, SKILLS[:1])

    def test_managed_root_link_is_rechecked_before_creating_temp(self):
        plan, = integration.plan_instruction_updates("user", None, SKILLS[:1])
        with mock.patch.object(common, "is_link_or_reparse", side_effect=lambda path: Path(path) == plan.path.parent), \
             mock.patch.object(integration.tempfile, "mkstemp") as make_temp:
            with self.assertRaises(integration.InstructionWriteError):
                integration.write_instruction_updates([plan])
            make_temp.assert_not_called()
        self.assertFalse(plan.path.exists())

    def test_managed_root_symlink_substitution_is_rejected_when_supported(self):
        alternate = self.root / "alternate"
        alternate.mkdir()
        plan, = integration.plan_instruction_updates("user", None, SKILLS[:1])
        saved = self.root / "codex_saved"
        self.codex.rename(saved)
        try:
            self.codex.symlink_to(alternate, target_is_directory=True)
        except (OSError, NotImplementedError):
            saved.rename(self.codex)
            self.skipTest("directory symlink creation is unavailable")
        with self.assertRaises(integration.InstructionWriteError):
            integration.write_instruction_updates([plan])
        self.assertFalse((alternate / "AGENTS.md").exists())
        self.assertFalse((saved / "AGENTS.md").exists())

    def test_copy_failure_prevents_instruction_write_and_later_failure_is_reported(self):
        plans = integration.plan_instruction_updates("user", None, SKILLS[:1])
        with mock.patch.object(common, "copy_skills", side_effect=OSError("copy failed")), \
             mock.patch.object(integration, "write_instruction_updates") as writer:
            with self.assertRaisesRegex(OSError, "copy failed"):
                install_gui.perform_install([], plans)
            writer.assert_not_called()

        first = integration.InstructionUpdate(self.codex / "AGENTS.md", None, b"one", "Create")
        second = integration.InstructionUpdate(self.repo / "AGENTS.md", None, b"two", "Create")
        with mock.patch.object(common, "copy_skills", return_value=common.SkillCopyResult(("skill",), (), ())), \
             mock.patch.object(integration, "write_instruction_updates", side_effect=integration.InstructionWriteError(second.path, [first.path], OSError("write failed"))):
            with self.assertRaises(integration.InstructionWriteError) as caught:
                install_gui.perform_install([], [first, second])
        self.assertEqual(caught.exception.written, (first.path,))
        self.assertEqual(caught.exception.path, second.path)

    def test_gui_preview_and_confirmation_show_instruction_actions(self):
        class Variable:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        class Preview:
            def __init__(self):
                self.value = ""

            def configure(self, **_kwargs):
                pass

            def delete(self, *_args):
                self.value = ""

            def insert(self, _where, text):
                self.value = text

        installer = install_gui.Installer.__new__(install_gui.Installer)
        installer.selected = {SKILLS[0]: Variable(True)}
        installer.scope = Variable("user")
        installer.repo_path = Variable("")
        installer.preview = Preview()
        installer.install_busy = False
        operation = common.SkillCopy(Path("source"), Path("destination"), None)
        instruction = integration.InstructionUpdate(self.codex / "AGENTS.md", None, b"block", "Create")
        with mock.patch.object(common, "skill_roots", return_value=[self.root / "skills"]), \
             mock.patch.object(common, "preflight_skill_copy", return_value=[operation]), \
             mock.patch.object(integration, "plan_instruction_updates", return_value=[instruction]):
            installer.refresh_preview()
        self.assertIn("Install: destination", installer.preview.value)
        self.assertIn(f"Create: {instruction.path}", installer.preview.value)
        self.assertIn("existing text is preserved", installer.preview.value)

        installer.selections = mock.Mock(return_value=([SKILLS[0]], [], [operation], [instruction], None))
        with mock.patch.object(install_gui.messagebox, "askyesno", return_value=False) as confirm, \
             mock.patch.object(install_gui, "perform_install") as perform:
            installer.install()
        confirmation = confirm.call_args.args[1]
        self.assertIn(str(instruction.path), confirmation)
        self.assertIn("Instructions (create)", confirmation)
        self.assertIn("Existing instruction text is preserved", confirmation)
        perform.assert_not_called()


if __name__ == "__main__":
    unittest.main()
