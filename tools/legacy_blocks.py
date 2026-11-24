"""Frozen renderers for managed instruction blocks written by earlier releases.

Nothing here is written any more. ``instruction_integration`` uses these
renderers only to recognize an unedited older block byte-for-byte, so an
upgrade can replace it with the current block while preserving user text.
Do not edit the strings: a change would stop old blocks from being recognized.
"""

from __future__ import annotations

import os

BEGIN = "<!-- getonmylevel-skills:begin -->"
END = "<!-- getonmylevel-skills:end -->"

_SKILL_FOLDERS = {"claude": ".claude", "codex": ".agents", "copilot": ".github", "opencode": ".opencode"}
_INTRO = "By default, at the start of each conversation, read the following installed skill instructions and follow them as relevant to the task"
_SHARED_NOTE = "Codex and OpenCode share this block: use only the list for the client you are running in."
_ROLE_SENTENCE = "Claude Code uses the corresponding hyphenated names."
_GATE_SKILLS = {"getonmylevel-communication", "getonmylevel-engineering", "getonmylevel-good-software-engineering-practices"}


def _user_skill_root(client: str) -> str:
    if client == "claude":
        return os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude"
    if client == "copilot":
        return "~/.copilot"
    return "~/.config/opencode" if client == "opencode" else "~/.agents"


def _paths(names: list[str], kind: str, client: str) -> tuple[list[str], str]:
    if kind == "user":
        return [f"{_user_skill_root(client)}/skills/{name}/SKILL.md" for name in names], ""
    folder = _SKILL_FOLDERS[client]
    return [f"{folder}/skills/{name}/SKILL.md" for name in names], "These paths are relative to the repository root.\n"


def _discovery(names: list[str], client: str) -> str | None:
    if "getonmylevel-skill-discovery" not in names:
        return None
    if client == "codex":
        return ("For each task, review the available skills and relevant skill locations (including `.agents/skills`, `.codex/skills`, and `.skills` where present). "
                "Use skills when they could materially help, and read their instructions before applying them. Honor explicit user preferences and higher-priority instructions.")
    folder = _SKILL_FOLDERS[client]
    return (f"For each task, review the available skills and relevant skill locations (including `{folder}/skills`, `.skills`, and client-specific locations where present). "
            "Use skills when they could materially help, and read their instructions before applying them. Honor explicit user preferences and higher-priority instructions.")


def _render(names: list[str], kind: str, newline: str, client: str, policy: str | None) -> str:
    paths, location_note = _paths(names, kind, client)
    lines = [BEGIN, "## getonmylevel skills", "",
             "By default, at the start of each conversation, read the following installed skill instructions and follow them as relevant to the task:",
             *[f"- `{path}`" for path in paths],
             "", location_note.rstrip("\n") if location_note else None,
             _discovery(names, client), policy,
             "Honor explicit user changes to this preference and higher-priority instructions.", END]
    return newline.join(line for line in lines if line is not None)


def current_block(names, kind, newline, client="codex"):
    return _render(names, kind, newline, client,
                   "Handle straightforward software changes directly without asking for a workflow choice. Use agent-based work when explicitly requested or useful under the active session's delegation rules. Preserve user control over independent review and testing: ask separately when relevant, and keep each disabled unless selected. Wait for actual answers to those choices before dependent work. Respect user preferences and higher-priority session instructions.")


def previous_block(names, kind, newline, client="codex"):
    return _render(names, kind, newline, client,
                   "For every new request involving any software edit, including small fixes, tests, configuration, documentation, or skills, ask the user to choose Simple or Agent-based before editing or delegating unless they explicitly chose a mode for that request. Ask again for each new request. In Agent-based mode, ask separately whether to use an independent reviewer and tester; keep each disabled unless selected. When a multiple-choice popup is available and can deliver the response, use it and wait for the user's actual answer. Never treat a preselected option, timeout, or elapsed time as an answer. If no usable popup exists, ask in chat and leave dependent work pending until the user answers. Respect higher-priority session instructions and explain if they prevent a mode from being used.")


def legacy_block(names, kind, newline, client="codex"):
    return _render(names, kind, newline, client, None)


def prior_block(names, kind, newline, client="codex"):
    lines = legacy_block(names, kind, newline, client).split(newline)
    return newline.join(line for line in lines if not line.startswith("For each task,")
                        and not line.startswith("Honor explicit user changes"))


def delegation_block(names, kind, newline, client="codex"):
    block = prior_block(names, kind, newline, client)
    if "getonmylevel-engineering" in names:
        request = ("When the engineering skill applies, I request agent delegation for Agentic mode. "
                   "Follow the skill's mode selection and review and testing choices, and respect "
                   "higher-priority instructions and available tools.")
        block = block.replace(END, request + newline + END)
    return block


def previous_agentic_block(names, kind, newline, client="codex"):
    block = prior_block(names, kind, newline, client)
    if "getonmylevel-engineering" in names:
        request = ("## Agentic mode" + newline + newline +
                   "To enable Agentic mode for a software task, choose Agentic when prompted or "
                   "request it directly. I request delegation to sub-agents when Agentic mode is "
                   "selected. Follow the engineering skill's mode selection and review and testing "
                   "choices, subject to higher-priority instructions and available tools.")
        block = block.replace(END, request + newline + END)
    return block


