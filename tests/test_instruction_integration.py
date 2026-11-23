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

    def test_exact_selection_and_no_embedded_policy(self):
        design, engineering = "getonmylevel-design", "getonmylevel-engineering"
        for client in ("codex", "claude"):
            for scope in ("user", "repo"):
                block = integration._block([design], scope, "\n", client)
                self.assertIn(design, block)
                for word in ("delegation", "review", "testing", "For each task"):
                    self.assertNotIn(word, block)
        path = self.codex / "AGENTS.md"
        original = b"\xef\xbb\xbfBefore\r\n" + integration._current_block([design, engineering], "user", "\r\n").encode() + b"\r\nAfter\r\n"
        path.write_bytes(original)
        plan, = integration.plan_instruction_updates("user", None, [design])
        integration.write_instruction_updates([plan])
        content = path.read_bytes()
        self.assertTrue(content.startswith(b"\xef\xbb\xbfBefore\r\n"))
        self.assertTrue(content.endswith(b"\r\nAfter\r\n"))
        self.assertIn(design.encode(), content)
        self.assertNotIn(engineering.encode(), content)
        self.assertEqual(integration.plan_instruction_updates("user", None, [design])[0].action, "Already current")
        plan, = integration.plan_instruction_updates("user", None, [])
        integration.write_instruction_updates([plan])
        self.assertEqual(path.read_bytes(), b"\xef\xbb\xbfBefore\r\n\r\nAfter\r\n")

    def test_engineering_activation_requests_delegation_and_upgrades_old_block(self):
        engineering = "getonmylevel-engineering"
        for client in ("codex", "claude"):
            for scope in ("user", "repo"):
                with self.subTest(client=client, scope=scope):
                    old = integration._prior_block([engineering], scope, "\n", client)
                    updated, action = integration._updated_bytes(old.encode(), scope, [engineering], client)
                    self.assertEqual(action, "Update")
                    self.assertIn(b"## Agentic mode", updated)
                    self.assertIn(b"request it directly", updated)
                    self.assertIn(b"I request delegation to sub-agents", updated)
                    previous = integration._delegation_block([engineering], scope, "\n", client).encode()
                    self.assertEqual(integration._updated_bytes(previous, scope, [engineering], client), (updated, "Update"))
                    self.assertEqual(integration._updated_bytes(updated, scope, [engineering], client)[1], "Already current")
                    removed, action = integration._updated_bytes(updated, scope, [], client)
                    self.assertEqual((removed, action), (b"", "Remove"))

    def test_mode_gate_is_added_only_for_relevant_active_skills(self):
        gate_skills = ("getonmylevel-communication", "getonmylevel-engineering",
                       "getonmylevel-good-software-engineering-practices")
        for client in ("codex", "claude"):
            for scope in ("user", "repo"):
                with self.subTest(client=client, scope=scope):
                    for skill in gate_skills:
                        updated, action = integration._updated_bytes(None, scope, [skill], client)
                        self.assertEqual(action, "Create")
                        text = updated.decode()
                        self.assertIn("choose Simple or Agentic mode before editing or delegating", text)
                        self.assertIn("Read-only investigation may continue", text)
                        self.assertIn("Record the actual answer for this request", text)
                        self.assertIn("independent reviewer and an independent tester", text)
                    design, = [name for name in SKILLS if name not in gate_skills][:1]
                    updated, _ = integration._updated_bytes(None, scope, [design], client)
                    self.assertNotIn(b"choose Simple or Agentic mode", updated)

    def test_mode_gate_upgrade_preserves_old_managed_blocks_and_user_text(self):
        for client in ("codex", "claude"):
            with self.subTest(client=client):
                old = integration._previous_block(["getonmylevel-engineering"], "user", "\n", client)
                original = ("Before\n" + old + "\nAfter\n").encode()
                updated, action = integration._updated_bytes(original, "user", ["getonmylevel-engineering"], client)
                self.assertEqual(action, "Update")
                self.assertIn(b"Record the actual answer for this request", updated)
                self.assertTrue(updated.startswith(b"Before\n"))
                self.assertTrue(updated.endswith(b"\nAfter\n"))
                self.assertEqual(integration._updated_bytes(updated, "user", ["getonmylevel-engineering"], client)[1], "Already current")
                removed, action = integration._updated_bytes(updated, "user", [], client)
                self.assertEqual((removed, action), (b"Before\n\nAfter\n", "Remove"))

    def test_activation_scope_and_missing_files(self):
        import skill_operations
        design, engineering = "getonmylevel-design", "getonmylevel-engineering"
        with mock.patch.dict(os.environ, {"CODEX_HOME": str(self.codex), "HOME": str(self.root), "USERPROFILE": str(self.root)}), mock.patch.object(common, "skill_roots", side_effect=lambda scope, repo, client: [self.root / scope / "skills"]):
            user = self.root / "user" / "skills"
            (user / engineering).mkdir(parents=True)
            (user / engineering / "SKILL.md").write_bytes(b"unchanged")
            copies, plans = skill_operations.plan_activation({"user": [design], "repo": [engineering]}, self.repo, "codex")
            self.assertEqual({c.destination.name for c in copies}, {design, engineering})
            self.assertEqual(len(plans), 2)
            skill_operations.perform_install(copies, plans)
            self.assertEqual((user / engineering / "SKILL.md").read_bytes(), b"unchanged")
            self.assertEqual(integration.active_skills("both", self.repo), {"user": [design], "repo": [engineering]})
            copies, plans = skill_operations.plan_activation({"user": [design], "repo": [engineering]}, self.repo, "codex")
            self.assertEqual(copies, [])
            self.assertTrue(all(p.action == "Already current" for p in plans))

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
                        self.assertNotIn("straightforward software changes directly", updated)
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
        self.assertNotIn("straightforward software changes directly", path.read_text(encoding="utf-8"))

    def test_legacy_claude_block_upgrades(self):
        claude = self.root / "claude"
        claude.mkdir()
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude)}):
            path = claude / "CLAUDE.md"
            path.write_text(integration._previous_block(SKILLS[:1], "user", "\n", "claude"), encoding="utf-8")
            plan, = integration.plan_instruction_updates("user", None, SKILLS[:1], "claude")
            self.assertEqual(plan.action, "Update")
            integration.write_instruction_updates([plan], "claude")
            self.assertNotIn("straightforward software changes directly", path.read_text(encoding="utf-8"))

    def test_clipboard_selector_requires_mode_choice_and_keeps_review_choices(self):
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
        for phrase in ("always prompt the user to choose Simple or Agentic mode", "before editing or delegating", "independent reviewer and an independent tester",
                       "Read-only investigation may continue", "Record the actual answer for this request",
                       "each is disabled unless selected",
                       "wait for the actual answer to every choice"):
            self.assertIn(phrase.casefold(), copied)
        self.assertIn("do not silently switch modes", copied)

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

    def test_readme_explains_instruction_level_limit(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8").casefold()
        self.assertIn("cannot intercept client tool calls", readme)
        self.assertIn("cannot guarantee that a choice was presented or recorded", readme)

    def test_discovery_policy_stays_in_skill(self):
        plan, = integration.plan_instruction_updates("user", None, ["getonmylevel-skill-discovery"])
        self.assertNotIn(b"review the available skills", plan.proposed)
        self.assertIn(b"getonmylevel-skill-discovery/SKILL.md", plan.proposed)

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
        self.assertIn("activate getonmylevel-communication", confirm.call_args.args[1])
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

        installer.selections = mock.Mock(return_value=([SKILLS[0]], [], [operation], [instruction], None))
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
