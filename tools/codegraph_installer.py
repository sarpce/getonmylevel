"""Plan and configure the optional user-wide CodeGraph dependency."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import shutil
import subprocess


PACKAGE = "@colbymchenry/codegraph"
def install_args(client: str = "codex") -> tuple[str, ...]:
    if client not in ("codex", "claude"):
        raise ValueError(f"Unsupported CodeGraph target: {client}")
    return ("install", f"--target={client}", "--location=global", "--yes")


INSTALL_ARGS = install_args()
TIMEOUT_SECONDS = 900


def _client_label(client: str) -> str:
    return "Claude Code" if client == "claude" else "Codex"


@dataclass(frozen=True)
class CodeGraphPlan:
    executable: tuple[str, ...] | None
    npm_install: tuple[str, ...] | None
    details: str
    prefix: Path | None = None
    client: str = "codex"

    @property
    def commands(self) -> tuple[tuple[str, ...], ...]:
        return tuple(command for command in (self.npm_install, self.executable and (*self.executable, *install_args(self.client))) if command)


def _run(command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(list(command), shell=False, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, errors="replace",
                              timeout=TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("CodeGraph setup command timed out after 15 minutes.") from exc


def _prefix(npm_command: tuple[str, ...]) -> Path:
    result = _run((*npm_command, "prefix", "-g"))
    if result.returncode:
        raise RuntimeError("Could not resolve npm's global package prefix: " + (result.stderr or result.stdout).strip())
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError("npm did not return exactly one global prefix path.")
    path = Path(lines[0]).expanduser()
    if not path.is_absolute():
        raise RuntimeError("npm returned a non-absolute global prefix path.")
    return path


def _windows_node_npm() -> tuple[Path, Path]:
    node = shutil.which("node.exe") or shutil.which("node")
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not node or not npm:
        raise RuntimeError("Node.js and npm are required to install CodeGraph. Install Node.js, then reopen the installer.")
    node_path, npm_path = Path(node).resolve(), Path(npm).resolve()
    candidates = [node_path.parent / "node_modules" / "npm" / "bin" / "npm-cli.js",
                  npm_path.parent / "node_modules" / "npm" / "bin" / "npm-cli.js"]
    cli = next((candidate for candidate in candidates if candidate.is_file()), None)
    if cli is None:
        raise RuntimeError("Could not safely locate npm-cli.js beside Node.js; install CodeGraph manually with npm.")
    return node_path, cli


def _package_cli(prefix: Path) -> Path:
    package = prefix / "node_modules" / "@colbymchenry" / "codegraph"
    current = package / "npm-shim.js"
    legacy = package / "dist" / "bin" / "codegraph.js"
    return legacy if legacy.is_file() and not current.is_file() else current


def plan_install(client: str = "codex") -> CodeGraphPlan:
    """Inspect prerequisites and construct a fixed, user-wide client plan."""
    args = install_args(client)
    existing = shutil.which("codegraph")
    if existing:
        path = Path(existing).resolve()
        if os.name == "nt" and path.suffix.lower() in (".cmd", ".bat"):
            node, _ = _windows_node_npm()
            cli = _package_cli(path.parent)
            if not cli.is_file():
                raise RuntimeError("An existing CodeGraph command uses a Windows script wrapper whose package CLI could not be identified safely. Configure it manually using the upstream instructions.")
            executable = (str(node), str(cli))
        else:
            executable = (str(path),)
        return CodeGraphPlan(executable, None, f"Existing CodeGraph command found at {path}; it will not be upgraded. Configure {_client_label(client)} globally.", client=client)

    if os.name == "nt" or platform.system() == "Windows":
        node, npm_cli = _windows_node_npm()
        npm_prefix_command = (str(node), str(npm_cli))
        prefix = _prefix(npm_prefix_command)
        npm_install = (*npm_prefix_command, "install", "-g", PACKAGE)
        installed_cli = _package_cli(prefix)
        executable = (str(node), str(installed_cli))
    else:
        npm = shutil.which("npm")
        if not npm or not shutil.which("node"):
            raise RuntimeError("Node.js and npm are required to install CodeGraph. Install Node.js, then reopen the installer.")
        npm_command = (str(Path(npm).resolve()),)
        prefix = _prefix(npm_command)
        npm_install = (*npm_command, "install", "-g", PACKAGE)
        executable = (str(prefix / "bin" / "codegraph"),)
    return CodeGraphPlan(executable, npm_install,
                         f"Install {PACKAGE} for this user, then configure {_client_label(client)} globally. No project will be initialized.", prefix, client)


def _checked(command: tuple[str, ...]) -> str:
    result = _run(command)
    output = "\n".join(text.strip() for text in (result.stdout, result.stderr) if text and text.strip())[-3000:]
    if result.returncode:
        raise RuntimeError(f"Command exited with status {result.returncode}: {' '.join(command)}" + (f"\n{output}" if output else ""))
    return output


def install(plan: CodeGraphPlan) -> str:
    """Run the confirmed package install and Codex configuration steps."""
    if plan.npm_install:
        _checked(plan.npm_install)
    if not plan.executable:
        raise RuntimeError("No CodeGraph executable was planned.")
    executable_path = Path(plan.executable[-1])
    if not executable_path.is_file():
        raise RuntimeError(f"CodeGraph CLI was not found after installation at {executable_path}. Package installation may have completed; Codex was not configured.")
    _checked((*plan.executable, *install_args(plan.client)))
    label = _client_label(plan.client)
    return f"CodeGraph is configured for {label} globally. No project was initialized. Restart {label} if the MCP server is not available."
