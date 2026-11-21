"""Shared, headless operations for bundled skill installation."""
from pathlib import Path
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
        if common.canonical(repo) == SOURCE_REPO:
            raise ValueError("The target repository must differ from this source checkout.")
    else:
        repo = None
    return repo, common.skill_roots(scope, repo, client)


def plan_install(names, scope, repo, client):
    repo, roots = roots_for(scope, repo, client)
    copies = common.preflight_skill_copy(SOURCE_ROOT, names, roots)
    plans = instructions.plan_instruction_updates(scope, repo, names, client)
    return roots, copies, plans


def perform_install(copies, plans, client="codex"):
    result = common.copy_skills(copies)
    return result, instructions.write_instruction_updates(plans, client)


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
