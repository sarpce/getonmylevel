"""Plan and write the managed instruction block that indexes installed skills."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat
import tempfile

import common
import legacy_blocks


BEGIN = "<!-- getonmylevel-skills:begin -->"
END = "<!-- getonmylevel-skills:end -->"

_SKILL_FOLDERS = {"claude": ".claude", "codex": ".agents", "copilot": ".github", "opencode": ".opencode"}
_FILENAMES = {"claude": ("CLAUDE.md",), "copilot": ("copilot-instructions.md",),
              "codex": ("AGENTS.override.md", "AGENTS.md"), "opencode": ("AGENTS.md",)}
_SHARED_REPO_CLIENTS = ("codex", "opencode")

# The managed block is an index, not a policy: one line per active skill saying
# when to read it. Skill bodies load only when their step comes up, and the
# block stays byte-stable between sessions so prompt caches stay warm.
_INTRO = "These installed skills are procedures for specific steps. Read a skill when you reach its step"
_SHARED_NOTE = "Codex and OpenCode share this block: use the list for the client you are running in."
_REPO_NOTE = "Paths are relative to the repository root."
SKILL_TRIGGERS = {
    "getonmylevel-verify": "before finishing a code change, and when fixing a bug",
    "getonmylevel-ui-check": "after changing an interface that renders in a browser or app window",
    "getonmylevel-context": "when finding callers across packages, or using an API that depends on the installed version",
}
_ENTRY = re.compile(r"- `(?P<path>[^`]+)/SKILL\.md`(?:: .*)?")


def _user_skill_root(client: str) -> str:
    if client == "claude":
        return os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude"
    if client == "copilot":
        return "~/.copilot"
    return "~/.config/opencode" if client == "opencode" else "~/.agents"


def _prefix(kind: str, client: str) -> str:
    return f"{_user_skill_root(client)}/skills/" if kind == "user" else f"{_SKILL_FOLDERS[client]}/skills/"


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


def _entries(prefix: str, names: list[str]) -> list[str]:
    return [f"- `{prefix}{name}/SKILL.md`: {SKILL_TRIGGERS[name]}" for name in names]


def _block(names: list[str], kind: str, newline: str, client: str = "codex") -> str:
    if client not in common.CLIENTS:
        raise ValueError(f"Unknown client: {client}")
    lines = [BEGIN, "## getonmylevel skills", "", _INTRO + ":", *_entries(_prefix(kind, client), names)]
    if kind != "user":
        lines.append(_REPO_NOTE)
    lines.append(END)
    return newline.join(lines)


def _shared_block(codex: list[str], opencode: list[str], newline: str) -> str | None:
    """Render the repository block; Codex and OpenCode lists share one managed block."""
    if not codex and not opencode:
        return None
    if not opencode:
        return _block(codex, "repo", newline, "codex")
    if not codex:
        return _block(opencode, "repo", newline, "opencode")
    return newline.join([BEGIN, "## getonmylevel skills", "", _INTRO + ". " + _SHARED_NOTE, "",
                         "Codex:", *_entries(".agents/skills/", codex), "",
                         "OpenCode:", *_entries(".opencode/skills/", opencode), _REPO_NOTE, END])


def _scan_block(text: str, newline: str, prefixes: dict[str, str]) -> tuple[str, dict[str, list[str]]] | None:
    if BEGIN not in text and END not in text:
        return None
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError("Managed skill instruction markers are duplicated or incomplete; repair or remove the getonmylevel block manually.")
    start = text.index(BEGIN)
    finish = text.index(END)
    if finish < start:
        raise ValueError("Managed skill instruction markers are reversed; repair or remove the getonmylevel block manually.")
    body = text[start:finish + len(END)]
    lists: dict[str, list[str]] = {client: [] for client in prefixes}
    known = set(common.SKILL_NAMES) | set(common.LEGACY_SKILL_NAMES)
    for line in body.split(newline):
        match = _ENTRY.fullmatch(line)
        if not match:
            continue
        path = match.group("path")
        matches = [client for client, prefix in prefixes.items() if path.startswith(prefix)]
        if not matches:
            raise ValueError("Managed skill instruction block has paths for a different scope; repair or remove it manually.")
        client = matches[0]
        name = path[len(prefixes[client]):]
        if name not in known or name in lists[client]:
            raise ValueError(f"Managed skill instruction block has an unknown or duplicate skill: {name!r}.")
        lists[client].append(name)
    return body, lists


_MALFORMED = "Managed skill instruction block was edited or is malformed; repair or remove it manually."


def _is_current(names: list[str]) -> bool:
    return all(name in common.SKILL_NAMES for name in names)


def _is_legacy(names: list[str]) -> bool:
    return all(name in common.LEGACY_SKILL_NAMES for name in names)


def _parse_lists(text: str, kind: str, newline: str, client: str) -> tuple[dict[str, list[str]], bool, dict[str, list[str]]] | None:
    """Return the active lists (legacy names migrated), whether the block is current, and the raw lists.

    An unedited block from an earlier release parses as stale so the next write
    replaces it. Anything else between the markers is refused unchanged.
    """
    shared = kind == "repo" and client in _SHARED_REPO_CLIENTS
    prefixes = {"codex": ".agents/skills/", "opencode": ".opencode/skills/"} if shared else {client: _prefix(kind, client)}
    scanned = _scan_block(text, newline, prefixes)
    if scanned is None:
        return None
    body, lists = scanned
    if shared:
        codex, opencode = lists["codex"], lists["opencode"]
        if (codex or opencode) and _is_current(codex + opencode) and body == _shared_block(codex, opencode, newline):
            return lists, True, lists
        if _is_legacy(codex + opencode):
            if codex and opencode:
                legacy = (legacy_blocks.shared_block(codex, opencode, newline),)
            elif codex:
                legacy = legacy_blocks.candidates(codex, "repo", newline, "codex")
            elif opencode:
                legacy = legacy_blocks.candidates(opencode, "repo", newline, "opencode")
            else:
                legacy = ()
            if body in legacy:
                return {name: common.migrate_skill_names(values) for name, values in lists.items()}, False, lists
        raise ValueError(_MALFORMED)
    names = lists[client]
    if names and _is_current(names) and body == _block(names, kind, newline, client):
        return lists, True, lists
    if names and _is_legacy(names) and body in legacy_blocks.candidates(names, kind, newline, client):
        return {client: common.migrate_skill_names(names)}, False, lists
    raise ValueError(_MALFORMED)


def _render_lists(lists: dict[str, list[str]], kind: str, newline: str, client: str) -> str | None:
    if kind == "repo" and client in _SHARED_REPO_CLIENTS:
        return _shared_block(lists.get("codex", []), lists.get("opencode", []), newline)
    names = lists.get(client, [])
    return _block(names, kind, newline, client) if names else None


def _decode(original: bytes | None) -> tuple[bytes, str, str]:
    bom = b"\xef\xbb\xbf" if original and original.startswith(b"\xef\xbb\xbf") else b""
    raw = original[len(bom):] if original else b""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Instruction file must be valid UTF-8 to preserve it safely.") from exc
    return bom, text, "\r\n" if "\r\n" in text else "\n"


def _replace_block(text: str, rendered: str | None, *, eat_newline: bool) -> str:
    start, finish = text.index(BEGIN), text.index(END) + len(END)
    if rendered is not None:
        return text[:start] + rendered + text[finish:]
    if eat_newline:
        # Installation appends a newline after the managed block. Remove that
        # one as part of the block while retaining all surrounding user text.
        if text.startswith("\r\n", finish):
            finish += 2
        elif text.startswith("\n", finish):
            finish += 1
    return text[:start] + text[finish:]


def _updated_bytes(original: bytes | None, kind: str, selected: list[str], client: str = "codex") -> tuple[bytes, str]:
    bom, text, newline = _decode(original)
    parsed = _parse_lists(text, kind, newline, client)
    names = [name for name in common.SKILL_NAMES if name in selected]
    if parsed is None:
        if not names:
            return original or b"", "Already current"
        if text:
            separator = "" if text.endswith(("\n", "\r")) else newline
            proposed_text = text + separator + _block(names, kind, newline, client) + newline
        else:
            proposed_text = _block(names, kind, newline, client) + newline
        return bom + proposed_text.encode("utf-8"), "Create" if original is None else "Update"
    existing = parsed[0]
    rendered = _render_lists({**existing, client: names}, kind, newline, client)
    proposed_text = _replace_block(text, rendered, eat_newline=False)
    if proposed_text == text:
        return original or b"", "Already current"
    return bom + proposed_text.encode("utf-8"), "Remove" if not names else "Update"


def plan_instruction_updates(scope: str, repo_root: Path | None, names: list[str], client: str = "codex") -> list[InstructionUpdate]:
    selected = common.validate_selection(names, common.SKILL_NAMES, "skill") if names else []
    plans: list[InstructionUpdate] = []
    for kind, root in _instruction_roots(scope, repo_root, client):
        path = _instruction_path(root, client)
        original = _read_optional(path)
        proposed, action = _updated_bytes(original, kind, selected, client)
        plans.append(InstructionUpdate(path, original, proposed, action))
    return plans


def _read_text(path: Path) -> tuple[bytes, bytes, str, str]:
    original = path.read_bytes()
    bom, text, newline = _decode(original)
    return original, bom, text, newline


def active_skills(scope: str, repo_root: Path | None, client: str = "codex") -> dict[str, list[str]]:
    result = {}
    for kind, root in _instruction_roots(scope, repo_root, client):
        path = _instruction_path(root, client)
        _bom, text, newline = _decode(_read_optional(path))
        parsed = _parse_lists(text, kind, newline, client)
        result[kind] = parsed[0].get(client, []) if parsed else []
    return result


def _removed_bytes(original: bytes, kind: str, client: str = "codex") -> bytes:
    bom, text, newline = _decode(original)
    parsed = _parse_lists(text, kind, newline, client)
    if parsed is None or not parsed[2].get(client):
        return original
    rendered = _render_lists({**parsed[0], client: []}, kind, newline, client)
    return bom + _replace_block(text, rendered, eat_newline=True).encode("utf-8")


def _existing_instruction_files(root: Path, client: str):
    # This validates the managed root and every instruction path for links.
    _instruction_path(root, client)
    for path in (root / name for name in _FILENAMES[client]):
        if common.is_link_or_reparse(path):
            raise ValueError(f"Refusing linked or reparse-point instruction file: {path}")
        info = _stat_optional(path)
        if info is None:
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"Instruction path is not a regular file: {path}")
        yield path


def plan_instruction_removals(scope: str, repo_root: Path | None, client: str = "codex") -> list[InstructionUpdate]:
    """Plan removal of managed blocks from every recognized instruction file."""
    plans: list[InstructionUpdate] = []
    for kind, root in _instruction_roots(scope, repo_root, client):
        for path in _existing_instruction_files(root, client):
            original = path.read_bytes()
            proposed = _removed_bytes(original, kind, client)
            if proposed != original:
                plans.append(InstructionUpdate(path, original, proposed, "Remove"))
    return plans


def plan_instruction_upgrades(scope: str, repo_root: Path | None, client: str = "codex",
                              available: set[str] | None = None) -> list[InstructionUpdate]:
    """Rewrite managed blocks left by earlier releases in the current format.

    Legacy skill names are mapped to their replacements. When ``available`` is
    given, this client's list keeps only skills that will be installed, so the
    block never points at a missing file. Current blocks are left untouched.
    """
    plans: list[InstructionUpdate] = []
    for kind, root in _instruction_roots(scope, repo_root, client):
        for path in _existing_instruction_files(root, client):
            original, bom, text, newline = _read_text(path)
            parsed = _parse_lists(text, kind, newline, client)
            if parsed is None or parsed[1]:
                continue
            lists = dict(parsed[0])
            if available is not None:
                lists[client] = [name for name in lists.get(client, []) if name in available]
            rendered = _render_lists(lists, kind, newline, client)
            proposed = bom + _replace_block(text, rendered, eat_newline=True).encode("utf-8")
            plans.append(InstructionUpdate(path, original, proposed, "Upgrade" if rendered else "Remove"))
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
        for path in _existing_instruction_files(root, client):
            original, bom, text, newline = _read_text(path)
            parsed = _parse_lists(text, kind, newline, client)
            if parsed is None:
                continue
            lists, current, _raw = parsed
            existing = lists.get(client, [])
            if current and not selected.intersection(existing):
                continue
            remaining = [name for name in existing if name not in selected]
            rendered = _render_lists({**lists, client: remaining}, kind, newline, client)
            proposed = bom + _replace_block(text, rendered, eat_newline=True).encode("utf-8")
            if proposed != original:
                plans.append(InstructionUpdate(path, original, proposed, "Remove selected"))
    return plans
