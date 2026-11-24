"""Plan and apply the optional stop hook that runs targeted checks, for every supported client.

All clients run the installed getonmylevel-verify skill's ``scripts/stop_check.py``:

- Claude Code: a ``Stop`` hook merged into ``settings.json``; failures exit 2.
- Codex: a ``Stop`` hook merged into ``hooks.json`` (same shape); failures exit 2.
  Codex skips new or changed hooks until they are trusted with ``/hooks``.
- GitHub Copilot CLI: an ``agentStop`` hook in its own ``hooks/getonmylevel-verify.json``;
  failures are a JSON ``block`` decision on stdout.
- OpenCode: a V2 plugin file in ``plugins/getonmylevel-verify.js`` that runs the
  script when a session goes idle and sends failures back as a prompt.

Merged files keep every other setting. Owned files carry a marker and are
only replaced or removed while the marker is present.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
import tempfile

import common

HOOK_MARKER = "getonmylevel-verify/scripts/stop_check.py"
OWNED_MARKER = "getonmylevel-managed: verify hook"
TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class HookPlan:
    path: Path
    original: bytes | None
    proposed: bytes | None
    action: str
    command: str
    client: str = "claude"
    notes: tuple[str, ...] = ()


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()


def settings_path(client: str = "claude") -> Path:
    if client == "claude":
        config = os.environ.get("CLAUDE_CONFIG_DIR")
        return (Path(config).expanduser() if config else Path.home() / ".claude") / "settings.json"
    if client == "codex":
        return _codex_home() / "hooks.json"
    if client == "copilot":
        home = os.environ.get("COPILOT_HOME")
        return (Path(home).expanduser() if home else Path.home() / ".copilot") / "hooks" / "getonmylevel-verify.json"
    if client == "opencode":
        return Path.home() / ".config" / "opencode" / "plugins" / "getonmylevel-verify.js"
    raise ValueError(f"Unknown client: {client}")


def _script(client: str) -> Path:
    script = common.skill_roots("user", None, client)[0] / "getonmylevel-verify" / "scripts" / "stop_check.py"
    if not script.is_file():
        raise FileNotFoundError(f"Install the getonmylevel-verify skill for {common.CLIENT_LABELS[client]} at user scope first; missing {script}")
    return script


def hook_command(client: str = "claude") -> str:
    python, script = Path(sys.executable).as_posix(), _script(client).as_posix()
    suffix = " --format json" if client == "copilot" else ""
    return f'"{python}" "{script}"{suffix}'


def _is_ours(hook: object) -> bool:
    return isinstance(hook, dict) and HOOK_MARKER in str(hook.get("command", "")).replace("\\", "/")


def _read(path: Path) -> bytes | None:
    if common.is_link_or_reparse(path):
        raise ValueError(f"Refusing linked or reparse-point hook file: {path}")
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _load_json(path: Path) -> tuple[bytes | None, dict]:
    original = _read(path)
    if original is None:
        return None, {}
    try:
        data = json.loads(original.decode("utf-8-sig")) if original.strip() else {}
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"Hook settings are not valid JSON; fix them first: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Hook settings must be a JSON object: {path}")
    return original, data


def _without_ours(data: dict) -> dict:
    hooks = data.get("hooks")
    if not isinstance(hooks, dict) or not isinstance(hooks.get("Stop"), list):
        return data
    groups = []
    for group in hooks["Stop"]:
        if isinstance(group, dict) and isinstance(group.get("hooks"), list):
            kept = [hook for hook in group["hooks"] if not _is_ours(hook)]
            if kept:
                groups.append({**group, "hooks": kept})
            elif not group["hooks"]:
                groups.append(group)
        else:
            groups.append(group)
    new_hooks = {**hooks, "Stop": groups} if groups else {k: v for k, v in hooks.items() if k != "Stop"}
    return {**data, "hooks": new_hooks} if new_hooks else {k: v for k, v in data.items() if k != "hooks"}


def _dump(data: dict) -> bytes:
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _merged_plan(action: str, client: str) -> HookPlan:
    """Claude Code settings.json and Codex hooks.json share the Stop hook shape."""
    path = settings_path(client)
    original, data = _load_json(path)
    notes = ("Codex runs new or changed hooks only after you review and trust them with /hooks.",) if client == "codex" else ()
    if action == "remove":
        cleaned = _without_ours(data)
        if cleaned == data:
            return HookPlan(path, original, original, "Not installed", "", client)
        return HookPlan(path, original, _dump(cleaned), "Remove", "", client)
    command = hook_command(client)
    cleaned = _without_ours(data)
    if not isinstance(cleaned.get("hooks", {}), dict) or not isinstance(cleaned.get("hooks", {}).get("Stop", []), list):
        raise ValueError(f"Unexpected hooks layout in {path}; add the hook manually.")
    hooks = dict(cleaned.get("hooks") or {})
    hooks["Stop"] = [*hooks.get("Stop", []), {"hooks": [{"type": "command", "command": command, "timeout": TIMEOUT_SECONDS}]}]
    proposed = {**cleaned, "hooks": hooks}
    if proposed == data:
        return HookPlan(path, original, original, "Already current", command, client, notes)
    return HookPlan(path, original, _dump(proposed), "Install" if cleaned == data else "Update", command, client, notes)


def _copilot_file(command: str) -> bytes:
    powershell = "& " + command  # a quoted executable path needs the call operator in PowerShell
    return _dump({"version": 1, "hooks": {"agentStop": [
        {"type": "command", "bash": command, "powershell": powershell, "timeoutSec": TIMEOUT_SECONDS}]}})


_OPENCODE_PLUGIN = """// {marker}. Written by getonmylevel tools/setup.py hooks; removed by `hooks remove`.
// Runs the project's targeted checks when a session goes idle and, if they fail,
// sends the failures back to the session as a prompt (once per idle, never twice in a row).
import {{ Plugin }} from "@opencode/plugin"
import {{ spawnSync }} from "node:child_process"

