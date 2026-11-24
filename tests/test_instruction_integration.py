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
import legacy_blocks
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

    def test_copilot_cli_and_vscode_use_shared_skill_and_instruction_locations(self):
        home = self.root / "home"
        home.mkdir()
        repo_github = self.repo / ".github"
        with mock.patch.object(Path, "home", return_value=home):
            self.assertEqual(common.skill_roots("user", None, "copilot"), [home / ".copilot" / "skills"])
            self.assertEqual(common.skill_roots("repo", self.repo, "copilot"), [repo_github / "skills"])
            self.assertEqual(common.agent_roots("global", None, "copilot"), [home / ".copilot" / "agents"])
            self.assertEqual(common.agent_roots("repo", self.repo, "copilot"), [repo_github / "agents"])
            user_plan, = integration.plan_instruction_updates("user", None, SKILLS[:1], "copilot")
            repo_plan, = integration.plan_instruction_updates("repo", self.repo, SKILLS[:1], "copilot")
            self.assertEqual(user_plan.path, home / ".copilot" / "copilot-instructions.md")
            self.assertEqual(repo_plan.path, repo_github / "copilot-instructions.md")
            self.assertIn("~/.copilot/skills/", user_plan.proposed.decode())
            self.assertIn(".github/skills/", repo_plan.proposed.decode())
            (repo_github).mkdir()
            repo_plan.path.write_text("Keep this.\n", encoding="utf-8")
            update, = integration.plan_instruction_updates("repo", self.repo, SKILLS[:1], "copilot")
            integration.write_instruction_updates([update], "copilot")
            self.assertTrue(update.path.read_text(encoding="utf-8").startswith("Keep this.\n"))
            removal, = integration.plan_instruction_removals("repo", self.repo, "copilot")
            integration.write_instruction_removals([removal], "copilot")
            self.assertEqual(update.path.read_text(encoding="utf-8"), "Keep this.\n")

    def test_copilot_agent_profiles_are_managed_markdown_and_refuse_edits(self):
        expected = agents_gui.claude_expected("reviewer", agents_gui.load_templates()["reviewer"])
        self.assertEqual(agents_gui.agent_filename("reviewer", "copilot"), "getonmylevel-reviewer.agent.md")
        rendered = agents_gui.render_copilot_agent(expected, "claude-sonnet-4")
        self.assertIn("model: \"claude-sonnet-4\"", rendered)
        self.assertNotIn("effort:", rendered)
        path = self.root / "reviewer.agent.md"
        path.write_text(rendered, encoding="utf-8")
        self.assertEqual(agents_gui.parse_copilot_managed_file(path, expected), ("claude-sonnet-4", ""))
        first_instruction = expected["developer_instructions"].splitlines()[0]
        path.write_text(rendered.replace(first_instruction, "Changed instruction body"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "edited outside model settings"):
            agents_gui.parse_copilot_managed_file(path, expected)

    def test_block_is_a_short_index_without_workflow_policy(self):
        for client in common.CLIENTS:
            for scope in ("user", "repo"):
                with self.subTest(client=client, scope=scope):
                    block = integration._block(SKILLS, scope, "\n", client)
                    self.assertLess(len(block.split()), 120)
                    for name in SKILLS:
                        self.assertIn(f"{name}/SKILL.md`: ", block)
                    for phrase in ("Simple", "Agentic", "CodeGraph", "start of each conversation", "always", "MUST"):
                        self.assertNotIn(phrase, block)

    def test_exact_selection_preserves_bom_crlf_and_surrounding_text(self):
        verify, ui = "getonmylevel-verify", "getonmylevel-ui-check"
        path = self.codex / "AGENTS.md"
        path.write_bytes(b"\xef\xbb\xbfBefore\r\n" + integration._block([verify, ui], "user", "\r\n").encode() + b"\r\nAfter\r\n")
        plan, = integration.plan_instruction_updates("user", None, [verify])
        integration.write_instruction_updates([plan])
        content = path.read_bytes()
        self.assertTrue(content.startswith(b"\xef\xbb\xbfBefore\r\n"))
        self.assertTrue(content.endswith(b"\r\nAfter\r\n"))
        self.assertIn(verify.encode(), content)
        self.assertNotIn(ui.encode(), content)
        self.assertEqual(integration.plan_instruction_updates("user", None, [verify])[0].action, "Already current")
        plan, = integration.plan_instruction_updates("user", None, [])
        integration.write_instruction_updates([plan])
        self.assertEqual(path.read_bytes(), b"\xef\xbb\xbfBefore\r\n\r\nAfter\r\n")

    def test_legacy_renderers_are_frozen(self):
        # Upgrades recognize old blocks byte-for-byte; editing a legacy string breaks migration.
        import hashlib
        environment = {key: value for key, value in os.environ.items() if key != "CLAUDE_CONFIG_DIR"}
        with mock.patch.dict(os.environ, environment, clear=True):
            digest = hashlib.sha256()
            order = legacy_blocks.LEGACY_ORDER
            for combo in ([order[0]], list(order[1:4]), list(order)):
                for client in ("codex", "claude", "copilot", "opencode"):
                    for kind in ("user", "repo"):
                        for candidate in legacy_blocks.candidates(combo, kind, "\n", client):
                            digest.update(candidate.encode())
            digest.update(legacy_blocks.shared_block(list(order[:2]), list(order[2:]), "\r\n").encode())
        self.assertEqual(digest.hexdigest(), "6d366cee6542a026f25f9709397c9cedb9fbd9e8d442ff3145f6509600e32653")

    def test_every_legacy_block_upgrades_twice_without_losing_user_text(self):
        claude = self.root / "claude"
        claude.mkdir()
        legacy = ["getonmylevel-communication", "getonmylevel-engineering", "getonmylevel-design"]
        expected = ["getonmylevel-verify", "getonmylevel-ui-check"]
        for client in ("codex", "claude", "copilot"):
            for scope in ("user", "repo"):
                for newline in ("\n", "\r\n"):
                    for index, render in enumerate(legacy_blocks.RENDERERS):
                        with self.subTest(client=client, scope=scope, newline=repr(newline), renderer=index), \
                             mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude)}), \
                             mock.patch.object(Path, "home", return_value=self.root / "home"):
                            repo = self.repo if scope == "repo" else None
                            root = integration._instruction_roots(scope, repo, client)[0][1]
                            root.mkdir(parents=True, exist_ok=True)
                            path = root / integration._FILENAMES[client][-1]
                            text = "Before" + newline + render(legacy, scope, newline, client) + newline + "After" + newline
                            path.write_bytes(text.encode())
                            self.assertEqual(integration.active_skills(scope, repo, client)[scope], expected)
                            upgrade, = integration.plan_instruction_upgrades(scope, repo, client)
                            self.assertEqual(upgrade.action, "Upgrade")
                            integration.write_instruction_updates([upgrade], client)
                            updated = path.read_bytes().decode()
                            self.assertTrue(updated.startswith("Before" + newline))
                            self.assertTrue(updated.endswith(newline + "After" + newline))
                            self.assertNotIn("Simple or Agent", updated)
                            self.assertNotIn("CodeGraph", updated)
                            self.assertIn(integration._block(expected, scope, newline, client), updated)
                            if newline == "\r\n":
                                self.assertNotIn("\n", updated.replace("\r\n", ""))
                            self.assertEqual(integration.plan_instruction_upgrades(scope, repo, client), [])
                            self.assertEqual(integration.plan_instruction_updates(scope, repo, expected, client)[0].action, "Already current")
                            path.unlink()

    def test_legacy_block_with_only_retired_skills_is_removed_on_upgrade(self):
        path = self.codex / "AGENTS.md"
        original = "Before\n" + legacy_blocks.gated_block(["getonmylevel-communication"], "user", "\n") + "\nAfter\n"
        path.write_text(original, encoding="utf-8")
        self.assertEqual(integration.active_skills("user", None), {"user": []})
        plan, = integration.plan_instruction_upgrades("user", None)
        self.assertEqual(plan.action, "Remove")
        integration.write_instruction_updates([plan])
        self.assertEqual(path.read_text(encoding="utf-8"), "Before\nAfter\n")
        path.write_text(original, encoding="utf-8")
        removal, = integration.plan_instruction_removals("user", None)
        integration.write_instruction_removals([removal])
        self.assertEqual(path.read_text(encoding="utf-8"), "Before\nAfter\n")

    def test_upgrade_keeps_only_skills_that_will_be_installed(self):
        path = self.codex / "AGENTS.md"
        path.write_text(legacy_blocks.gated_block(["getonmylevel-context", "getonmylevel-design"], "user", "\n") + "\n", encoding="utf-8")
        plan, = integration.plan_instruction_upgrades("user", None, available={"getonmylevel-context"})
        self.assertIn(b"getonmylevel-context/SKILL.md", plan.proposed)
        self.assertNotIn(b"getonmylevel-ui-check", plan.proposed)

    def test_edited_legacy_block_is_refused(self):
        path = self.codex / "AGENTS.md"
        text = legacy_blocks.gated_block(["getonmylevel-engineering"], "user", "\n").replace("Simple means", "Simple MEANS")
        path.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "edited or is malformed"):
            integration.plan_instruction_upgrades("user", None)
        self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_activation_scope_and_missing_files(self):
        import skill_operations
        verify, context = "getonmylevel-verify", "getonmylevel-context"
        with mock.patch.dict(os.environ, {"CODEX_HOME": str(self.codex), "HOME": str(self.root), "USERPROFILE": str(self.root)}), mock.patch.object(common, "skill_roots", side_effect=lambda scope, repo, client: [self.root / scope / "skills"]):
            user = self.root / "user" / "skills"
            (user / context).mkdir(parents=True)
            (user / context / "SKILL.md").write_bytes(b"unchanged")
            copies, plans = skill_operations.plan_activation({"user": [verify], "repo": [context]}, self.repo, "codex")
            self.assertEqual({c.destination.name for c in copies}, {verify, context})
            self.assertEqual(len(plans), 2)
            skill_operations.perform_install(copies, plans)
            self.assertEqual((user / context / "SKILL.md").read_bytes(), b"unchanged")
            self.assertEqual(integration.active_skills("both", self.repo), {"user": [verify], "repo": [context]})
            copies, plans = skill_operations.plan_activation({"user": [verify], "repo": [context]}, self.repo, "codex")
            self.assertEqual(copies, [])
            self.assertTrue(all(p.action == "Already current" for p in plans))

    def test_install_retires_old_skills_and_upgrades_their_block(self):
        import skill_operations
        user = self.root / "user" / "skills"
        old = user / "getonmylevel-engineering"
        old.mkdir(parents=True)
        (old / "SKILL.md").write_text("always ask Simple or Agentic", encoding="utf-8")
        agents = self.codex / "AGENTS.md"
        agents.write_text("Mine\n" + legacy_blocks.gated_block(["getonmylevel-engineering", "getonmylevel-communication"], "user", "\n") + "\n", encoding="utf-8")
        with mock.patch.object(common, "skill_roots", side_effect=lambda scope, repo, client: [self.root / scope / "skills"]):
            _roots, copies, plans = skill_operations.plan_install(["getonmylevel-verify"], "user", None, "codex")
            self.assertEqual([type(p).__name__ for p in plans], ["RetiredSkill", "InstructionUpdate"])
            result, written = skill_operations.perform_install(copies, plans, "codex")
        self.assertFalse(old.exists())
        self.assertEqual(len(result.backups), 1)
        self.assertTrue((Path(result.backups[0]) / "getonmylevel-engineering" / "SKILL.md").is_file())
        self.assertEqual(written, [agents])
        self.assertEqual(agents.read_text(encoding="utf-8"), "Mine\n" + integration._block(["getonmylevel-verify"], "user", "\n") + "\n")
        self.assertTrue((user / "getonmylevel-verify" / "scripts" / "find_checks.py").is_file())

    def test_bundled_skills_are_compact_and_discoverable(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                folder = ROOT / "skills" / name
                text = (folder / "SKILL.md").read_text(encoding="utf-8")
                front, body = text.split("---\n", 2)[1:]
                self.assertIn(f"name: {name}\n", front)
                description = front.split("description: ", 1)[1].strip()
                self.assertIn("Use ", description)
                self.assertLess(len(body.split()), 450)
                self.assertNotIn("Simple or Agentic", text)
                self.assertFalse((folder / "agents" / "openai.yaml").exists(), "implicit invocation must stay enabled")
        self.assertEqual(sorted(p.name for p in (ROOT / "skills").iterdir()), sorted(SKILLS))

    def test_claude_agent_preview_runs_planner_validation(self):
        class Preview:
            def __init__(self):
                self.text = ""

            def configure(self, **_kwargs):
                pass

            def delete(self, *_args):
                self.text = ""

            def insert(self, _index, value):
                self.text = value

        gui = agents_gui.AgentConfigurator.__new__(agents_gui.AgentConfigurator)
        gui.client = mock.Mock()
        gui.client.get.return_value = "claude"
        gui.selected_roles = mock.Mock(return_value=["designer"])
        gui.selected_roots = mock.Mock(return_value=[self.root / ".claude/agents"])
        gui.plan = mock.Mock(side_effect=ValueError("Unsupported Claude Code effort 'ultracode'"))
        gui.preview = Preview()
        gui.scope_conflicts = {}
        gui.refresh_preview()
        gui.plan.assert_called_once_with()
        self.assertIn("Unsupported Claude Code effort 'ultracode'", gui.preview.text)

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
            integration._block([SKILLS[0]], "user", "\n").replace("Read a skill", "Always read a skill"),
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

    def test_skill_status_distinguishes_installed_and_default_active_per_scope(self):
        with mock.patch.object(Path, "home", return_value=self.root / "home"):
            user_root = common.skill_roots("user", None, "codex")[0]
            repo_root = common.skill_roots("repo", self.repo, "codex")[0]
            (user_root / SKILLS[0]).mkdir(parents=True)
            (user_root / SKILLS[0] / "SKILL.md").write_text("skill", encoding="utf-8")
            (repo_root / SKILLS[0]).mkdir(parents=True)
            (repo_root / SKILLS[0] / "SKILL.md").write_text("skill", encoding="utf-8")
            integration.write_instruction_updates(integration.plan_instruction_updates("user", None, [SKILLS[0]]))
            result = install_gui.skill_operations.skill_status("both", self.repo, "codex", [SKILLS[0], SKILLS[1]])
        self.assertEqual(result["user"]["skills"][SKILLS[0]]["status"], "Installed and active by default")
        self.assertEqual(result["repo"]["skills"][SKILLS[0]]["status"], "Installed and available on request")
        self.assertEqual(result["user"]["skills"][SKILLS[1]]["status"], "Not installed")
        self.assertEqual(result["repo"]["skills"][SKILLS[1]]["status"], "Not installed")

    def test_skill_status_reports_orphan_activation_and_scope_local_errors(self):
        with mock.patch.object(Path, "home", return_value=self.root / "home"):
            integration.write_instruction_updates(integration.plan_instruction_updates("user", None, [SKILLS[0]]))
            result = install_gui.skill_operations.skill_status("both", self.repo / "missing", "codex", [SKILLS[0]])
        self.assertEqual(result["user"]["skills"][SKILLS[0]]["status"], "Not installed")
        self.assertIn("file is missing", result["user"]["skills"][SKILLS[0]]["warning"])
        self.assertIsNotNone(result["repo"]["error"])

    def test_skill_status_reports_malformed_managed_instructions_without_hiding_other_scope(self):
        (self.codex / "AGENTS.md").write_text(
            f"{integration.BEGIN}\nmanual edit\n{integration.END}", encoding="utf-8")
        with mock.patch.object(Path, "home", return_value=self.root / "home"):
            result = install_gui.skill_operations.skill_status("both", self.repo, "codex", [SKILLS[0]])
        self.assertIn("malformed", result["user"]["error"])
        self.assertIsNone(result["repo"]["error"])
        self.assertEqual(result["repo"]["skills"][SKILLS[0]]["status"], "Not installed")

    def test_skill_status_uses_each_clients_user_skill_root(self):
        home = self.root / "home"
        claude_home = self.root / "claude-config"
        with mock.patch.object(Path, "home", return_value=home), mock.patch.dict(os.environ, {
                "CLAUDE_CONFIG_DIR": str(claude_home), "CODEX_HOME": str(self.codex)}):
            for client in ("codex", "claude", "copilot"):
                with self.subTest(client=client):
                    root = common.skill_roots("user", None, client)[0]
                    skill_dir = root / SKILLS[0]
                    skill_dir.mkdir(parents=True)
                    (skill_dir / "SKILL.md").write_text("skill", encoding="utf-8")
                    plans = integration.plan_instruction_updates("user", None, [SKILLS[0]], client)
                    integration.write_instruction_updates(plans, client)
                    result = install_gui.skill_operations.skill_status("user", None, client, [SKILLS[0]])
                    self.assertEqual(result["user"]["skills"][SKILLS[0]]["status"], "Installed and active by default")

    def test_skill_status_reports_inaccessible_skill_files_instead_of_not_installed(self):
        with mock.patch.object(Path, "home", return_value=self.root / "home"):
            skill_file = common.skill_roots("user", None, "codex")[0] / SKILLS[0] / "SKILL.md"
            skill_file.parent.mkdir(parents=True)
            skill_file.write_text("skill", encoding="utf-8")
            original_stat = Path.stat

            def inaccessible(path, *args, **kwargs):
                if path == skill_file:
                    raise PermissionError("access denied")
                return original_stat(path, *args, **kwargs)

            with mock.patch.object(Path, "stat", inaccessible):
                result = install_gui.skill_operations.skill_status("user", None, "codex", [SKILLS[0]])
        self.assertEqual(result["user"]["skills"], {})
        self.assertIn("access denied", result["user"]["error"])

    def test_inaccessible_codex_override_does_not_look_absent_or_fall_back(self):
        integration.write_instruction_updates(integration.plan_instruction_updates("user", None, [SKILLS[0]]))
        override = self.codex / "AGENTS.override.md"
        original_stat = Path.stat

        def inaccessible(path, *args, **kwargs):
            if path == override:
                raise PermissionError("override access denied")
            return original_stat(path, *args, **kwargs)

        with mock.patch.object(Path, "stat", inaccessible):
            status = install_gui.skill_operations.skill_status("user", None, "codex", [SKILLS[0]])
            with self.assertRaisesRegex(PermissionError, "override access denied"):
                integration.plan_instruction_updates("user", None, [SKILLS[0]])
        self.assertIn("override access denied", status["user"]["error"])

    def test_unavailable_repository_permission_is_not_reported_as_missing(self):
        original_stat = Path.stat

        def inaccessible(path, *args, **kwargs):
            if path == self.repo:
                raise PermissionError("repository access denied")
            return original_stat(path, *args, **kwargs)

        with mock.patch.object(Path, "home", return_value=self.root / "home"), \
             mock.patch.object(Path, "stat", inaccessible):
            status = install_gui.skill_operations.skill_status("both", self.repo, "codex", [SKILLS[0]])
        self.assertIsNone(status["user"]["error"])
        self.assertIn("repository access denied", status["repo"]["error"])

    def test_deactivating_skill_keeps_its_installed_files_available_on_request(self):
        with mock.patch.object(Path, "home", return_value=self.root / "home"):
            root = common.skill_roots("user", None, "codex")[0]
            skill_dir = root / SKILLS[0]
            skill_dir.mkdir(parents=True)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("installed content", encoding="utf-8")
            activation = integration.plan_instruction_updates("user", None, [SKILLS[0]])
            integration.write_instruction_updates(activation)
            deactivation = integration.plan_instruction_updates("user", None, [])
            integration.write_instruction_updates(deactivation)
            result = install_gui.skill_operations.skill_status("user", None, "codex", [SKILLS[0]])
        self.assertEqual(skill_file.read_text(encoding="utf-8"), "installed content")
        self.assertEqual(result["user"]["skills"][SKILLS[0]]["status"], "Installed and available on request")

    def test_gui_shows_separate_both_scope_status_and_refreshes_after_activation(self):
        class Variable:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        class Label:
            def __init__(self):
                self.text = ""

            def configure(self, **kwargs):
                self.text = kwargs["text"]

        installer = install_gui.Installer.__new__(install_gui.Installer)
        installer.repo_path = Variable(str(self.repo))
        installer.scope = Variable("both")
        installer.client = Variable("codex")
        user = {"skills": {SKILLS[0]: {"status": "Installed and active by default", "warning": None}}, "error": None}
        repository = {"skills": {}, "error": "managed instruction file is malformed"}
        label = Label()
        installer.skill_card_status = {SKILLS[0]: label}
        with mock.patch.object(install_gui.skill_operations, "skill_status", return_value={"user": user, "repo": repository}):
            installer.refresh_skill_status()
        self.assertIn("User-wide: Installed and active by default", label.text)
        self.assertIn("Repository: Status unavailable — managed instruction file is malformed", label.text)

        installer.scope = Variable("user")
        installer.repo_path = Variable("")
        installer.activation_plan = mock.Mock(return_value=({"user": [SKILLS[0]]}, [], [
            integration.InstructionUpdate(self.codex / "AGENTS.md", None, b"managed", "Create")]))
        installer.activation_cache = {("codex", "user", ""): {"user": []}}
        installer.activation_key = ("codex", "user", "")
        installer.load_activation = mock.Mock()
        installer.refresh_skill_status = mock.Mock()
        with mock.patch.object(install_gui.messagebox, "askyesno", return_value=True) as confirm, \
             mock.patch.object(install_gui.messagebox, "showinfo") as completed, \
             mock.patch.object(install_gui, "perform_install", return_value=(None, [self.codex / "AGENTS.md"])) as apply:
            installer.apply_activation()
        self.assertIn(f"activate {SKILLS[0]}", confirm.call_args.args[1])
        self.assertIn("Installed skill files remain available on request", confirm.call_args.args[1])
        self.assertIn("Active by default now", completed.call_args.args[1])
        self.assertIn(SKILLS[0], completed.call_args.args[1])
        installer.refresh_skill_status.assert_called_once()
        apply.assert_called_once()

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
        installer.activation_vars = {"user": {SKILLS[0]: Variable(True)}}
        installer.activation_plan = mock.Mock(return_value=({"user": [SKILLS[0]]}, [operation], [instruction]))
        with mock.patch.object(common, "skill_roots", return_value=[self.root / "skills"]), \
             mock.patch.object(common, "preflight_skill_copy", return_value=[operation]), \
             mock.patch.object(integration, "plan_instruction_updates", return_value=[instruction]):
            installer.refresh_preview()
        self.assertIn("Install: destination", installer.preview.value)
        self.assertIn(f"Create managed instructions: {instruction.path}", installer.preview.value)
        self.assertIn("Required installation (available on request): destination", installer.preview.value)
        self.assertIn("does not activate skills by default", installer.preview.value)

        installer.selections = mock.Mock(return_value=([SKILLS[0]], [], [operation], [instruction]))
        with mock.patch.object(install_gui.messagebox, "askyesno", return_value=False) as confirm, \
             mock.patch.object(install_gui, "perform_install") as perform:
            installer.install()
        confirmation = confirm.call_args.args[1]
        self.assertIn(str(instruction.path), confirmation)
        self.assertIn("Instructions (create)", confirmation)
        self.assertIn("does not select them for default use", confirmation)
        perform.assert_not_called()


if __name__ == "__main__":
    unittest.main()

class OpenCodeInstructionTests(unittest.TestCase):
    HEAD = ("<!-- getonmylevel-skills:begin -->\n## getonmylevel skills\n\n"
            "By default, at the start of each conversation, read the following installed skill instructions and follow them as relevant to the task. "
            "Codex and OpenCode share this block: use only the list for the client you are running in.\n\n"
            "Codex:\n- `.agents/skills/getonmylevel-engineering/SKILL.md`\n\n"
            "OpenCode:\n- `.opencode/skills/getonmylevel-communication/SKILL.md`\n\n"
            "These paths are relative to the repository root.\n## Agentic mode\n")
    ROLE = "Claude Code uses the corresponding hyphenated names."
    OPENCODE_ROLE = "Claude Code, GitHub Copilot, and OpenCode use the corresponding hyphenated names."

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.repo = self.base / "repo"
        self.home.mkdir()
        self.repo.mkdir()
        env = mock.patch.dict(os.environ, {"CODEX_HOME": str(self.home / ".codex"),
                                           "CLAUDE_CONFIG_DIR": str(self.home / ".claude")})
        env.start()
        self.addCleanup(env.stop)
        home = mock.patch.object(Path, "home", return_value=self.home)
        home.start()
        self.addCleanup(home.stop)
        self.agents = self.repo / "AGENTS.md"
        self.codex_names = [common.SKILL_NAMES[0], common.SKILL_NAMES[2]]  # communication, engineering
        self.opencode_names = [common.SKILL_NAMES[1]]  # context

    def write(self, text: str, path: Path | None = None) -> None:
        (path or self.agents).write_bytes(text.encode("utf-8"))

    def read(self, path: Path | None = None) -> str:
        return (path or self.agents).read_bytes().decode("utf-8")

    def activate(self, scope: str, names: list[str], client: str):
        plans = integration.plan_instruction_updates(scope, self.repo, names, client)
        integration.write_instruction_updates(plans, client)
        return plans

    def test_opencode_repo_and_user_blocks_use_opencode_paths(self):
        names = self.opencode_names
        repo_plan = integration.plan_instruction_updates("repo", self.repo, names, "opencode")[0]
        expected = (integration._block(names, "repo", "\n", "codex").replace(".agents/skills/", ".opencode/skills/")
                    .replace(self.ROLE, self.OPENCODE_ROLE) + "\n").encode("utf-8")
        self.assertEqual(repo_plan.proposed, expected)
        user_plan = integration.plan_instruction_updates("user", None, names, "opencode")[0]
        self.assertEqual(user_plan.path, self.home / ".config" / "opencode" / "AGENTS.md")
        expected_user = (integration._block(names, "user", "\n", "codex").replace("~/.agents/skills/", "~/.config/opencode/skills/")
                         .replace(self.ROLE, self.OPENCODE_ROLE) + "\n").encode("utf-8")
        self.assertEqual(user_plan.proposed, expected_user)

    def test_codex_only_repo_activation_is_unchanged(self):
        plan = integration.plan_instruction_updates("repo", self.repo, self.codex_names, "codex")[0]
        self.assertEqual(plan.proposed, (integration._block(self.codex_names, "repo", "\n", "codex") + "\n").encode("utf-8"))

    def test_shared_block_lifecycle_and_active_lists(self):
        codex_block = integration._block(self.codex_names, "repo", "\n", "codex")
        self.write("Intro\n" + codex_block + "\n")
        self.activate("repo", self.opencode_names, "opencode")
        shared = integration._shared_block(self.codex_names, self.opencode_names, "\n")
        self.assertEqual(self.read(), "Intro\n" + shared + "\n")
        self.assertEqual(integration.active_skills("repo", self.repo, "codex"), {"repo": self.codex_names})
        self.assertEqual(integration.active_skills("repo", self.repo, "opencode"), {"repo": self.opencode_names})
        # Removing Codex leaves only the OpenCode block; re-adding and removing OpenCode restores the Codex-only block.
        self.activate("repo", [], "codex")
        self.assertEqual(self.read(), "Intro\n" + integration._block(self.opencode_names, "repo", "\n", "opencode") + "\n")
        self.activate("repo", self.codex_names, "codex")
        self.activate("repo", [], "opencode")
        self.assertEqual(self.read(), "Intro\n" + integration._block(self.codex_names, "repo", "\n", "codex") + "\n")
        plans = integration.plan_instruction_removals("repo", self.repo, "codex")
        integration.write_instruction_removals(plans, "codex")
        self.assertEqual(self.read(), "Intro\n")

    def test_remove_selected_keeps_the_other_client_list(self):
        self.write("Intro\n" + integration._shared_block(self.codex_names, self.opencode_names, "\n") + "\n")
        plans = integration.plan_selected_removals("repo", self.repo, self.opencode_names, "opencode")
        integration.write_instruction_removals(plans, "opencode")
        self.assertEqual(self.read(), "Intro\n" + integration._block(self.codex_names, "repo", "\n", "codex") + "\n")
        self.write("Intro\n" + integration._shared_block(self.codex_names, self.opencode_names, "\n") + "\n")
        plans = integration.plan_selected_removals("repo", self.repo, self.codex_names, "codex")
        integration.write_instruction_removals(plans, "codex")
        self.assertEqual(self.read(), "Intro\n" + integration._block(self.opencode_names, "repo", "\n", "opencode") + "\n")

    def test_empty_opencode_selection_removes_only_its_list(self):
        self.write("Intro\n" + integration._shared_block(self.codex_names, self.opencode_names, "\n") + "\n")
        plan = integration.plan_instruction_updates("repo", self.repo, [], "opencode")[0]
        self.assertEqual(plan.action, "Remove")
        integration.write_instruction_updates([plan], "opencode")
        self.assertEqual(self.read(), "Intro\n" + integration._block(self.codex_names, "repo", "\n", "codex") + "\n")

        codex_only = "Intro\n" + integration._block(self.codex_names, "repo", "\n", "codex") + "\n"
        self.write(codex_only)
        plan = integration.plan_instruction_updates("repo", self.repo, [], "opencode")[0]
        self.assertEqual(plan.action, "Already current")
        self.assertEqual(plan.proposed, codex_only.encode("utf-8"))

    def test_legacy_codex_blocks_upgrade_to_shared_block(self):
        legacy = ["getonmylevel-communication", "getonmylevel-engineering"]
        for index, renderer in enumerate(legacy_blocks.RENDERERS):
            with self.subTest(renderer=index):
                self.write("Intro\n" + renderer(legacy, "repo", "\n", "codex") + "\n")
                plan = integration.plan_instruction_updates("repo", self.repo, self.opencode_names, "opencode")[0]
                self.assertEqual(plan.action, "Update")
                integration.write_instruction_updates([plan], "opencode")
                migrated = ["getonmylevel-verify"]
                self.assertEqual(self.read(), "Intro\n" + integration._shared_block(migrated, self.opencode_names, "\n") + "\n")
                self.activate("repo", [], "opencode")
                self.assertEqual(self.read(), "Intro\n" + integration._block(migrated, "repo", "\n", "codex") + "\n")

    def test_legacy_shared_block_migrates_both_lists(self):
        old = legacy_blocks.shared_block(["getonmylevel-engineering"], ["getonmylevel-design", "getonmylevel-context"], "\n")
        self.write("Intro\n" + old + "\n")
        self.assertEqual(integration.active_skills("repo", self.repo, "opencode"), {"repo": ["getonmylevel-ui-check", "getonmylevel-context"]})
        plan, = integration.plan_instruction_upgrades("repo", self.repo, "codex")
        integration.write_instruction_updates([plan], "codex")
        self.assertEqual(self.read(), "Intro\n" + integration._shared_block(
            ["getonmylevel-verify"], ["getonmylevel-ui-check", "getonmylevel-context"], "\n") + "\n")

    def test_edited_shared_blocks_are_refused_and_left_unchanged(self):
        communication, context = common.SKILL_NAMES[0], common.SKILL_NAMES[1]
        shared = integration._shared_block([communication], [context], "\n")
        edits = {
            "label": shared.replace("\nCodex:\n", "\nCodex list:\n"),
            "order": shared.replace("\nCodex:\n", "\n@\n").replace("\nOpenCode:\n", "\nCodex:\n").replace("\n@\n", "\nOpenCode:\n"),
            "trigger": shared.replace(integration.SKILL_TRIGGERS[communication], "whenever you like"),
            "scope": shared.replace("Paths are relative", f"- `.claude/skills/{communication}/SKILL.md`\nPaths are relative"),
        }
        for label, edited in edits.items():
            for client in ("codex", "opencode"):
                with self.subTest(edit=label, client=client):
                    self.assertNotEqual(edited, shared)
                    text = "Intro\n" + edited + "\n"
                    self.write(text)
                    with self.assertRaises(ValueError):
                        integration.plan_instruction_updates("repo", self.repo, [communication], client)
                    self.assertEqual(self.read(), text)

    def test_override_file_is_separate_from_opencode_agents_file(self):
        override = self.repo / "AGENTS.override.md"
        override_text = "Override\n" + integration._block(self.codex_names, "repo", "\n", "codex") + "\n"
        override.write_bytes(override_text.encode("utf-8"))
        opencode_text = "Intro\n" + integration._block(self.opencode_names, "repo", "\n", "opencode") + "\n"
        self.write(opencode_text)
        plan = integration.plan_instruction_updates("repo", self.repo, self.codex_names, "codex")[0]
        self.assertEqual(plan.path, override)
        plan = integration.plan_instruction_updates("repo", self.repo, self.opencode_names, "opencode")[0]
        self.assertEqual(plan.path, self.agents)
        removals = integration.plan_instruction_removals("repo", self.repo, "codex")
        self.assertEqual([item.path for item in removals], [override])
        removals = integration.plan_instruction_removals("repo", self.repo, "opencode")
        self.assertEqual([item.path for item in removals], [self.agents])
        selected = integration.plan_selected_removals("repo", self.repo, self.codex_names, "codex")
        self.assertEqual([item.path for item in selected], [override])
        selected = integration.plan_selected_removals("repo", self.repo, self.opencode_names, "opencode")
        self.assertEqual([item.path for item in selected], [self.agents])

    def test_crlf_and_bom_are_preserved_when_adding_opencode(self):
        codex_block = integration._block(self.codex_names, "repo", "\r\n", "codex")
        self.agents.write_bytes(b"\xef\xbb\xbf" + ("Intro\r\n" + codex_block + "\r\n").encode("utf-8"))
        plan = integration.plan_instruction_updates("repo", self.repo, self.opencode_names, "opencode")[0]
        expected = b"\xef\xbb\xbf" + ("Intro\r\n" + integration._shared_block(self.codex_names, self.opencode_names, "\r\n") + "\r\n").encode("utf-8")
        self.assertEqual(plan.proposed, expected)

    def test_opencode_agent_profiles_render_parse_and_refuse_unsafe_edits(self):
        import agent_operations as agents

        templates = agents.load_templates()
        expected = agents.claude_expected("reviewer", templates["reviewer"])
        self.assertEqual(agents.agent_filename("reviewer", "opencode"), "getonmylevel-reviewer.md")
        model = "anthropic/claude-sonnet-4-5#high"
        text = agents.render_opencode_agent(expected, model)
        self.assertIn('\nmode: "subagent"\n', text)
        self.assertIn(f'model: "{model}"', text)
        self.assertNotIn("\nname:", text)
        self.assertIn("\n---\n" + agents.OPENCODE_MARKER + "\n", text)
        path = self.repo / "reviewer.md"
        path.write_text(text, encoding="utf-8")
        self.assertEqual(agents.parse_opencode_managed_file(path, expected), (model, ""))
        path.write_text(agents.render_opencode_agent(expected, ""), encoding="utf-8")
        self.assertEqual(agents.parse_opencode_managed_file(path, expected), ("", ""))
        with self.assertRaises(ValueError):
            agents.render_opencode_agent(expected, model, "high")
        with self.assertRaises(ValueError):
            agents.render_opencode_agent(expected, "no-slash")
        path.write_text(text, encoding="utf-8")
        edits = {
            "body": text + "extra\n",
            "temperature": text.replace("\n---\n", "\ntemperature: 0.1\n---\n", 1),
            "primary": text.replace('mode: "subagent"', 'mode: "primary"'),
        }
        for label, edited in edits.items():
            with self.subTest(edit=label):
                path.write_text(edited, encoding="utf-8")
                with self.assertRaises(ValueError):
                    agents.parse_opencode_managed_file(path, expected)

    def test_opencode_agent_preview_runs_planner_validation(self):
        import agent_operations as agents

        class Value:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        gui = agents_gui.AgentConfigurator.__new__(agents_gui.AgentConfigurator)
        gui.client = Value("opencode")
        gui.scope = Value("repo")
        gui.repo_path = Value(str(self.repo))
        gui.selected_roles = lambda: ["reviewer"]
        gui.templates = agents.load_templates()
        gui.model_vars = {"reviewer": Value("provider/model-x#high")}
        gui.effort_vars = {"reviewer": Value("")}
        gui.dirty_fields = {"opencode": {("reviewer", "model")}}
        _roles, _roots, _templates, entries = gui.plan()
        self.assertEqual(entries[0][1], self.repo / ".opencode" / "agents" / "getonmylevel-reviewer.md")
        self.assertIn('model: "provider/model-x#high"', entries[0][2])
        gui.model_vars["reviewer"] = Value("invalid")
        with self.assertRaises(ValueError):
            gui.plan()
