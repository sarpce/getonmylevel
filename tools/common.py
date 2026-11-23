"""Shared validation and path helpers for the standalone Tk tools."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import tempfile
from dataclasses import dataclass
from typing import Iterable


SKILL_NAMES = (
    "getonmylevel-communication",
    "getonmylevel-context",
    "getonmylevel-engineering",
    "getonmylevel-design",
    "getonmylevel-good-software-engineering-practices",
    "getonmylevel-skill-discovery",
    "getonmylevel-simplicity",
)
AGENT_NAMES = ("designer", "implementer", "reviewer", "tester")


@dataclass(frozen=True)
class SkillCopy:
    source: Path
    destination: Path
    expected_identity: tuple[int, int] | None

    @property
    def is_update(self) -> bool:
        return self.expected_identity is not None


@dataclass(frozen=True)
class SkillCopyResult:
    installed: tuple[str, ...]
    updated: tuple[str, ...]
    backups: tuple[str, ...]


class SkillCopyError(OSError):
    """A failed install with details about changes already made."""

    def __init__(self, message: str, installed: list[str], updated: list[str], backups: list[str]):
        self.installed = tuple(installed)
        self.updated = tuple(updated)
        self.backups = tuple(backups)
        details = []
        if installed:
            details.append("installed: " + ", ".join(installed))
        if updated:
            details.append("updated: " + ", ".join(updated))
        if backups:
            details.append("backups: " + ", ".join(backups))
        super().__init__(message + ("\nCompleted changes — " + "; ".join(details) if details else ""))


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
    """Reject linked/reparse points at the selected base and managed path segments."""
    expanded = root.expanduser()
    if expanded.parent.name in (".agents", ".codex", ".claude", ".copilot", ".github"):
        base = expanded.parent.parent
        managed = (expanded.parent, expanded)
    elif expanded.name in ("agents", "skills"):
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


def _identity(path: Path) -> tuple[int, int]:
    info = path.lstat()
    return info.st_dev, info.st_ino


def _validate_backup_root(path: Path) -> None:
    if is_link_or_reparse(path):
        raise ValueError(f"Refusing linked or reparse-point backup directory: {path}")
    if path.exists() and not path.is_dir():
        raise ValueError(f"Backup path exists but is not a directory: {path}")


def preflight_skill_copy(source_root: Path, names: Iterable[str], roots: Iterable[Path]) -> list[SkillCopy]:
    """Validate all selected sources and destinations before creating anything."""
    selected = validate_selection(names, SKILL_NAMES, "skill")
    resolved_roots = validate_roots(roots)
    sources: dict[str, Path] = {}
    for name in selected:
        source = source_root / name
        if not (source / "SKILL.md").is_file():
            raise FileNotFoundError(f"Skill source is missing SKILL.md: {source}")
        sources[name] = source

    copies: list[SkillCopy] = []
    backup_roots: set[Path] = set()
    for root in resolved_roots:
        check_managed_root(root)
        for name in selected:
            destination = root / name
            source = canonical(sources[name])
            target = canonical(destination)
            if source == target or source in target.parents or target in source.parents:
                raise ValueError(f"Source and destination overlap: {source} and {target}")
            if is_link_or_reparse(destination):
                raise FileExistsError(f"Refusing linked or reparse-point destination: {destination}")
            if destination.exists():
                if not destination.is_dir():
                    raise FileExistsError(f"Refusing non-directory destination: {destination}")
                expected = _identity(destination)
                backup_root = root.parent / "getonmylevel-backups"
                _validate_backup_root(backup_root)
                backup_roots.add(backup_root)
            else:
                expected = None
            copies.append(SkillCopy(source, destination, expected))
    for backup_root in backup_roots:
        _validate_backup_root(backup_root)
    return copies


def copy_skills(copies: Iterable[SkillCopy]) -> SkillCopyResult:
    """Install preflighted skills, backing up each replaced directory first."""
    installed: list[str] = []
    updated: list[str] = []
    backups: list[str] = []
    for operation in copies:
        source, destination = operation.source, operation.destination
        staging: Path | None = None
        backup: Path | None = None
        try:
            check_managed_root(destination.parent)
            if is_link_or_reparse(destination):
                raise FileExistsError(f"Refusing linked or reparse-point destination: {destination}")
            exists = destination.exists()
            if operation.expected_identity is None:
                if exists:
                    raise FileExistsError(f"Destination appeared after preflight: {destination}")
            else:
                if not exists or not destination.is_dir() or _identity(destination) != operation.expected_identity:
                    raise FileExistsError(f"Destination changed after preflight: {destination}")

            destination.parent.mkdir(parents=True, exist_ok=True)
            staging_parent = Path(tempfile.mkdtemp(prefix=".getonmylevel-stage-", dir=destination.parent))
            staging = staging_parent / "skill"
            shutil.copytree(source, staging, symlinks=True)

            # Recheck immediately before moving anything to catch changes during staging.
            check_managed_root(destination.parent)
            if is_link_or_reparse(destination):
                raise FileExistsError(f"Refusing linked or reparse-point destination: {destination}")
            exists = destination.exists()
            if operation.expected_identity is None:
                if exists:
                    raise FileExistsError(f"Destination appeared after preflight: {destination}")
            elif not exists or not destination.is_dir() or _identity(destination) != operation.expected_identity:
                raise FileExistsError(f"Destination changed after preflight: {destination}")

            if operation.is_update:
                backup_root = destination.parent.parent / "getonmylevel-backups"
                _validate_backup_root(backup_root)
                backup_root.mkdir(parents=True, exist_ok=True)
                backup = Path(tempfile.mkdtemp(prefix=f"{destination.name}-", dir=backup_root))
                saved_skill = backup / destination.name
                try:
                    destination.rename(saved_skill)
                except OSError as move_error:
                    try:
                        backup.rmdir()
                    except OSError as cleanup_error:
                        raise OSError(
                            f"Could not move destination into backup ({move_error}); unused backup directory remains at {backup} and could not be removed ({cleanup_error})"
                        ) from move_error
                    raise
                backups.append(str(backup))
                try:
                    staging.rename(destination)
                except OSError:
                    try:
                        saved_skill.rename(destination)
                        backups.remove(str(backup))
                        try:
                            backup.rmdir()
                        except OSError:
                            backups.append(str(backup))
                    except OSError as restore_error:
                        raise OSError(f"Could not install update or restore original. Original remains at backup: {backup}. Restoration error: {restore_error}")
                    raise
                updated.append(str(destination))
            else:
                staging.rename(destination)
                installed.append(str(destination))
        except (OSError, ValueError) as exc:
            raise SkillCopyError(str(exc), installed, updated, backups) from exc
        finally:
            if staging is not None:
                staging_parent = staging.parent
                if staging_parent.exists():
                    shutil.rmtree(staging_parent, ignore_errors=True)
    return SkillCopyResult(tuple(installed), tuple(updated), tuple(backups))


def skill_roots(scope: str, repo_root: Path | None, client: str = "codex") -> list[Path]:
    if client not in ("codex", "claude", "copilot"):
        raise ValueError(f"Unknown client: {client}")
    home = {"codex": ".agents", "claude": ".claude", "copilot": ".github"}[client]
    roots: list[Path] = []
    if scope in ("user", "both"):
        user_root = Path.home()
        if client == "claude" and os.environ.get("CLAUDE_CONFIG_DIR"):
            user_root = Path(os.environ["CLAUDE_CONFIG_DIR"]).expanduser()
        if client == "copilot":
            user_root = Path.home() / ".copilot"
            roots.append(user_root / "skills")
        else:
            roots.append(user_root / home / "skills" if client == "codex" or not os.environ.get("CLAUDE_CONFIG_DIR") else user_root / "skills")
    if scope in ("repo", "both"):
        if repo_root is None or not repo_root.is_dir():
            raise ValueError("Choose an existing target repository for repository scope.")
        roots.append(repo_root / (".github" if client == "copilot" else home) / "skills")
    if scope not in ("user", "repo", "both"):
        raise ValueError(f"Unknown installation scope: {scope}")
    return validate_roots(roots)


def agent_roots(scope: str, repo_root: Path | None, client: str = "codex") -> list[Path]:
    if client not in ("codex", "claude", "copilot"):
        raise ValueError(f"Unknown client: {client}")
    roots: list[Path] = []
    if scope in ("global", "both"):
        if client == "claude":
            config_home = os.environ.get("CLAUDE_CONFIG_DIR")
            roots.append((Path(config_home).expanduser() if config_home else Path.home() / ".claude") / "agents")
        elif client == "copilot":
            roots.append(Path.home() / ".copilot" / "agents")
        else:
            codex_home = os.environ.get("CODEX_HOME")
            roots.append((Path(codex_home).expanduser() if codex_home else Path.home() / ".codex") / "agents")
    if scope in ("repo", "both"):
        if repo_root is None or not repo_root.is_dir():
            raise ValueError("Choose an existing target repository for repository scope.")
        roots.append(repo_root / ({"claude": ".claude", "codex": ".codex", "copilot": ".github"}[client]) / "agents")
    if scope not in ("global", "repo", "both"):
        raise ValueError(f"Unknown agent configuration scope: {scope}")
    return validate_roots(roots)
