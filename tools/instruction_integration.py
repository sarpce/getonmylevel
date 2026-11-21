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
    if client not in ("codex", "claude"):
        raise ValueError(f"Unknown client: {client}")
    roots: list[tuple[str, Path]] = []
    if scope in ("user", "both"):
        config = os.environ.get("CLAUDE_CONFIG_DIR") if client == "claude" else os.environ.get("CODEX_HOME")
        default = ".claude" if client == "claude" else ".codex"
        roots.append(("user", Path(config).expanduser() if config else Path.home() / default))
    if scope in ("repo", "both"):
        if repo_root is None or not repo_root.is_dir():
            raise ValueError("Choose an existing target repository for repository scope.")
        roots.append(("repo", repo_root))
    if scope not in ("user", "repo", "both"):
        raise ValueError(f"Unknown installation scope: {scope}")
    return roots


def _instruction_path(root: Path, client: str = "codex") -> Path:
    common.check_managed_root(root / "agents")
    expanded_root = root.expanduser()
    for candidate in (expanded_root, *expanded_root.parents):
        if common.is_link_or_reparse(candidate):
            raise ValueError(f"Refusing linked or reparse-point managed instruction root: {candidate}")
    filenames = ("CLAUDE.md",) if client == "claude" else ("AGENTS.override.md", "AGENTS.md")
    candidates = [root / name for name in filenames]
    for candidate in candidates:
        if common.is_link_or_reparse(candidate):
            raise ValueError(f"Refusing linked or reparse-point instruction file: {candidate}")
        if candidate.exists():
            if not candidate.is_file():
                raise ValueError(f"Instruction path is not a regular file: {candidate}")
            if candidate.stat().st_size:
                return candidate
    return candidates[-1]


def _block(names: list[str], kind: str, newline: str, client: str = "codex") -> str:
    if client not in ("codex", "claude"):
        raise ValueError(f"Unknown client: {client}")
    folder = ".claude" if client == "claude" else ".agents"
    if kind == "user":
        user_root = os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude" if client == "claude" else "~/.agents"
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
    """Render the exact previous template so existing managed blocks remain recognized."""
    folder = ".claude" if client == "claude" else ".agents"
    if kind == "user":
        user_root = os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude" if client == "claude" else "~/.agents"
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


def _parse_block(text: str, kind: str, newline: str, client: str = "codex") -> list[str] | None:
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
    names: list[str] = []
    folder = ".claude" if client == "claude" else ".agents"
    user_root = os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude" if client == "claude" else "~/.agents"
    prefix = f"{user_root}/skills/" if kind == "user" else f"{folder}/skills/"
    suffix = "/SKILL.md`"
    for line in body.split(newline):
        if line.startswith("- `") and line.endswith(suffix):
            path = line[3:-1]
            if not path.startswith(prefix):
                raise ValueError("Managed skill instruction block has paths for a different scope; repair or remove it manually.")
            name = path[len(prefix):-len("/SKILL.md")]
            if name not in common.SKILL_NAMES or name in names:
                raise ValueError(f"Managed skill instruction block has an unknown or duplicate skill: {name!r}.")
            names.append(name)
    if not names or body not in (_block(names, kind, newline, client), _legacy_block(names, kind, newline, client)):
        raise ValueError("Managed skill instruction block was edited or is malformed; repair or remove it manually.")
    return names


def _updated_bytes(original: bytes | None, kind: str, selected: list[str], client: str = "codex") -> tuple[bytes, str]:
    bom = b"\xef\xbb\xbf" if original and original.startswith(b"\xef\xbb\xbf") else b""
    raw = original[len(bom):] if original else b""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Instruction file must be valid UTF-8 to preserve it safely.") from exc
    newline = "\r\n" if "\r\n" in text else "\n"
    existing = _parse_block(text, kind, newline, client)
    names = [name for name in common.SKILL_NAMES if name in set((existing or []) + selected)]
    block = _block(names, kind, newline, client)
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
    selected = common.validate_selection(names, common.SKILL_NAMES, "skill")
    plans: list[InstructionUpdate] = []
    for kind, root in _instruction_roots(scope, repo_root, client):
        path = _instruction_path(root, client)
        original = path.read_bytes() if path.exists() else None
        proposed, action = _updated_bytes(original, kind, selected, client)
        plans.append(InstructionUpdate(path, original, proposed, action))
    return plans


def _removed_bytes(original: bytes, kind: str, client: str = "codex") -> bytes:
    bom = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
    try:
        text = original[len(bom):].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Instruction file must be valid UTF-8 to preserve it safely.") from exc
    newline = "\r\n" if "\r\n" in text else "\n"
    if _parse_block(text, kind, newline, client) is None:
        return original
    start = text.index(BEGIN)
    finish = text.index(END) + len(END)
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
        filenames = ("CLAUDE.md",) if client == "claude" else ("AGENTS.override.md", "AGENTS.md")
        for path in (root / name for name in filenames):
            if common.is_link_or_reparse(path):
                raise ValueError(f"Refusing linked or reparse-point instruction file: {path}")
            if not path.exists():
                continue
            if not path.is_file():
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
                allowed = ("CLAUDE.md",) if client == "claude" else ("AGENTS.md", "AGENTS.override.md")
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
                    allowed = ("CLAUDE.md",) if client == "claude" else ("AGENTS.md", "AGENTS.override.md")
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
