"""Plan and write managed Codex instructions that activate installed skills by default."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat
import tempfile

import common


BEGIN = "<!-- getonmylevel-skills:begin -->"
END = "<!-- getonmylevel-skills:end -->"

_SKILL_FOLDERS = {"claude": ".claude", "codex": ".agents", "copilot": ".github", "opencode": ".opencode"}
_FILENAMES = {"claude": ("CLAUDE.md",), "copilot": ("copilot-instructions.md",),
              "codex": ("AGENTS.override.md", "AGENTS.md"), "opencode": ("AGENTS.md",)}
_SHARED_REPO_CLIENTS = ("codex", "opencode")
_INTRO = "By default, at the start of each conversation, read the following installed skill instructions and follow them as relevant to the task"
_SHARED_NOTE = "Codex and OpenCode share this block: use only the list for the client you are running in."
_ROLE_SENTENCE = "Claude Code uses the corresponding hyphenated names."


def _user_skill_root(client: str) -> str:
    if client == "claude":
        return os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude"
    if client == "copilot":
        return "~/.copilot"
    return "~/.config/opencode" if client == "opencode" else "~/.agents"


@dataclass(frozen=True)
class InstructionUpdate:
    path: Path
    original: bytes | None
    proposed: bytes
    action: str


class InstructionWriteError(OSError):
    def __init__(self, path: Path, written: list[Path], cause: Exception):
        self.path = path
        self.written = tuple(written)
        super().__init__(f"Could not update instruction file {path}: {cause}")


def _instruction_roots(scope: str, repo_root: Path | None, client: str = "codex") -> list[tuple[str, Path]]:
    if client not in common.CLIENTS:
        raise ValueError(f"Unknown client: {client}")
    roots: list[tuple[str, Path]] = []
    if scope in ("user", "both"):
        config = os.environ.get("CLAUDE_CONFIG_DIR") if client == "claude" else os.environ.get("CODEX_HOME") if client == "codex" else None
        default = {"claude": ".claude", "codex": ".codex", "copilot": ".copilot", "opencode": ".config/opencode"}[client]
        roots.append(("user", Path(config).expanduser() if config else Path.home() / default))
    if scope in ("repo", "both"):
        if repo_root is None:
            raise ValueError("Choose an existing target repository for repository scope.")
        repo_root = Path(repo_root).expanduser()
        repo_info = _stat_optional(repo_root)
        if repo_info is None:
            raise ValueError(f"Target repository is unavailable: {repo_root}")
        if not stat.S_ISDIR(repo_info.st_mode):
            raise ValueError(f"Target repository is not a directory: {repo_root}")
        roots.append(("repo", repo_root / ".github" if client == "copilot" else repo_root))
    if scope not in ("user", "repo", "both"):
        raise ValueError(f"Unknown installation scope: {scope}")
    return roots


def _instruction_path(root: Path, client: str = "codex") -> Path:
    common.check_managed_root(root / "agents")
    expanded_root = root.expanduser()
    for candidate in (expanded_root, *expanded_root.parents):
        if common.is_link_or_reparse(candidate):
            raise ValueError(f"Refusing linked or reparse-point managed instruction root: {candidate}")
    filenames = _FILENAMES[client]
    candidates = [root / name for name in filenames]
    for candidate in candidates:
        if common.is_link_or_reparse(candidate):
            raise ValueError(f"Refusing linked or reparse-point instruction file: {candidate}")
        info = _stat_optional(candidate)
        if info is not None:
            if not stat.S_ISREG(info.st_mode):
                raise ValueError(f"Instruction path is not a regular file: {candidate}")
            if info.st_size:
                return candidate
    return candidates[-1]


def _stat_optional(path: Path):
    """Return stat data, treating only a missing path as absent."""
    try:
        return path.stat()
    except FileNotFoundError:
        return None


def _read_optional(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _current_block(names: list[str], kind: str, newline: str, client: str = "codex") -> str:
    if client not in common.CLIENTS:
        raise ValueError(f"Unknown client: {client}")
    folder = _SKILL_FOLDERS[client]
    if kind == "user":
        user_root = _user_skill_root(client)
        paths = [f"{user_root}/skills/{name}/SKILL.md" for name in names]
        location_note = ""
    else:
        paths = [f"{folder}/skills/{name}/SKILL.md" for name in names]
        location_note = "These paths are relative to the repository root.\n"
    lines = [BEGIN, "## getonmylevel skills", "",
             "By default, at the start of each conversation, read the following installed skill instructions and follow them as relevant to the task:",
             *[f"- `{path}`" for path in paths],
             "", location_note.rstrip("\n") if location_note else None,
             (("For each task, review the available skills and relevant skill locations (including `.agents/skills`, `.codex/skills`, and `.skills` where present). Use skills when they could materially help, and read their instructions before applying them. Honor explicit user preferences and higher-priority instructions." if client == "codex" else f"For each task, review the available skills and relevant skill locations (including `{folder}/skills`, `.skills`, and client-specific locations where present). Use skills when they could materially help, and read their instructions before applying them. Honor explicit user preferences and higher-priority instructions.") if "getonmylevel-skill-discovery" in names else None),
             "Handle straightforward software changes directly without asking for a workflow choice. Use agent-based work when explicitly requested or useful under the active session's delegation rules. Preserve user control over independent review and testing: ask separately when relevant, and keep each disabled unless selected. Wait for actual answers to those choices before dependent work. Respect user preferences and higher-priority session instructions.",
             "Honor explicit user changes to this preference and higher-priority instructions.", END]
    return newline.join(line for line in lines if line is not None)


def _prior_block(names: list[str], kind: str, newline: str, client: str = "codex") -> str:
    old = _legacy_block(names, kind, newline, client)
    lines = old.split(newline)
    return newline.join(line for line in lines if not line.startswith("For each task,")
                        and not line.startswith("Honor explicit user changes"))


def _delegation_block(names: list[str], kind: str, newline: str, client: str = "codex") -> str:
    block = _prior_block(names, kind, newline, client)
    if "getonmylevel-engineering" in names:
        request = ("When the engineering skill applies, I request agent delegation for Agentic mode. "
                   "Follow the skill's mode selection and review and testing choices, and respect "
                   "higher-priority instructions and available tools.")
        block = block.replace(END, request + newline + END)
    return block


def _previous_agentic_block(names: list[str], kind: str, newline: str, client: str = "codex") -> str:
    block = _prior_block(names, kind, newline, client)
    if "getonmylevel-engineering" in names:
        request = ("## Agentic mode" + newline + newline +
                   "To enable Agentic mode for a software task, choose Agentic when prompted or "
                   "request it directly. I request delegation to sub-agents when Agentic mode is "
                   "selected. Follow the engineering skill's mode selection and review and testing "
                   "choices, subject to higher-priority instructions and available tools.")
        block = block.replace(END, request + newline + END)
    return block


def _block(names: list[str], kind: str, newline: str, client: str = "codex") -> str:
    block = _previous_agentic_block(names, kind, newline, client)
    if {"getonmylevel-communication", "getonmylevel-engineering", "getonmylevel-good-software-engineering-practices"}.intersection(names):
        mode_gate = ("For every new request involving any software or code edit, including fixes, tests, configuration, documentation, and skill instructions, always prompt the user to choose Simple or Agentic mode before editing or delegating, regardless of size or any choice made for an earlier request. Read-only investigation may continue while the answer is pending. Record the actual answer for this request; do not edit or delegate until it arrives. Simple means working directly. Agentic mode uses only the installed getonmylevel agent roles configured for the active client: getonmylevel_designer and getonmylevel_implementer, plus getonmylevel_reviewer and getonmylevel_tester only when the user opts into those roles. Claude Code uses the corresponding hyphenated names. Set each spawned agent's type to its installed getonmylevel role. A task-specific spawn name or identifier may be chosen freely; it does not change the required agent type. If a required configured role is unavailable, explain which role is missing and ask the user how to proceed. Ask separately whether the user wants an independent reviewer and an independent tester; each is disabled unless selected. Wait for the actual answer to every choice before assigning roles or doing dependent work. A default, timeout, or elapsed time is not an answer. Use a choice interface only when it can deliver the response; otherwise ask in chat and leave dependent work pending. If Agentic mode is unavailable or disallowed, explain why and ask how to proceed instead of silently switching modes. Respect higher-priority instructions.")
        block = block.replace(END, mode_gate + newline + END)
    if client == "copilot":
        block = block.replace("Claude Code uses the corresponding hyphenated names.",
                              "Claude Code and GitHub Copilot use the corresponding hyphenated names.")
    if client == "opencode":
        block = block.replace(_ROLE_SENTENCE, "Claude Code, GitHub Copilot, and OpenCode use the corresponding hyphenated names.")
    return _add_context_guidance(block, newline)


def _previous_block_with_mode_gate(names: list[str], kind: str, newline: str, client: str = "codex") -> str:
    """Render the immediately previous managed template for migration compatibility."""
    block = _previous_agentic_block(names, kind, newline, client)
    if {"getonmylevel-communication", "getonmylevel-engineering", "getonmylevel-good-software-engineering-practices"}.intersection(names):
        mode_gate = ("For every new request involving any software or code edit, including fixes, tests, configuration, documentation, and skill instructions, always prompt the user to choose Simple or Agentic mode before editing or delegating, regardless of size or any choice made for an earlier request. Read-only investigation may continue while the answer is pending. Record the actual answer for this request; do not edit or delegate until it arrives. Simple means working directly; Agentic means using agents subject to the active session's delegation rules. In Agentic mode, ask separately whether the user wants an independent reviewer and an independent tester; each is disabled unless selected. Wait for the actual answer to every choice before assigning roles or doing dependent work. A default, timeout, or elapsed time is not an answer. Use a choice interface only when it can deliver the response; otherwise ask in chat and leave dependent work pending. If Agentic mode is unavailable or disallowed, explain why and ask how to proceed instead of silently switching modes. Respect higher-priority instructions.")
        block = block.replace(END, mode_gate + newline + END)
    return _add_context_guidance(block, newline)


def _add_context_guidance(block: str, newline: str) -> str:
    guidance = ("## CodeGraph project context" + newline + newline +
                "Whenever a task requires repository context, check whether the repository has a CodeGraph index. "
                "If it does, use the index for relevant code exploration when available, and fall back to other tools if unavailable or insufficient. "
                "If it does not, always inform the user that the project is not indexed and ask whether they want CodeGraph indexing to improve context navigation. "
                "Do not install CodeGraph or initialize an index without the user's authorization. Continue independent work using available search and reads while the choice is pending; respect the user's answer and higher-priority instructions.")
    return block.replace(END, guidance + newline + END)


def _previous_block(names: list[str], kind: str, newline: str, client: str = "codex") -> str:
    if client not in common.CLIENTS:
        raise ValueError(f"Unknown client: {client}")
    folder = _SKILL_FOLDERS[client]
    if kind == "user":
        user_root = _user_skill_root(client)
        paths = [f"{user_root}/skills/{name}/SKILL.md" for name in names]
        location_note = ""
    else:
        paths = [f"{folder}/skills/{name}/SKILL.md" for name in names]
        location_note = "These paths are relative to the repository root.\n"
    lines = [BEGIN, "## getonmylevel skills", "",
             "By default, at the start of each conversation, read the following installed skill instructions and follow them as relevant to the task:",
             *[f"- `{path}`" for path in paths],
             "", location_note.rstrip("\n") if location_note else None,
             (("For each task, review the available skills and relevant skill locations (including `.agents/skills`, `.codex/skills`, and `.skills` where present). Use skills when they could materially help, and read their instructions before applying them. Honor explicit user preferences and higher-priority instructions." if client == "codex" else f"For each task, review the available skills and relevant skill locations (including `{folder}/skills`, `.skills`, and client-specific locations where present). Use skills when they could materially help, and read their instructions before applying them. Honor explicit user preferences and higher-priority instructions.") if "getonmylevel-skill-discovery" in names else None),
             "For every new request involving any software edit, including small fixes, tests, configuration, documentation, or skills, ask the user to choose Simple or Agent-based before editing or delegating unless they explicitly chose a mode for that request. Ask again for each new request. In Agent-based mode, ask separately whether to use an independent reviewer and tester; keep each disabled unless selected. When a multiple-choice popup is available and can deliver the response, use it and wait for the user's actual answer. Never treat a preselected option, timeout, or elapsed time as an answer. If no usable popup exists, ask in chat and leave dependent work pending until the user answers. Respect higher-priority session instructions and explain if they prevent a mode from being used.",
             "Honor explicit user changes to this preference and higher-priority instructions.", END]
    return newline.join(line for line in lines if line is not None)


def _legacy_block(names: list[str], kind: str, newline: str, client: str = "codex") -> str:
    """Render the older legacy template for migration compatibility."""
    folder = _SKILL_FOLDERS[client]
    if kind == "user":
        user_root = _user_skill_root(client)
        paths = [f"{user_root}/skills/{name}/SKILL.md" for name in names]
        location_note = ""
    else:
        paths = [f"{folder}/skills/{name}/SKILL.md" for name in names]
        location_note = "These paths are relative to the repository root.\n"
    lines = [BEGIN, "## getonmylevel skills", "",
             "By default, at the start of each conversation, read the following installed skill instructions and follow them as relevant to the task:",
             *[f"- `{path}`" for path in paths], "", location_note.rstrip("\n") if location_note else None,
             (("For each task, review the available skills and relevant skill locations (including `.agents/skills`, `.codex/skills`, and `.skills` where present). Use skills when they could materially help, and read their instructions before applying them. Honor explicit user preferences and higher-priority instructions." if client == "codex" else f"For each task, review the available skills and relevant skill locations (including `{folder}/skills`, `.skills`, and client-specific locations where present). Use skills when they could materially help, and read their instructions before applying them. Honor explicit user preferences and higher-priority instructions.") if "getonmylevel-skill-discovery" in names else None),
             "Honor explicit user changes to this preference and higher-priority instructions.", END]
    return newline.join(line for line in lines if line is not None)


def _scan_block(text: str, newline: str, prefixes: dict[str, str]) -> tuple[str, dict[str, list[str]]] | None:
    if BEGIN not in text and END not in text:
        return None
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError("Managed skill instruction markers are duplicated or incomplete; repair or remove the getonmylevel block manually.")
    start = text.index(BEGIN)
    finish = text.index(END)
    if finish < start:
        raise ValueError("Managed skill instruction markers are reversed; repair or remove the getonmylevel block manually.")
    end_after = finish + len(END)
    body = text[start:end_after]
    lists: dict[str, list[str]] = {client: [] for client in prefixes}
    suffix = "/SKILL.md`"
    for line in body.split(newline):
        if line.startswith("- `") and line.endswith(suffix):
            path = line[3:-1]
            matches = [client for client, prefix in prefixes.items() if path.startswith(prefix)]
            if not matches:
                raise ValueError("Managed skill instruction block has paths for a different scope; repair or remove it manually.")
            client = matches[0]
            name = path[len(prefixes[client]):-len("/SKILL.md")]
            if name not in common.SKILL_NAMES or name in lists[client]:
                raise ValueError(f"Managed skill instruction block has an unknown or duplicate skill: {name!r}.")
            lists[client].append(name)
    return body, lists


def _candidates(names: list[str], kind: str, newline: str, client: str) -> tuple[str, ...]:
    if client == "opencode":
        return (_block(names, kind, newline, client),)
    return (_block(names, kind, newline, client), _previous_block_with_mode_gate(names, kind, newline, client),
            _add_context_guidance(_previous_agentic_block(names, kind, newline, client), newline),
            _previous_agentic_block(names, kind, newline, client), _delegation_block(names, kind, newline, client),
            _prior_block(names, kind, newline, client), _current_block(names, kind, newline, client),
            _previous_block(names, kind, newline, client), _legacy_block(names, kind, newline, client))


def _parse_block(text: str, kind: str, newline: str, client: str = "codex") -> list[str] | None:
    prefix = f"{_user_skill_root(client)}/skills/" if kind == "user" else f"{_SKILL_FOLDERS[client]}/skills/"
    scanned = _scan_block(text, newline, {client: prefix})
    if scanned is None:
        return None
    body, lists = scanned
    names = lists[client]
    if not names or body not in _candidates(names, kind, newline, client):
        raise ValueError("Managed skill instruction block was edited or is malformed; repair or remove it manually.")
    return names


def _shared_block(codex: list[str], opencode: list[str], newline: str) -> str | None:
    """Render the repository block; Codex and OpenCode lists share one managed block."""
    if not codex and not opencode:
        return None
    if not opencode:
        return _block(codex, "repo", newline, "codex")
    if not codex:
        return _block(opencode, "repo", newline, "opencode")
    union = [name for name in common.SKILL_NAMES if name in codex or name in opencode]
    block = _block(union, "repo", newline, "opencode")
    single = newline.join([_INTRO + ":", *[f"- `.opencode/skills/{name}/SKILL.md`" for name in union]])
    shared = newline.join([_INTRO + ". " + _SHARED_NOTE, "", "Codex:",
                           *[f"- `.agents/skills/{name}/SKILL.md`" for name in codex],
                           "", "OpenCode:",
                           *[f"- `.opencode/skills/{name}/SKILL.md`" for name in opencode]])
    if block.count(single) != 1:
        raise RuntimeError("Shared managed block template mismatch.")
    return block.replace(single, shared)


def _parse_shared_block(text: str, newline: str) -> dict[str, list[str]] | None:
    scanned = _scan_block(text, newline, {"codex": ".agents/skills/", "opencode": ".opencode/skills/"})
    if scanned is None:
        return None
    body, lists = scanned
    codex, opencode = lists["codex"], lists["opencode"]
    if codex and opencode:
        candidates = (_shared_block(codex, opencode, newline),)
    elif codex:
        candidates = _candidates(codex, "repo", newline, "codex")
    elif opencode:
        candidates = (_block(opencode, "repo", newline, "opencode"),)
    else:
        candidates = ()
    if body not in candidates:
        raise ValueError("Managed skill instruction block was edited or is malformed; repair or remove it manually.")
    return {"codex": codex, "opencode": opencode}


def _parse_lists(text: str, kind: str, newline: str, client: str) -> dict[str, list[str]] | None:
    if kind == "repo" and client in _SHARED_REPO_CLIENTS:
        return _parse_shared_block(text, newline)
    names = _parse_block(text, kind, newline, client)
    return None if names is None else {client: names}


def _render_lists(lists: dict[str, list[str]], kind: str, newline: str, client: str) -> str | None:
    if kind == "repo" and client in _SHARED_REPO_CLIENTS:
        return _shared_block(lists.get("codex", []), lists.get("opencode", []), newline)
    names = lists.get(client, [])
    return _block(names, kind, newline, client) if names else None


def _updated_bytes(original: bytes | None, kind: str, selected: list[str], client: str = "codex") -> tuple[bytes, str]:
    bom = b"\xef\xbb\xbf" if original and original.startswith(b"\xef\xbb\xbf") else b""
    raw = original[len(bom):] if original else b""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Instruction file must be valid UTF-8 to preserve it safely.") from exc
    newline = "\r\n" if "\r\n" in text else "\n"
    existing = _parse_lists(text, kind, newline, client)
    own = (existing or {}).get(client, [])
    names = [name for name in common.SKILL_NAMES if name in selected]
    if not names:
        if existing is None or not own:
            return original or b"", "Already current"
        start, finish = text.index(BEGIN), text.index(END) + len(END)
        rendered = _render_lists({**existing, client: []}, kind, newline, client)
        if rendered is not None:
            return bom + (text[:start] + rendered + text[finish:]).encode("utf-8"), "Remove"
        return bom + (text[:start] + text[finish:]).encode("utf-8"), "Remove"
    block = _render_lists({**(existing or {}), client: names}, kind, newline, client)
    if existing is not None:
        start, finish = text.index(BEGIN), text.index(END) + len(END)
        proposed_text = text[:start] + block + text[finish:]
        if proposed_text == text:
            return original or b"", "Already current"
        return bom + proposed_text.encode("utf-8"), "Update"
    if text:
        separator = "" if text.endswith(("\n", "\r")) else newline
        proposed_text = text + separator + block + newline
    else:
        proposed_text = block + newline
    return bom + proposed_text.encode("utf-8"), "Create" if original is None else "Update"


def plan_instruction_updates(scope: str, repo_root: Path | None, names: list[str], client: str = "codex") -> list[InstructionUpdate]:
    selected = common.validate_selection(names, common.SKILL_NAMES, "skill") if names else []
    plans: list[InstructionUpdate] = []
    for kind, root in _instruction_roots(scope, repo_root, client):
        path = _instruction_path(root, client)
        original = _read_optional(path)
        proposed, action = _updated_bytes(original, kind, selected, client)
        plans.append(InstructionUpdate(path, original, proposed, action))
    return plans


def active_skills(scope: str, repo_root: Path | None, client: str = "codex") -> dict[str, list[str]]:
    result = {}
    for kind, root in _instruction_roots(scope, repo_root, client):
        path = _instruction_path(root, client)
        raw = _read_optional(path) or b""
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Instruction file must be valid UTF-8 to preserve it safely.") from exc
        newline = "\r\n" if "\r\n" in text else "\n"
        result[kind] = (_parse_lists(text, kind, newline, client) or {}).get(client, [])
    return result


def _removed_bytes(original: bytes, kind: str, client: str = "codex") -> bytes:
    bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
    try:
        text = original[len(bom):].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Instruction file must be valid UTF-8 to preserve it safely.") from exc
    newline = "\r\n" if "\r\n" in text else "\n"
    lists = _parse_lists(text, kind, newline, client)
    if lists is None or not lists.get(client):
        return original
    start = text.index(BEGIN)
    finish = text.index(END) + len(END)
    rendered = _render_lists({**lists, client: []}, kind, newline, client)
    if rendered is not None:
        return bom + (text[:start] + rendered + text[finish:]).encode("utf-8")
    # Installation appends a newline after the managed block. Remove that one
    # as part of the block while retaining all surrounding user text.
    if text.startswith("\r\n", finish):
        finish += 2
    elif text.startswith("\n", finish):
        finish += 1
    return bom + (text[:start] + text[finish:]).encode("utf-8")


def plan_instruction_removals(scope: str, repo_root: Path | None, client: str = "codex") -> list[InstructionUpdate]:
    """Plan removal of managed blocks from every recognized instruction file."""
    plans: list[InstructionUpdate] = []
    for kind, root in _instruction_roots(scope, repo_root, client):
        # This validates the managed root and both instruction paths for links.
        _instruction_path(root, client)
        filenames = _FILENAMES[client]
        for path in (root / name for name in filenames):
            if common.is_link_or_reparse(path):
                raise ValueError(f"Refusing linked or reparse-point instruction file: {path}")
            info = _stat_optional(path)
            if info is None:
                continue
            if not stat.S_ISREG(info.st_mode):
                raise ValueError(f"Instruction path is not a regular file: {path}")
            original = path.read_bytes()
            proposed = _removed_bytes(original, kind, client)
            if proposed != original:
                plans.append(InstructionUpdate(path, original, proposed, "Remove"))
    return plans


def _write_instruction_plans(plans: list[InstructionUpdate], *, allow_hidden: bool, client: str = "codex") -> list[Path]:
    written: list[Path] = []
    for plan in plans:
        try:
            if allow_hidden:
                _instruction_path(plan.path.parent, client)
                allowed = _FILENAMES[client]
                if plan.path.name not in allowed:
                    raise OSError(f"Not a recognized instruction file: {plan.path}")
            elif _instruction_path(plan.path.parent, client) != plan.path:
                raise OSError(f"The selected instruction file changed since preview: {plan.path}")
            current = plan.path.read_bytes() if plan.path.exists() else None
            if current != plan.original:
                raise OSError(f"Instruction file changed since preview: {plan.path}")
            if plan.proposed == plan.original:
                continue
            plan.path.parent.mkdir(parents=True, exist_ok=True)
            mode = stat.S_IMODE(plan.path.stat().st_mode) if plan.path.exists() else None
            fd, temp_name = tempfile.mkstemp(prefix=f".{plan.path.name}.", suffix=".tmp", dir=plan.path.parent)
            temp_path = Path(temp_name)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(plan.proposed)
                    stream.flush()
                    os.fsync(stream.fileno())
                if mode is not None:
                    os.chmod(temp_path, mode)
                if allow_hidden:
                    _instruction_path(plan.path.parent, client)
                    allowed = _FILENAMES[client]
                    if plan.path.name not in allowed:
                        raise OSError(f"Not a recognized instruction file: {plan.path}")
                elif _instruction_path(plan.path.parent, client) != plan.path:
                    raise OSError(f"The selected instruction file changed since preview: {plan.path}")
                if common.is_link_or_reparse(plan.path):
                    raise ValueError(f"Refusing linked or reparse-point instruction file: {plan.path}")
                if plan.path.exists() and not plan.path.is_file():
                    raise ValueError(f"Instruction path is not a regular file: {plan.path}")
                current = plan.path.read_bytes() if plan.path.exists() else None
                if current != plan.original:
                    raise OSError(f"Instruction file changed since preview: {plan.path}")
                temp_path.replace(plan.path)
                written.append(plan.path)
            finally:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
        except (OSError, ValueError) as exc:
            raise InstructionWriteError(plan.path, written, exc) from exc
    return written


def write_instruction_updates(plans: list[InstructionUpdate], client: str = "codex") -> list[Path]:
    return _write_instruction_plans(plans, allow_hidden=False, client=client)


def write_instruction_removals(plans: list[InstructionUpdate], client: str = "codex") -> list[Path]:
    return _write_instruction_plans(plans, allow_hidden=True, client=client)


def plan_selected_removals(scope: str, repo_root: Path | None, names: list[str], client: str = "codex") -> list[InstructionUpdate]:
    """Remove selected skill references while preserving other managed instructions."""
    selected = set(common.validate_selection(names, common.SKILL_NAMES, "skill"))
    plans = []
    for kind, root in _instruction_roots(scope, repo_root, client):
        _instruction_path(root, client)
        for path in (root / name for name in _FILENAMES[client]):
            info = _stat_optional(path)
            if info is None:
                continue
            if common.is_link_or_reparse(path) or not stat.S_ISREG(info.st_mode):
                raise ValueError(f"Invalid instruction file: {path}")
            original = path.read_bytes()
            bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
            try:
                text = original[len(bom):].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("Instruction file must be valid UTF-8 to preserve it safely.") from exc
            newline = "\r\n" if "\r\n" in text else "\n"
            lists = _parse_lists(text, kind, newline, client)
            existing = (lists or {}).get(client)
            if not existing or not selected.intersection(existing):
                continue
            remaining = [name for name in existing if name not in selected]
            rendered = _render_lists({**lists, client: remaining}, kind, newline, client)
            if rendered is not None:
                start, end = text.index(BEGIN), text.index(END) + len(END)
                proposed = bom + (text[:start] + rendered + text[end:]).encode("utf-8")
            else:
                proposed = _removed_bytes(original, kind, client)
            plans.append(InstructionUpdate(path, original, proposed, "Remove selected"))
    return plans


