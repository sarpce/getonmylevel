"""Shared, headless operations for bundled skill installation."""
from dataclasses import dataclass
from pathlib import Path
import stat
import tempfile
import common
import instruction_integration as instructions

SOURCE_REPO = Path(__file__).resolve().parent.parent
SOURCE_ROOT = SOURCE_REPO / "skills"


def roots_for(scope, repo, client):
    if scope in ("repo", "both"):
        if repo is None or not str(repo).strip():
            raise ValueError("Choose an existing target repository for repository scope.")
        repo = Path(repo).expanduser()
        try:
            repo_info = repo.stat()
        except FileNotFoundError as exc:
            raise ValueError(f"Target repository is unavailable: {repo}") from exc
        if not stat.S_ISDIR(repo_info.st_mode):
            raise ValueError(f"Target repository is not a directory: {repo}")
        if common.canonical(repo) == SOURCE_REPO:
            raise ValueError("The target repository must differ from this source checkout.")
    else:
        repo = None
    return repo, common.skill_roots(scope, repo, client)


@dataclass(frozen=True)
class RetiredSkill:
    """An installed skill from an earlier release, moved to backups on install or update.

    Retired skill bodies still carry the old always-ask workflow rules, and
    clients discover installed skills natively, so leaving them in place would
    keep those rules active after the managed block is upgraded.
    """
    path: Path
    identity: tuple[int, int]
    action: str = "Retire (backup kept)"


def _retired_in(root):
    found = []
    for name in common.RETIRED_SKILL_NAMES:
        path = root / name
        if common.is_link_or_reparse(path):
            raise ValueError(f"Refusing linked or reparse-point destination: {path}")
        if path.is_dir() and (path / "SKILL.md").is_file():
            common._validate_backup_root(root.parent / "getonmylevel-backups")
            found.append(RetiredSkill(path, common._identity(path)))
    return found


def plan_install(names, scope, repo, client):
    """Plan skill copies plus the upgrade steps an earlier install needs.

    The returned plans hold managed-block upgrades (``InstructionUpdate``) and
    retired skill directories (``RetiredSkill``); ``perform_install`` applies both.
    """
    repo, roots = roots_for(scope, repo, client)
    copies = common.preflight_skill_copy(SOURCE_ROOT, names, roots)
    plans = []
    scopes = ("user", "repo") if scope == "both" else (scope,)
    for kind, root in zip(scopes, roots):
        installed = {name for name in common.SKILL_NAMES if (root / name / "SKILL.md").is_file()}
        plans.extend(_retired_in(root))
        plans.extend(instructions.plan_instruction_upgrades(kind, repo if kind == "repo" else None, client,
                                                            available=installed | set(names)))
    return roots, copies, plans


def skill_status(scope, repo, client, names=None):
    """Read installed files and managed activation independently per scope.

    Errors stay attached to the affected scope so a broken repository path or
    managed block cannot hide valid user-wide state in ``both`` mode.
    """
    names = tuple(names or common.SKILL_NAMES)
    scopes = ("user", "repo") if scope == "both" else (scope,)
    result = {}
    for kind in scopes:
        try:
            target_repo, roots = roots_for(kind, repo, client)
            root = roots[0]
            active = instructions.active_skills(kind, target_repo, client)[kind]
            per_skill = {}
            for name in names:
                path = root / name
                if common.is_link_or_reparse(path):
                    raise ValueError(f"Refusing linked or reparse-point skill path: {path}")
                warning = None
                try:
                    path_info = path.lstat()
                except FileNotFoundError:
                    path_info = None
                if path_info is None:
                    installed = False
                elif not stat.S_ISDIR(path_info.st_mode):
                    installed = False
                    warning = f"Skill destination is not a directory: {path}"
                else:
                    skill_path = path / "SKILL.md"
                    if common.is_link_or_reparse(skill_path):
                        raise ValueError(f"Refusing linked or reparse-point skill file: {skill_path}")
                    try:
                        skill_info = skill_path.stat()
                    except FileNotFoundError:
                        skill_info = None
                    installed = skill_info is not None and stat.S_ISREG(skill_info.st_mode)
                    if skill_info is not None and not installed:
                        warning = f"Skill entry is not a regular file: {skill_path}"
                    elif not installed:
                        warning = f"Skill directory is missing SKILL.md: {path}"
                enabled = name in active
                per_skill[name] = {
                    "installed": installed,
                    "active": enabled,
                    "status": ("Installed and active by default" if installed and enabled else
                               "Installed and available on request" if installed else
                               "Not installed"),
                    "warning": (f"Managed instructions activate this skill, but its file is missing: {path / 'SKILL.md'}"
                                if enabled and not installed else warning),
                }
            result[kind] = {"skills": per_skill, "error": None}
        except (OSError, ValueError) as exc:
            result[kind] = {"skills": {}, "error": str(exc)}
    return result