const PYTHON = {python}
const SCRIPT = {script}

export default Plugin.define({{
  id: "getonmylevel-verify",
  async setup(ctx) {{
    const continued = new Set()
    const controller = new AbortController()
    void (async () => {{
      for await (const event of ctx.event.subscribe({{ signal: controller.signal }})) {{
        if (event?.type !== "session.idle") continue
        const sessionID = event?.properties?.sessionID ?? event?.sessionID ?? event?.properties?.info?.id
        if (!sessionID) continue
        const active = continued.delete(sessionID)
        const input = JSON.stringify({{
          session_id: sessionID,
          cwd: ctx.location?.directory ?? process.cwd(),
          stop_hook_active: active,
        }})
        const run = spawnSync(PYTHON, [SCRIPT, "--format", "json"], {{ input, encoding: "utf8", timeout: {timeout_ms} }})
        let result
        try {{ result = JSON.parse(run.stdout || "{{}}") }} catch {{ continue }}
        if (result.decision !== "block" || !result.reason) continue
        continued.add(sessionID)
        try {{ await ctx.session.prompt({{ sessionID, text: result.reason }}) }} catch {{ continued.delete(sessionID) }}
      }}
    }})().catch(() => {{}})
    return () => controller.abort()
  }},
}})
"""


def _opencode_file(client: str) -> bytes:
    return _OPENCODE_PLUGIN.format(marker=OWNED_MARKER, python=json.dumps(Path(sys.executable).as_posix()),
                                   script=json.dumps(_script(client).as_posix()),
                                   timeout_ms=TIMEOUT_SECONDS * 1000).encode("utf-8")


def _owned(content: bytes) -> bool:
    # Copilot files carry no comment field, so the hook script path identifies them.
    return OWNED_MARKER.encode() in content or HOOK_MARKER.encode() in content


def _owned_plan(action: str, client: str) -> HookPlan:
    path = settings_path(client)
    original = _read(path)
    if original is not None and not _owned(original):
        raise ValueError(f"{path} exists but was not written by getonmylevel; refusing to change it.")
    if action == "remove":
        return HookPlan(path, original, None if original is not None else original,
                        "Remove" if original is not None else "Not installed", "", client)
    if client == "copilot":
        command = hook_command(client)
        proposed = _copilot_file(command)
        notes = ("Copilot CLI loads user hooks from this folder; the agentStop hook forces one more turn with the failures.",)
    else:
        proposed = _opencode_file(client)
        command = f'{Path(sys.executable).as_posix()} {_script(client).as_posix()} --format json (from an OpenCode plugin)'
        notes = ("OpenCode loads this V2 plugin from ~/.config/opencode/plugins. It targets the documented "
                 "Plugin.define, ctx.event.subscribe, and ctx.session.prompt API and has not been run in a live client.",)
    if proposed == original:
        return HookPlan(path, original, original, "Already current", command, client, notes)
    return HookPlan(path, original, proposed, "Install" if original is None else "Update", command, client, notes)


def plan(action: str, client: str = "claude") -> HookPlan:
    if action not in ("install", "remove"):
        raise ValueError(f"Unknown hook action: {action}")
    if client in ("claude", "codex"):
        return _merged_plan(action, client)
    if client in ("copilot", "opencode"):
        return _owned_plan(action, client)
    raise ValueError(f"Unknown client: {client}")


def status(client: str = "claude") -> str:
    path = settings_path(client)
    if client in ("claude", "codex"):
        _original, data = _load_json(path)
        stops = (data.get("hooks") or {}).get("Stop") or []
        found = [hook for group in stops if isinstance(group, dict) for hook in group.get("hooks", []) if _is_ours(hook)]
        return f"Installed: {found[0]['command']}" if found else "Not installed"
    original = _read(path)
    if original is None:
        return "Not installed"
    return "Installed" if _owned(original) else "A file not written by getonmylevel is at this path"


def apply(hook_plan: HookPlan) -> bool:
    if hook_plan.proposed == hook_plan.original:
        return False
    path = hook_plan.path
    if _read(path) != hook_plan.original:
        raise OSError(f"Hook file changed since preview; run the command again: {path}")
    if hook_plan.proposed is None:
        path.unlink()
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(hook_plan.proposed)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return True
