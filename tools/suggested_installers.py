"""Optional third-party skills, kept only where a controlled evaluation shows a benefit.

Each suggestion records the evidence it is kept on and is copied from a pinned
upstream commit into the selected client's user-wide skill directory; nothing
upstream is executed.

Earlier releases suggested RTK, Last 30 Days, CLI-Anything, Impeccable,
UI UX Pro Max, and Anti UI Slop. None had a controlled evaluation showing a
benefit for coding tasks, and RTK's independent benchmark showed no cost
saving, so they are no longer offered. Copies an earlier release installed can
still be removed (``RETIRED_ITEMS``).
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import common

SAMBER_URL = "https://github.com/samber/cc-skills-golang"
SAMBER_COMMIT = "d68d80aec298e1b74b37c2a472c002b5217248b3"


@dataclass(frozen=True)
class SuggestedItem:
    id: str
    name: str
    description: str
    upstream_url: str
    evidence: str
    repo: str
    commit: str
    source_path: str   # skill directory inside the upstream repository
    skill_name: str    # installed directory name
    license_path: str  # upstream license copied into the skill directory


@dataclass(frozen=True)
class SuggestedInstallPlan:
    id: str
    name: str
    destination: Path | None
    details: str
    commands: tuple[tuple[str, ...], ...]
    client: str = "codex"

    @property
    def confirmation_text(self) -> str:
        commands = "\n".join("  " + " ".join(command) for command in self.commands)
        destination = f"\nDestination: {self.destination}" if self.destination else ""
        return f"{self.name}\n{self.details}{destination}\nCommands/actions:\n{commands}"


@dataclass(frozen=True)
class SuggestedRemovalPlan:
    id: str
    name: str
    destinations: tuple[tuple[Path, tuple[int, int]], ...]
    client: str = "codex"

    @property
    def confirmation_text(self) -> str:
        return f"{self.name}\nMove these skill directories to getonmylevel-backups:\n" + "\n".join(f"  {path}" for path, _ in self.destinations)


SUGGESTED_ITEMS = (
    SuggestedItem(
        "go_viper", "Go: spf13/viper configuration skill",
        "For Go projects that use github.com/spf13/viper: precedence, env binding, and test isolation.",
        SAMBER_URL,
        "SWE-Skills-Bench (arXiv 2603.15401): one of 4 of 98 public skills with a significant gain; "
        "pass ratio 59.6% to 77.3% (+17.7 points) on Viper tasks. Helps only on matching stacks.",
        SAMBER_URL, SAMBER_COMMIT, "skills/golang-spf13-viper", "golang-spf13-viper", "LICENSE"),
    SuggestedItem(
        "go_testify", "Go: stretchr/testify testing skill",
        "For Go projects that test with github.com/stretchr/testify: assert, require, mock, and suites.",
        SAMBER_URL,
        "SWE-Skills-Bench (arXiv 2603.15401): one of 4 of 98 public skills with a significant gain "
        "(+4.9 points). Helps only on matching stacks.",
        SAMBER_URL, SAMBER_COMMIT, "skills/golang-stretchr-testify", "golang-stretchr-testify", "LICENSE"),
)

# Suggestions from earlier releases: removal only. Values are installed directory names.
RETIRED_ITEMS = {
    "last30days": ("Last 30 Days research skill", "last30days"),
    "impeccable": ("Impeccable UI/UX skill", "impeccable"),
    "ui_ux_pro_max": ("UI UX Pro Max design skill", "ui-ux-pro-max"),
    "anti_ui_slop": ("Anti UI Slop skill", "anti-ui-slop"),
    "cli_anything": ("CLI-Anything Codex generator skill", "cli-anything"),
}
# Earlier versions of this release also listed Playwright and a Next.js docs index as
# manual suggestions. They installed nothing, so there is nothing to remove.

_BY_ID = {item.id: item for item in SUGGESTED_ITEMS}


def _item(item_id: str) -> SuggestedItem:
    if item_id not in _BY_ID:
        raise ValueError(f"Unknown suggested item: {item_id}")
    return _BY_ID[item_id]


# --- process and git helpers -------------------------------------------------

def _run(command, *, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(list(command), shell=False, stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, errors="replace", timeout=900, check=False, env=env)


def _output(result: subprocess.CompletedProcess) -> str:
    return "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())[-2000:]


def _run_checked(command, *, env=None) -> tuple[bool, str]:
    try:
        result = _run(command, env=env)
    except subprocess.TimeoutExpired:
        return False, "The operation timed out after 15 minutes."
    except OSError as exc:
        return False, f"Could not start the command: {exc}"
    output = _output(result)
    if result.returncode:
        return False, f"Command exited with status {result.returncode}." + (f"\n\n{output}" if output else "")
    return True, output


def _git_path() -> str | None:
    return shutil.which("git")


def _clone(git: str, url: str, commit: str, destination: Path) -> tuple[bool, str]:
    env = dict(os.environ)
    env.update({"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"})
    commands = ((git, "init", str(destination)),
                (git, "-C", str(destination), "remote", "add", "origin", url),
                (git, "-C", str(destination), "fetch", "--depth", "1", "origin", commit),
                (git, "-C", str(destination), "checkout", "--detach", commit),
                (git, "-C", str(destination), "rev-parse", "HEAD"))
    for command in commands:
        ok, detail = _run_checked(command, env=env)
        if not ok:
            return False, detail
        if command[-2:] == ("rev-parse", "HEAD") and detail.strip().lower() != commit:
            return False, f"Pinned checkout verification failed: expected {commit}, got {detail.strip()}."
    return True, f"Verified pinned commit {commit}."


def _validate_git_tree(git: str, checkout: Path, commit: str, source_paths: tuple[str, ...]) -> tuple[bool, str]:
    command = (git, "-C", str(checkout), "ls-tree", "-rz", "-r", "-t", commit, "--", *source_paths)
    try:
        result = _run(command)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Could not inspect pinned skill files. {exc}"
    if result.returncode:
        return False, f"Could not inspect pinned skill files. {_output(result)}"
    found = set()
    for entry in result.stdout.encode("utf-8", errors="surrogateescape").split(b"\0"):
        if not entry:
            continue
        metadata, path = entry.split(b"\t", 1)
        mode = metadata.decode("ascii").split(" ", 2)[0]
        if mode in ("120000", "160000"):
            return False, f"Pinned skill source contains a symlink or submodule at {path.decode('utf-8', errors='replace')}"
        found.add(path.decode("utf-8", errors="surrogateescape"))
    missing = [path for path in source_paths
               if path not in found and not any(entry.startswith(path.rstrip("/") + "/") for entry in found)]
    if missing:
        return False, "Pinned checkout is missing required skill files: " + ", ".join(missing)
    return True, "Verified selected skill files are regular tracked files."


# --- destinations ------------------------------------------------------------

def _skill_root(client: str) -> Path:
    if client not in common.CLIENTS:
        raise ValueError(f"Unknown client: {client}")
    return common.skill_roots("user", None, client)[0]


def _discovery_roots(client: str) -> tuple[Path, ...]:
    """Directories the client scans for user-wide skills; OpenCode also reads Claude and Codex locations."""
    roots = [_skill_root(client)]
    if client == "opencode":
        roots += [_skill_root("claude"), _skill_root("codex")]
    elif client == "codex":
        codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
        roots.append(codex_home / "skills")
    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return tuple(unique)


def _is_present(path: Path) -> bool:
    return path.exists() or common.is_link_or_reparse(path)


def _check_root(root: Path) -> None:
    expanded = root.expanduser()
    for candidate in (expanded, *expanded.parents):
        if common.is_link_or_reparse(candidate):
            raise ValueError(f"Refusing linked or reparse-point managed path: {candidate}")
    if root.exists() and not root.is_dir():
        raise ValueError(f"Skills root is not a directory: {root}")


def _reject_linked_tree(root: Path) -> None:
    if common.is_link_or_reparse(root):
        raise ValueError(f"Refusing linked or reparse-point path: {root}")
    for current, dirs, files in os.walk(root, followlinks=False):
        for name in (*dirs, *files):
            entry = Path(current) / name
            if common.is_link_or_reparse(entry):
                raise ValueError(f"Refusing linked or reparse-point entry: {entry}")


def _identity(path: Path) -> tuple[int, int]:
    info = path.lstat()
    return info.st_dev, info.st_ino


def _copies(directory: str, client: str) -> tuple[Path, ...]:
    return tuple(root / directory for root in _discovery_roots(client) if _is_present(root / directory))


# --- status ------------------------------------------------------------------

def suggested_status(client: str = "codex") -> dict[str, tuple[Path, ...] | str | None]:
    status: dict[str, tuple[Path, ...] | str | None] = {}
    for item in SUGGESTED_ITEMS:
        status[item.id] = _copies(item.skill_name, client)
    return status


def retired_status(client: str = "codex") -> dict[str, tuple[Path, ...]]:
    return {item_id: copies for item_id, (_name, directory) in RETIRED_ITEMS.items()
            if (copies := _copies(directory, client))}


def integration_details(item_id: str, locations=(), *, detection_error: str | None = None, client: str = "codex") -> str:
    item = _item(item_id)
    if detection_error:
        status = f"Status: unknown (detection failed: {detection_error})"
    elif locations:
        status = "Detected copy at: " + ", ".join(map(str, locations)) + "; version and provenance unknown."
    else:
        status = f"Status: not installed for {common.CLIENT_LABELS[client]}; destination: {_skill_root(client) / item.skill_name}"
    lines = [f"Upstream: {item.upstream_url}", f"Why it is suggested: {item.evidence}", status]
    lines += [f"Pinned source: {item.repo} at commit {item.commit}, path {item.source_path} (license copied with it).",
                  "Effects: fetches that commit with Git and copies the skill directory. Nothing upstream is executed; "
              "client configuration is unchanged. The skill loads only when its description matches the task."]
    return "\n".join(lines)


# --- install -----------------------------------------------------------------

def plan_selected(selected_ids: list[str], client: str = "codex") -> tuple[list[SuggestedInstallPlan] | None, str | None]:
    plans = []
    for item_id in selected_ids:
        if item_id in RETIRED_ITEMS:
            return None, (f"{RETIRED_ITEMS[item_id][0]} is no longer suggested: no controlled evaluation showed a benefit "
                          "for coding tasks. An existing copy can still be removed.")
        item = _item(item_id)
        git = _git_path()
        if not git:
            return None, "Git is required to fetch pinned skill copies."
        try:
            root = _skill_root(client)
            _check_root(root)
            existing = _copies(item.skill_name, client)
            if existing:
                return None, f"{item.name} is already present at {', '.join(map(str, existing))}; remove it first to reinstall the pinned copy."
        except (OSError, ValueError) as exc:
            return None, str(exc)
        destination = root / item.skill_name
        commands = ((git, "fetch", item.repo, item.commit), ("copy", item.source_path, str(destination)))
        plans.append(SuggestedInstallPlan(item.id, item.name, destination,
                                          f"{item.evidence}\nPinned commit {item.commit}; files are copied, not executed.",
                                          commands, client))
    return plans, None


def _install_skill(plan: SuggestedInstallPlan) -> tuple[bool, str]:
    item = _item(plan.id)
    git = _git_path()
    if not git or plan.destination is None:
        return False, "Git is required."
    destination = plan.destination
    try:
        _check_root(destination.parent)
        if _is_present(destination):
            return False, f"Destination appeared after confirmation: {destination}"
        with tempfile.TemporaryDirectory(prefix=f"getonmylevel-{item.id}-") as temp:
            checkout = Path(temp) / "checkout"
            ok, detail = _clone(git, item.repo, item.commit, checkout)
            if not ok:
                return False, detail
            ok, detail = _validate_git_tree(git, checkout, item.commit, (item.source_path, item.license_path))
            if not ok:
                return False, detail
            source = checkout / item.source_path
            _reject_linked_tree(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".getonmylevel-stage-", dir=destination.parent))
            try:
                staged = staging / item.skill_name
                shutil.copytree(source, staged)
                shutil.copy2(checkout / item.license_path, staged / "LICENSE.upstream")
                if _is_present(destination):
                    return False, f"Destination appeared during installation: {destination}"
                staged.rename(destination)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
        return True, f"Installed {destination} from {item.repo} at {item.commit}."
    except (OSError, ValueError, shutil.Error) as exc:
        return False, f"Installation stopped: {exc}"


def install_selected(plans: list[SuggestedInstallPlan]) -> list[tuple[str, bool, str]]:
    return [(plan.name, *_install_skill(plan)) for plan in plans]


# --- removal -----------------------------------------------------------------

def plan_removal(item_id: str, client: str = "codex") -> tuple[SuggestedRemovalPlan | None, str | None]:
    if item_id in _BY_ID:
        item = _BY_ID[item_id]
        name, directory = item.name, item.skill_name
    elif item_id in RETIRED_ITEMS:
        name, directory = RETIRED_ITEMS[item_id]
    else:
        return None, f"Unknown suggested item: {item_id}"
    destinations = []
    try:
        for path in _copies(directory, client):
            _check_root(path.parent)
            if common.is_link_or_reparse(path) or not path.is_dir() or not (path / "SKILL.md").is_file():
                return None, f"Refusing to remove {path}: not a plain skill directory with SKILL.md."
            _reject_linked_tree(path)
            destinations.append((path, _identity(path)))
    except (OSError, ValueError) as exc:
        return None, str(exc)
    if not destinations:
        return None, f"{name} is not installed for {common.CLIENT_LABELS[client]}."
    return SuggestedRemovalPlan(item_id, name, tuple(destinations), client), None


def remove_selected(plans: list[SuggestedRemovalPlan]) -> list[tuple[str, bool, str]]:
    results = []
    for plan in plans:
        moved = []
        try:
            for path, identity in plan.destinations:
                if common.is_link_or_reparse(path) or not path.is_dir() or _identity(path) != identity:
                    raise FileExistsError(f"Destination changed after confirmation: {path}")
                backup_root = path.parent.parent / "getonmylevel-backups"
                if common.is_link_or_reparse(backup_root):
                    raise ValueError(f"Refusing linked backup directory: {backup_root}")
                backup_root.mkdir(parents=True, exist_ok=True)
                backup = Path(tempfile.mkdtemp(prefix=f"{path.name}-", dir=backup_root))
                path.rename(backup / path.name)
                moved.append(f"{path} -> {backup / path.name}")
            results.append((plan.name, True, "Moved to backups:\n" + "\n".join(moved)))
        except (OSError, ValueError) as exc:
            detail = f"Removal stopped: {exc}"
            if moved:
                detail += "\nAlready moved: " + ", ".join(moved)
            results.append((plan.name, False, detail))
    return results
