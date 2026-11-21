"""Shared validation and path helpers for the standalone Tk tools."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
from typing import Iterable


SKILL_NAMES = (
    "getonmylevel-communication",
    "getonmylevel-context",
    "getonmylevel-engineering",
)
AGENT_NAMES = ("designer", "implementer", "reviewer", "tester")


def canonical(path: Path) -> Path:
    """Resolve existing portions and normalize a destination path."""
    return path.expanduser().resolve(strict=False)


def is_link_or_reparse(path: Path) -> bool:
    """Detect links, Windows junctions, and other reparse points, including dangling links."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    if os.name == "nt":
        flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if getattr(info, "st_file_attributes", 0) & flag:
            return True
        is_junction = getattr(os.path, "isjunction", None)
        if is_junction is not None and is_junction(path):
            return True
    return False


def check_managed_root(root: Path) -> None:
    """Reject linked/reparse points at the selected base and Codex-managed path segments."""
    expanded = root.expanduser()
    if expanded.parent.name in (".agents", ".codex"):
        base = expanded.parent.parent
        managed = (expanded.parent, expanded)
    elif expanded.name == "agents":
        base = expanded.parent
        managed = (expanded,)
    else:
        raise ValueError(f"Unexpected managed destination layout: {root}")
    for path in (base, *managed):
        if is_link_or_reparse(path):
            raise ValueError(f"Refusing linked or reparse-point destination path: {path}")


def validate_selection(names: Iterable[str], allowed: Iterable[str], label: str) -> list[str]:
    selected = list(names)
    allowed_set = set(allowed)
    if not selected:
        raise ValueError(f"Select at least one {label}.")
    seen: set[str] = set()
    for name in selected:
        if name not in allowed_set:
            raise ValueError(f"Unknown {label}: {name}")
        if name in seen:
            raise ValueError(f"Duplicate {label}: {name}")
        seen.add(name)
    return selected


def validate_roots(roots: Iterable[Path]) -> list[Path]:
    originals = list(roots)
    for root in originals:
        check_managed_root(root)
    result = [canonical(root) for root in originals]
    if not result:
        raise ValueError("Select at least one installation scope.")
    if len(set(result)) != len(result):
        raise ValueError("Selected scopes resolve to the same destination directory.")
    for root in result:
        if root.exists() and not root.is_dir():
            raise ValueError(f"Installation root exists but is not a directory: {root}")
    return result


def preflight_skill_copy(source_root: Path, names: Iterable[str], roots: Iterable[Path]) -> list[tuple[Path, Path]]:
    """Validate all selected sources and destinations before creating anything."""
    selected = validate_selection(names, SKILL_NAMES, "skill")
    resolved_roots = validate_roots(roots)
    sources: dict[str, Path] = {}
    for name in selected:
        source = source_root / name
        if not (source / "SKILL.md").is_file():
            raise FileNotFoundError(f"Skill source is missing SKILL.md: {source}")
        sources[name] = source

    copies: list[tuple[Path, Path]] = []
    for root in resolved_roots:
        check_managed_root(root)
        for name in selected:
            destination = root / name
            if is_link_or_reparse(destination) or destination.exists():
                raise FileExistsError(f"Refusing to overwrite existing destination: {destination}")
            copies.append((sources[name], destination))
    return copies


def copy_skills(copies: Iterable[tuple[Path, Path]]) -> list[str]:
    """Perform a preflighted copy and return successfully created paths.

    Filesystem operations are not transactional; an I/O error can leave earlier
    copies in place, which is reported to the caller.
    """
    created: list[str] = []
    for source, destination in copies:
        check_managed_root(destination.parent)
        if is_link_or_reparse(destination) or destination.exists():
            raise FileExistsError(f"Refusing to overwrite newly occupied destination: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, symlinks=True)
        created.append(str(destination))
    return created


def skill_roots(scope: str, repo_root: Path | None) -> list[Path]:
    roots: list[Path] = []
    if scope in ("user", "both"):
        roots.append(Path.home() / ".agents" / "skills")
    if scope in ("repo", "both"):
        if repo_root is None or not repo_root.is_dir():
            raise ValueError("Choose an existing target repository for repository scope.")
        roots.append(repo_root / ".agents" / "skills")
    if scope not in ("user", "repo", "both"):
        raise ValueError(f"Unknown installation scope: {scope}")
    return validate_roots(roots)


def agent_roots(scope: str, repo_root: Path | None) -> list[Path]:
    roots: list[Path] = []
    if scope in ("global", "both"):
        codex_home = os.environ.get("CODEX_HOME")
        roots.append((Path(codex_home).expanduser() if codex_home else Path.home() / ".codex") / "agents")
    if scope in ("repo", "both"):
        if repo_root is None or not repo_root.is_dir():
            raise ValueError("Choose an existing target repository for repository scope.")
        roots.append(repo_root / ".codex" / "agents")
    if scope not in ("global", "repo", "both"):
        raise ValueError(f"Unknown agent configuration scope: {scope}")
    return validate_roots(roots)