def perform_install(copies, plans, client="codex"):
    retired = [plan for plan in plans if isinstance(plan, RetiredSkill)]
    updates = [plan for plan in plans if not isinstance(plan, RetiredSkill)]
    result = common.copy_skills(copies)
    if retired:
        backups, _ = perform_remove([(plan.path, plan.identity) for plan in retired], [], client)
        result = common.SkillCopyResult(result.installed, result.updated, (*result.backups, *backups))
    return result, instructions.write_instruction_updates(updates, client)


def plan_remove(names, scope, repo, client):
    selected = common.validate_selection(names, common.SKILL_NAMES, "skill")
    repo, roots = roots_for(scope, repo, client)
    paths = []
    for root in roots:
        for name in selected:
            path = root / name
            if common.is_link_or_reparse(path):
                raise ValueError(f"Refusing linked or reparse-point destination: {path}")
            if path.exists():
                if not path.is_dir() or not (path / "SKILL.md").is_file():
                    raise ValueError(f"Refusing directory without SKILL.md: {path}")
                common._validate_backup_root(root.parent / "getonmylevel-backups")
                paths.append((path, common._identity(path)))
        if set(selected) == set(common.SKILL_NAMES):
            paths.extend((plan.path, plan.identity) for plan in _retired_in(root))
    return paths, instructions.plan_selected_removals(scope, repo, selected, client)


def perform_remove(paths, plans, client):
    backups = []
    try:
        for path, identity in paths:
            common.check_managed_root(path.parent)
            if common.is_link_or_reparse(path) or not path.is_dir() or common._identity(path) != identity:
                raise ValueError(f"Destination changed since preview: {path}")
            backup_root = path.parent.parent / "getonmylevel-backups"
            common._validate_backup_root(backup_root)
            backup_root.mkdir(parents=True, exist_ok=True)
            backup = Path(tempfile.mkdtemp(prefix=f"{path.name}-", dir=backup_root))
            try:
                path.rename(backup / path.name)
            except OSError:
                backup.rmdir()
                raise
            backups.append(str(backup))
        written = instructions.write_instruction_removals(plans, client)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Removal stopped; completed backups: {', '.join(backups) or 'none'}. {exc}") from exc
    return backups, written


def plan_activation(selections, repo, client):
    """Plan exact per-scope activation and install only missing skill files."""
    copies, plans = [], []
    for scope, names in selections.items():
        target_repo, roots = roots_for(scope, repo, client)
        root = roots[0]
        common.check_managed_root(root)
        missing = []
        for name in names:
            path = root / name
            if common.is_link_or_reparse(path):
                raise ValueError(f"Refusing linked or reparse-point destination: {path}")
            if not (path / "SKILL.md").is_file():
                if path.exists():
                    raise ValueError(f"Refusing directory without SKILL.md: {path}")
                missing.append(name)
        if missing:
            copies.extend(common.preflight_skill_copy(SOURCE_ROOT, missing, roots))
        plans.extend(_retired_in(root))
        plans.extend(instructions.plan_instruction_updates(scope, target_repo, names, client))
    return copies, plans