def add_context_guidance(block, newline):
    guidance = ("## CodeGraph project context" + newline + newline +
                "Whenever a task requires repository context, check whether the repository has a CodeGraph index. "
                "If it does, use the index for relevant code exploration when available, and fall back to other tools if unavailable or insufficient. "
                "If it does not, always inform the user that the project is not indexed and ask whether they want CodeGraph indexing to improve context navigation. "
                "Do not install CodeGraph or initialize an index without the user's authorization. Continue independent work using available search and reads while the choice is pending; respect the user's answer and higher-priority instructions.")
    return block.replace(END, guidance + newline + END)


def gated_block(names, kind, newline, client="codex"):
    """The block written by the release that introduced getonmylevel role names in the gate."""
    block = previous_agentic_block(names, kind, newline, client)
    if _GATE_SKILLS.intersection(names):
        mode_gate = ("For every new request involving any software or code edit, including fixes, tests, configuration, documentation, and skill instructions, always prompt the user to choose Simple or Agentic mode before editing or delegating, regardless of size or any choice made for an earlier request. Read-only investigation may continue while the answer is pending. Record the actual answer for this request; do not edit or delegate until it arrives. Simple means working directly. Agentic mode uses only the installed getonmylevel agent roles configured for the active client: getonmylevel_designer and getonmylevel_implementer, plus getonmylevel_reviewer and getonmylevel_tester only when the user opts into those roles. Claude Code uses the corresponding hyphenated names. Set each spawned agent's type to its installed getonmylevel role. A task-specific spawn name or identifier may be chosen freely; it does not change the required agent type. If a required configured role is unavailable, explain which role is missing and ask the user how to proceed. Ask separately whether the user wants an independent reviewer and an independent tester; each is disabled unless selected. Wait for the actual answer to every choice before assigning roles or doing dependent work. A default, timeout, or elapsed time is not an answer. Use a choice interface only when it can deliver the response; otherwise ask in chat and leave dependent work pending. If Agentic mode is unavailable or disallowed, explain why and ask how to proceed instead of silently switching modes. Respect higher-priority instructions.")
        block = block.replace(END, mode_gate + newline + END)
    if client == "copilot":
        block = block.replace(_ROLE_SENTENCE, "Claude Code and GitHub Copilot use the corresponding hyphenated names.")
    if client == "opencode":
        block = block.replace(_ROLE_SENTENCE, "Claude Code, GitHub Copilot, and OpenCode use the corresponding hyphenated names.")
    return add_context_guidance(block, newline)


def previous_block_with_mode_gate(names, kind, newline, client="codex"):
    block = previous_agentic_block(names, kind, newline, client)
    if _GATE_SKILLS.intersection(names):
        mode_gate = ("For every new request involving any software or code edit, including fixes, tests, configuration, documentation, and skill instructions, always prompt the user to choose Simple or Agentic mode before editing or delegating, regardless of size or any choice made for an earlier request. Read-only investigation may continue while the answer is pending. Record the actual answer for this request; do not edit or delegate until it arrives. Simple means working directly; Agentic means using agents subject to the active session's delegation rules. In Agentic mode, ask separately whether the user wants an independent reviewer and an independent tester; each is disabled unless selected. Wait for the actual answer to every choice before assigning roles or doing dependent work. A default, timeout, or elapsed time is not an answer. Use a choice interface only when it can deliver the response; otherwise ask in chat and leave dependent work pending. If Agentic mode is unavailable or disallowed, explain why and ask how to proceed instead of silently switching modes. Respect higher-priority instructions.")
        block = block.replace(END, mode_gate + newline + END)
    return add_context_guidance(block, newline)


RENDERERS = (gated_block, previous_block_with_mode_gate,
             lambda n, k, nl, c="codex": add_context_guidance(previous_agentic_block(n, k, nl, c), nl),
             previous_agentic_block, delegation_block, prior_block, current_block, previous_block, legacy_block)


def candidates(names: list[str], kind: str, newline: str, client: str) -> tuple[str, ...]:
    """Every unedited single-client block an earlier release could have written."""
    if client == "opencode":
        return (gated_block(names, kind, newline, client),)
    return tuple(render(names, kind, newline, client) for render in RENDERERS)


def shared_block(codex: list[str], opencode: list[str], newline: str) -> str:
    """The earlier shared Codex/OpenCode repository block."""
    union = [name for name in LEGACY_ORDER if name in codex or name in opencode]
    block = gated_block(union, "repo", newline, "opencode")
    single = newline.join([_INTRO + ":", *[f"- `.opencode/skills/{name}/SKILL.md`" for name in union]])
    shared = newline.join([_INTRO + ". " + _SHARED_NOTE, "", "Codex:",
                           *[f"- `.agents/skills/{name}/SKILL.md`" for name in codex],
                           "", "OpenCode:",
                           *[f"- `.opencode/skills/{name}/SKILL.md`" for name in opencode]])
    return block.replace(single, shared)


LEGACY_ORDER = (
    "getonmylevel-communication",
    "getonmylevel-context",
    "getonmylevel-engineering",
    "getonmylevel-design",
    "getonmylevel-good-software-engineering-practices",
    "getonmylevel-skill-discovery",
    "getonmylevel-simplicity",
)
