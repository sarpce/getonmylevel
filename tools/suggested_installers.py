"""User-wide installers for optional skills and tools suggested by the GUI."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
from typing import Callable

import common

RTK_URL = "https://github.com/rtk-ai/rtk"
RTK_INSTALL_URL = "https://www.rtk-ai.app/docs/getting-started/installation/"
LAST30_URL = "https://github.com/mvanhorn/last30days-skill"
CLI_ANYTHING_URL = "https://github.com/HKUDS/CLI-Anything"
LAST30_COMMIT = "bb2f1ed2b9f6d07b90557c5eebd736b566533fec"
CLI_ANYTHING_COMMIT = "34f519533bc175d2fe287ab8316b0dd99bb9cc43"
IMPECCABLE_URL = "https://github.com/pbakaus/impeccable"
IMPECCABLE_COMMIT = "b49177d32788f2dc585c42831d845dacf1ebed2c"
UI_UX_PRO_MAX_URL = "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill"
UI_UX_PRO_MAX_COMMIT = "a38d04c3d5c298c851dbe5e6ee1965ee3de42cb5"
ANTI_UI_SLOP_URL = "https://github.com/uizze/uizze"
ANTI_UI_SLOP_COMMIT = "4a0224f578f65a87f328e9c533b3d8bf1023c1f7"

_OPTIONAL_DESIGN_SKILLS = {
    "impeccable": ("impeccable", IMPECCABLE_URL, IMPECCABLE_COMMIT,
                   ".agents/skills/impeccable", ("SKILL.md", "reference", "scripts", "agents"),
                   ("LICENSE", "NOTICE.md"), "Impeccable design critique, audit, and polish skill"),
    "ui_ux_pro_max": ("ui-ux-pro-max", UI_UX_PRO_MAX_URL, UI_UX_PRO_MAX_COMMIT,
                      ".claude/skills/ui-ux-pro-max", ("SKILL.md", "data", "scripts", "references"),
                      ("LICENSE",), "UI UX Pro Max design-system and interface guidance"),
    "anti_ui_slop": ("anti-ui-slop", ANTI_UI_SLOP_URL, ANTI_UI_SLOP_COMMIT,
                     "skills/anti-ui-slop", ("SKILL.md", "LICENSE", "NOTICE"), (),
                     "Anti UI Slop product-specific design and UI review skill"),
}

_DESIGN_SKILL_EFFECTS = {
    "impeccable": "Its engine may download a platform binary on first use. The optional hook and live mode are not configured.",
    "ui_ux_pro_max": "Uses bundled Python 3 scripts and data. Its Codex skill path is adapted from the upstream Claude path.",
    "anti_ui_slop": "Uses its upstream public design catalogue when the agent follows a catalogue link.",
}

_INTEGRATION_PINS = {
    "last30days": LAST30_COMMIT,
    "cli_anything": CLI_ANYTHING_COMMIT,
    **{item_id: values[2] for item_id, values in _OPTIONAL_DESIGN_SKILLS.items()},
}

_INTEGRATION_EFFECTS = {
    "rtk": "No automatic installation is offered. A manual package-manager installation may execute package scripts; this project does not change Codex configuration.",
    "last30days": "Downloads the selected Git commit and copies skill files. The copied skill is not executed during installation; client configuration is unchanged.",
    "cli_anything": "Downloads the selected Git commit, then executes its upstream installer with your privileges. It copies skill files and does not configure Codex.",
    "impeccable": "Downloads the selected Git commit and copies skill files. It does not execute the skill or configure hooks; its engine may download a platform binary on first use.",
    "ui_ux_pro_max": "Downloads the selected Git commit and copies/adapts skill files and data. It does not execute the skill or change client configuration.",
    "anti_ui_slop": "Downloads the selected Git commit and copies skill files. It does not execute the skill or change client configuration.",
}


def integration_details(item_id: str, locations=(), *, detection_error: str | None = None) -> str:
    """Describe known status and installation facts without inferring copy identity."""
    item = next((item for item in SUGGESTED_ITEMS if item.id == item_id), None)
    if item is None:
        raise ValueError(f"Unknown suggested integration: {item_id}")
    if detection_error:
        status = f"Status: Unknown (status detection failed: {detection_error})"
    elif item_id == "rtk":
        status = f"Detected command: {', '.join(map(str, locations)) if isinstance(locations, (tuple, list)) else locations}; identity unknown, installed version unknown, provenance unknown." if locations else "Status: No rtk command detected on PATH; this does not rule out installations elsewhere."
    elif locations:
        status = "Detected copy at: " + ", ".join(map(str, locations))
    else:
        status = "Status: Not detected in supported skill locations."
    pin = _INTEGRATION_PINS.get(item_id)
    selected = f"New installation selection: commit {pin} (selected pin; not a test claim)." if pin else "New installation selection: none (manual installation only)."
    existing = "Existing installed version: unknown. Provenance: unknown; ownership by getonmylevel is not established by presence alone."
    if item_id == "rtk":
        existing = "Installed version: unknown. Provenance: unknown; this project does not manage that command."
    return "\n".join((f"Upstream project: {item.upstream_url}", status, selected, existing,
                       "Installation effects: " + _INTEGRATION_EFFECTS[item_id]))


@dataclass(frozen=True)
class SuggestedItem:
    id: str
    name: str
    description: str
    upstream_url: str
    planner: Callable[[], tuple[SuggestedInstallPlan | None, str | None]]
    installer: Callable[[SuggestedInstallPlan], tuple[bool, str]]


@dataclass(frozen=True)
class SuggestedInstallPlan:
    id: str
    name: str
    destination: Path | None
    details: str
    commands: tuple[tuple[str, ...], ...]
    data: tuple[str, ...] = ()
    manager: str = ""
    license: str = ""

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

    @property
    def confirmation_text(self) -> str:
        return f"{self.name}\nRemove these skill directories:\n" + "\n".join(f"  {path}" for path, _ in self.destinations)


def _run(command: list[str] | tuple[str, ...], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command), shell=False, stdin=subprocess.DEVNULL, capture_output=True,
        text=True, errors="replace", timeout=900, check=False, env=env,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())[-2000:]


def _run_checked(command: list[str] | tuple[str, ...], *, env: dict[str, str] | None = None) -> tuple[bool, str]:
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


def _rtk_plan(system: str | None = None, manager_path: str | None = None) -> tuple[SuggestedInstallPlan | None, str | None]:
    system = system or platform.system()
    existing_rtk = shutil.which("rtk")
    if existing_rtk:
        return None, f"An executable named rtk already exists at {existing_rtk}; it may be unrelated. Review {RTK_URL}."
    return None, (f"Automatic RTK installation is disabled because Winget and Homebrew select moving package versions. "
                  f"Install and verify a reviewed version manually using {RTK_INSTALL_URL}; upstream: {RTK_URL}.")


def _install_rtk(plan: SuggestedInstallPlan) -> tuple[bool, str]:
    env = dict(os.environ)
    if plan.manager == "brew":
        env["NONINTERACTIVE"] = "1"
    ok, detail = _run_checked(plan.commands[0], env=env)
    if ok:
        return True, "Package manager reported success. Open a new terminal if PATH has not refreshed; verify with `rtk --version` and `rtk gain`. " + detail
    return False, detail


def _git_path() -> str | None:
    return shutil.which("git")


def _is_present(path: Path) -> bool:
    return path.exists() or common.is_link_or_reparse(path)


def _safe_destination(path: Path) -> None:
    root = path.parent
    expanded = root.expanduser()
    if expanded.parent.name in (".agents", ".codex"):
        common.check_managed_root(root)
    else:
        # CODEX_HOME may point outside the conventional ~/.codex location.
        for candidate in (expanded, *expanded.parents):
            if common.is_link_or_reparse(candidate):
                raise ValueError(f"Refusing linked or reparse-point managed path: {candidate}")
    if common.is_link_or_reparse(path):
        raise ValueError(f"Refusing linked or reparse-point destination: {path}")
    if _is_present(path):
        raise FileExistsError(f"Destination already exists; updates are not performed: {path}")


def _skill_roots() -> tuple[Path, ...]:
    codex_home = os.environ.get("CODEX_HOME")
    roots = (Path.home() / ".agents" / "skills",
             (Path(codex_home).expanduser() if codex_home else Path.home() / ".codex") / "skills")
    result = []
    seen = set()
    for root in roots:
        expanded = root.expanduser()
        normalized = expanded.resolve(strict=False)
        if normalized not in seen:
            seen.add(normalized)
            result.append(expanded)
    return tuple(result)


def _skill_destinations(item_id: str) -> tuple[Path, ...]:
    name = {"last30days": "last30days", "cli_anything": "cli-anything",
            **{key: value[0] for key, value in _OPTIONAL_DESIGN_SKILLS.items()}}.get(item_id)
    if name is None:
        return ()
    return tuple(root / name for root in _skill_roots() if _is_present(root / name))


def _ensure_no_alternate_install(item_id: str, destination: Path) -> None:
    target = os.path.normcase(os.path.abspath(destination))
    others = [path for path in _skill_destinations(item_id)
              if os.path.normcase(os.path.abspath(path)) != target]
    if others:
        raise FileExistsError("The skill appeared in another supported location: " + ", ".join(map(str, others)))


def suggested_status() -> dict[str, tuple[Path, ...] | str | None]:
    """Return detected locations for suggested installs; RTK is only detected on PATH."""
    return {"last30days": _skill_destinations("last30days"),
            "cli_anything": _skill_destinations("cli_anything"),
            **{item_id: _skill_destinations(item_id) for item_id in _OPTIONAL_DESIGN_SKILLS},
            "rtk": shutil.which("rtk")}


def plan_removal(item_id: str) -> tuple[SuggestedRemovalPlan | None, str | None]:
    if item_id not in ("last30days", "cli_anything", *_OPTIONAL_DESIGN_SKILLS):
        return None, "Only detected skill directories can be removed here."
    paths = _skill_destinations(item_id)
    if not paths:
        return None, "The skill is no longer installed in the supported locations. Refresh and try again."
    name = next(item.name for item in SUGGESTED_ITEMS if item.id == item_id)
    destinations = []
    try:
        for path in paths:
            _safe_removal_destination(path)
            destinations.append((path, _identity(path)))
    except (OSError, ValueError) as exc:
        return None, f"Cannot safely prepare removal: {exc}"
    return SuggestedRemovalPlan(item_id, name, tuple(destinations)), None


def _identity(path: Path) -> tuple[int, int]:
    info = path.lstat()
    return info.st_dev, info.st_ino


def _safe_removal_destination(path: Path) -> None:
    root = path.parent
    _safe_destination_root(root)
    if common.is_link_or_reparse(path):
        raise ValueError(f"Refusing linked or reparse-point destination: {path}")
    if not path.is_dir():
        raise ValueError(f"Skill destination is not a directory: {path}")
    if not (path / "SKILL.md").is_file():
        raise ValueError(f"Destination does not contain SKILL.md: {path}")
    _reject_linked_tree(path)


def _safe_destination_root(root: Path) -> None:
    expanded = root.expanduser()
    for candidate in (expanded, *expanded.parents):
        if common.is_link_or_reparse(candidate):
            raise ValueError(f"Refusing linked or reparse-point managed path: {candidate}")
    if root.exists() and not root.is_dir():
        raise ValueError(f"Skills root is not a directory: {root}")


def remove_selected(plans: list[SuggestedRemovalPlan]) -> list[tuple[str, bool, str]]:
    results = []
    for plan in plans:
        removed = []
        try:
            for path, identity in plan.destinations:
                _safe_removal_destination(path)
                if _identity(path) != identity:
                    raise FileExistsError(f"Destination changed after confirmation: {path}")
                # Recheck immediately before deleting the confirmed tree.
                _safe_removal_destination(path)
                if _identity(path) != identity:
                    raise FileExistsError(f"Destination changed before removal: {path}")
                shutil.rmtree(path)
                removed.append(str(path))
            results.append((plan.name, True, "Removed:\n" + "\n".join(removed)))
        except (OSError, ValueError) as exc:
            detail = f"Removal stopped: {exc}"
            if removed:
                detail += "\nAlready removed: " + ", ".join(removed)
            results.append((plan.name, False, detail))
    return results


def _reject_linked_tree(root: Path) -> None:
    if common.is_link_or_reparse(root):
        raise ValueError(f"Refusing linked or reparse-point source: {root}")
    for current, dirs, files in os.walk(root, followlinks=False):
        parent = Path(current)
        for name in (*dirs, *files):
            entry = parent / name
            if common.is_link_or_reparse(entry):
                raise ValueError(f"Refusing linked or reparse-point source entry: {entry}")


def _git_checked(command: tuple[str, ...], env: dict[str, str]) -> tuple[bool, str]:
    return _run_checked(command, env=env)


def _clone(git: str, url: str, commit: str, destination: Path) -> tuple[bool, str]:
    env = dict(os.environ)
    env.update({"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"})
    commands = ((git, "init", str(destination)),
                (git, "-C", str(destination), "remote", "add", "origin", url),
                (git, "-C", str(destination), "fetch", "--depth", "1", "origin", commit),
                (git, "-C", str(destination), "checkout", "--detach", commit),
                (git, "-C", str(destination), "rev-parse", "HEAD"))
    for command in commands:
        ok, detail = _git_checked(command, env)
        if not ok:
            return False, detail
        if command[-2:] == ("rev-parse", "HEAD") and detail.strip().lower() != commit:
            return False, f"Pinned checkout verification failed: expected {commit}, got {detail.strip()}."
    return True, f"Verified pinned commit {commit}."


def _last30_plan() -> tuple[SuggestedInstallPlan | None, str | None]:
    git = _git_path()
    if not git:
        return None, f"Git is required. Install manually: {LAST30_URL}"
    destination = Path.home() / ".agents" / "skills" / "last30days"
    existing = _skill_destinations("last30days")
    if existing:
        return None, "Already installed at " + ", ".join(map(str, existing))
    try:
        _safe_destination(destination)
    except (OSError, ValueError) as exc:
        return None, f"{exc}. Manual instructions: {LAST30_URL}"
    commands = ((os.path.abspath(git), "init", "<temporary checkout>"),
                (os.path.abspath(git), "-C", "<temporary checkout>", "remote", "add", "origin", LAST30_URL),
                (os.path.abspath(git), "-C", "<temporary checkout>", "fetch", "--depth", "1", "origin", LAST30_COMMIT),
                (os.path.abspath(git), "-C", "<temporary checkout>", "checkout", "--detach", LAST30_COMMIT),
                (os.path.abspath(git), "-C", "<temporary checkout>", "rev-parse", "HEAD"),
                ("copy", "<checkout>/skills/last30days", str(destination)))
    details = (f"Installs the complete Last 30 Days skill directory user-wide from selected commit {LAST30_COMMIT}. "
               f"Requires Git; the installer verifies checkout HEAD before copying. Candidate pin, not claimed integration-tested. "
               f"The copied skill is not executed. Upstream: {LAST30_URL}.")
    return SuggestedInstallPlan("last30days", "Last 30 Days research skill", destination, details, commands,
                                data=(os.path.abspath(git),)), None


def _install_last30(plan: SuggestedInstallPlan) -> tuple[bool, str]:
    git = plan.data[0]
    destination = plan.destination
    assert destination is not None
    try:
        _ensure_no_alternate_install("last30days", destination)
        _safe_destination(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="getonmylevel-last30-") as temp:
            checkout = Path(temp) / "checkout"
            ok, detail = _clone(git, LAST30_URL, LAST30_COMMIT, checkout)
            if not ok:
                return False, detail
            source = checkout / "skills" / "last30days"
            _reject_linked_tree(checkout)
            if not (source / "SKILL.md").is_file():
                return False, f"Upstream checkout does not contain skills/last30days/SKILL.md. Review {LAST30_URL}."
            stage_parent = Path(tempfile.mkdtemp(prefix=".last30days-stage-", dir=destination.parent))
            stage = stage_parent / "last30days"
            try:
                shutil.copytree(source, stage, symlinks=False)
                _reject_linked_tree(stage)
                _ensure_no_alternate_install("last30days", destination)
                _safe_destination(destination)
                stage.rename(destination)
            finally:
                shutil.rmtree(stage_parent, ignore_errors=True)
    except (OSError, ValueError) as exc:
        return False, f"Installation failed: {exc}. Check for partial changes at {destination}."
    return True, f"Installed {destination}. Restart Codex to discover the skill."


def _cli_destination() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    base = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    return base / "skills" / "cli-anything"


def _cli_plan(system: str | None = None) -> tuple[SuggestedInstallPlan | None, str | None]:
    system = system or platform.system()
    git = _git_path()
    if not git:
        return None, f"Git is required. Install manually: {CLI_ANYTHING_URL}"
    destination = _cli_destination()
    existing = _skill_destinations("cli_anything")
    if existing:
        return None, "Already installed at " + ", ".join(map(str, existing))
    try:
        _safe_destination(destination)
    except (OSError, ValueError) as exc:
        return None, f"{exc}. Manual instructions: {CLI_ANYTHING_URL}"
    if system == "Windows":
        shell = shutil.which("pwsh") or shutil.which("powershell")
        script = "codex-skill/scripts/install.ps1"
        args = ("-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", f"<checkout>/{script}")
    elif system in ("Darwin", "Linux"):
        shell = shutil.which("bash")
        script = "codex-skill/scripts/install.sh"
        args = (f"<checkout>/{script}",)
    else:
        return None, f"Automatic installation is unsupported on {system}. See {CLI_ANYTHING_URL}."
    if not shell:
        return None, f"Required shell for this platform was not found. Install manually: {CLI_ANYTHING_URL}"
    command = (os.path.abspath(git), "init", "<temporary checkout>")
    fetch_commands = ((os.path.abspath(git), "-C", "<temporary checkout>", "remote", "add", "origin", CLI_ANYTHING_URL),
                      (os.path.abspath(git), "-C", "<temporary checkout>", "fetch", "--depth", "1", "origin", CLI_ANYTHING_COMMIT),
                      (os.path.abspath(git), "-C", "<temporary checkout>", "checkout", "--detach", CLI_ANYTHING_COMMIT),
                      (os.path.abspath(git), "-C", "<temporary checkout>", "rev-parse", "HEAD"))
    installer = (os.path.abspath(shell), *args)
    details = (f"Installs the CLI-Anything Codex generator skill and supporting resources user-wide; it does not install all application harnesses. "
               f"Requires Git and the platform shell. Uses selected commit {CLI_ANYTHING_COMMIT} and verifies checkout HEAD before executing its installer with your privileges. Candidate pin, not claimed integration-tested. Upstream: {CLI_ANYTHING_URL}.")
    return SuggestedInstallPlan("cli_anything", "CLI-Anything Codex generator skill", destination, details,
                                (command, *fetch_commands, installer), data=(os.path.abspath(git), os.path.abspath(shell), system)), None


def _validate_git_tree(git: str, checkout: Path, commit: str, source_paths: tuple[str, ...]) -> tuple[bool, str]:
    command = (git, "-C", str(checkout), "ls-tree", "-rz", "-r", "-t", commit, "--", *source_paths)
    try:
        result = _run(command)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Could not inspect pinned skill files. {exc}"
    if result.returncode:
        return False, f"Could not inspect pinned skill files. {_output(result)}"
    output = result.stdout
    entries = output.encode("utf-8", errors="surrogateescape").split(b"\0")
    found = set()
    for entry in entries:
        if not entry:
            continue
        metadata, path = entry.split(b"\t", 1)
        mode, object_type, _ = metadata.decode("ascii").split(" ", 2)
        if mode in ("120000", "160000"):
            return False, f"Pinned skill source contains a symlink or submodule at {path.decode('utf-8', errors='replace')}"
        found.add(path.decode("utf-8", errors="surrogateescape"))
    missing = [path for path in source_paths
               if path not in found and not any(entry.startswith(path.rstrip("/") + "/") for entry in found)]
    if missing:
        return False, "Pinned checkout is missing required skill files: " + ", ".join(missing)
    return True, "Verified selected skill files are regular tracked files."


def _design_skill_plan(item_id: str) -> tuple[SuggestedInstallPlan | None, str | None]:
    name, url, commit, source_path, required_paths, license_paths, description = _OPTIONAL_DESIGN_SKILLS[item_id]
    git = _git_path()
    if not git:
        return None, f"Git is required. Install manually from {url}."
    destination = Path.home() / ".agents" / "skills" / name
    existing = _skill_destinations(item_id)
    if existing:
        return None, "Already installed at " + ", ".join(map(str, existing))
    try:
        _safe_destination(destination)
    except (OSError, ValueError) as exc:
        return None, f"{exc}. Manual instructions: {url}"

    source_files = (source_path, *license_paths)
    commands = ((os.path.abspath(git), "init", "<temporary checkout>"),
                (os.path.abspath(git), "-C", "<temporary checkout>", "remote", "add", "origin", url),
                (os.path.abspath(git), "-C", "<temporary checkout>", "fetch", "--depth", "1", "origin", commit),
                (os.path.abspath(git), "-C", "<temporary checkout>", "checkout", "--detach", commit),
                (os.path.abspath(git), "-C", "<temporary checkout>", "rev-parse", "HEAD"),
                (os.path.abspath(git), "-C", "<temporary checkout>", "ls-tree", "-rz", "-r", "-t", commit, "--", *source_files),
                ("copy", f"<checkout>/{source_path}", str(destination)))
    details = (f"Installs the complete {description} from selected commit {commit} to {destination}. Requires Git and network access. "
               f"The installer verifies checkout HEAD and checks the selected skill files for symlinks before copying. "
               f"It does not execute the downloaded skill or configure hooks. {_DESIGN_SKILL_EFFECTS[item_id]} Upstream: {url}.")
    return SuggestedInstallPlan(item_id, description, destination, details, commands,
                                data=(os.path.abspath(git), commit, source_path, *required_paths, *license_paths)), None


def _design_skill_installer(plan: SuggestedInstallPlan) -> tuple[bool, str]:
    git, commit, source_path, *required_and_licenses = plan.data
    required_count = len(_OPTIONAL_DESIGN_SKILLS[plan.id][4])
    required_paths = tuple(required_and_licenses[:required_count])
    license_paths = tuple(required_and_licenses[required_count:])
    destination = plan.destination
    assert destination is not None
    try:
        _ensure_no_alternate_install(plan.id, destination)
        _safe_destination(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"getonmylevel-{plan.id}-") as temp:
            checkout = Path(temp) / "checkout"
            ok, detail = _clone(git, _OPTIONAL_DESIGN_SKILLS[plan.id][1], commit, checkout)
            if not ok:
                return False, detail
            source = checkout / Path(source_path)
            all_paths = (source_path, *license_paths)
            ok, detail = _validate_git_tree(git, checkout, commit, all_paths)
            if not ok:
                return False, detail
            _reject_linked_tree(source)
            for relative_path in required_paths:
                entry = source / relative_path
                if relative_path in ("SKILL.md", "LICENSE", "NOTICE", "NOTICE.md"):
                    if not entry.is_file():
                        return False, f"Required skill file is missing: {entry}"
                elif not entry.is_dir():
                    return False, f"Required skill resources are missing: {entry}"

            stage_parent = Path(tempfile.mkdtemp(prefix=f".{destination.name}-stage-", dir=destination.parent))
            stage = stage_parent / destination.name
            try:
                shutil.copytree(source, stage, symlinks=False)
                for license_path in license_paths:
                    shutil.copy2(checkout / license_path, stage / Path(license_path).name)
                if plan.id == "ui_ux_pro_max":
                    skill_file = stage / "SKILL.md"
                    skill_text = skill_file.read_text(encoding="utf-8")
                    skill_text = skill_text.replace("${CLAUDE_PLUGIN_ROOT}/.claude/skills/ui-ux-pro-max", "{SKILL_DIR}")
                    marker = "## Running the search tool"
                    skill_text = skill_text.replace(marker, marker + "\n\nFirst resolve `SKILL_DIR` to the absolute directory containing this loaded `SKILL.md`. Use that directory in the examples below.\n")
                    skill_file.write_text(skill_text, encoding="utf-8")
                _reject_linked_tree(stage)
                _ensure_no_alternate_install(plan.id, destination)
                _safe_destination(destination)
                stage.rename(destination)
            finally:
                shutil.rmtree(stage_parent, ignore_errors=True)
    except (OSError, ValueError) as exc:
        return False, f"Installation failed: {exc}. Check for partial changes at {destination}."
    return True, f"Installed {destination}. Restart Codex to discover the skill."


def _impeccable_plan():
    return _design_skill_plan("impeccable")


def _ui_ux_pro_max_plan():
    return _design_skill_plan("ui_ux_pro_max")


def _anti_ui_slop_plan():
    return _design_skill_plan("anti_ui_slop")


def _install_cli(plan: SuggestedInstallPlan) -> tuple[bool, str]:
    destination = plan.destination
    assert destination is not None
    git, shell, system = plan.data
    try:
        _ensure_no_alternate_install("cli_anything", destination)
        _safe_destination(destination)
        with tempfile.TemporaryDirectory(prefix="getonmylevel-cli-anything-") as temp:
            checkout = Path(temp) / "checkout"
            ok, detail = _clone(git, CLI_ANYTHING_URL, CLI_ANYTHING_COMMIT, checkout)
            if not ok:
                return False, detail
            _reject_linked_tree(checkout)
            script = checkout / "codex-skill" / "scripts" / ("install.ps1" if system == "Windows" else "install.sh")
            if not script.is_file():
                return False, f"Upstream installer was not found: {script}. Review {CLI_ANYTHING_URL}."
            command = ((shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script))
                       if system == "Windows" else (shell, str(script)))
            _ensure_no_alternate_install("cli_anything", destination)
            _safe_destination(destination)
            env = dict(os.environ)
            env.update({"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"})
            ok, detail = _run_checked(command, env=env)
            if not ok:
                return False, f"Upstream installer failed and may have made partial changes at {destination}. {detail}"
            if not _is_present(destination):
                return False, f"Installer reported success but destination was not created: {destination}"
    except (OSError, ValueError) as exc:
        return False, f"Installation failed and may have made partial changes at {destination}: {exc}"
    return True, f"Installed {destination}. Restart Codex to discover the skill."


SUGGESTED_ITEMS = (
    SuggestedItem("rtk", "RTK command-output optimizer", "Reduces common command output; standalone package.", RTK_URL,
                  _rtk_plan, _install_rtk),
    SuggestedItem("last30days", "Last 30 Days research skill", "Researches recent discussions and sources.", LAST30_URL,
                  _last30_plan, _install_last30),
    SuggestedItem("cli_anything", "CLI-Anything Codex generator skill", "Generates agentic harnesses for graphical applications.", CLI_ANYTHING_URL,
                  _cli_plan, _install_cli),
    SuggestedItem("impeccable", "Impeccable UI/UX skill", "Design critique, accessibility audits, and UI polish.", IMPECCABLE_URL,
                  _impeccable_plan, _design_skill_installer),
    SuggestedItem("ui_ux_pro_max", "UI UX Pro Max design skill", "Searchable design-system guidance for interface work.", UI_UX_PRO_MAX_URL,
                  _ui_ux_pro_max_plan, _design_skill_installer),
    SuggestedItem("anti_ui_slop", "Anti UI Slop skill", "Product-specific interface guidance and a UI quality gate.", ANTI_UI_SLOP_URL,
                  _anti_ui_slop_plan, _design_skill_installer),
)


def plan_selected(selected_ids: list[str]) -> tuple[list[SuggestedInstallPlan] | None, str | None]:
    """Plan all selections before any confirmation or side effects."""
    if not selected_ids:
        return None, "Select at least one suggested skill or tool."
    by_id = {item.id: item for item in SUGGESTED_ITEMS}
    if len(set(selected_ids)) != len(selected_ids) or any(item_id not in by_id for item_id in selected_ids):
        return None, "The suggested selection is invalid."
    plans = []
    errors = []
    for item_id in selected_ids:
        item = by_id[item_id]
        plan, error = item.planner()
        if error:
            errors.append(f"{item.name}: {error}")
        elif plan is not None:
            plans.append(plan)
    if errors:
        return None, "Cannot prepare the selected items; nothing will be installed:\n\n" + "\n\n".join(errors)
    return plans, None


def install_selected(plans: list[SuggestedInstallPlan]) -> list[tuple[str, bool, str]]:
    """Install plans in selection order and retain independent outcomes."""
    installers = {item.id: item.installer for item in SUGGESTED_ITEMS}
    results = []
    for plan in plans:
        try:
            success, detail = installers[plan.id](plan)
        except Exception as exc:
            success, detail = False, f"Installer failed; partial changes may remain: {exc}"
        results.append((plan.name, success, detail))
    return results
