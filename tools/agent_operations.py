"""Tk-free managed agent role file operations shared by the GUI and CLI."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import platform
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import tomllib
from typing import Any

import common

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = REPO_ROOT / "optional" / "agents"
MAX_LINE_BYTES = 1_000_000
MAX_PAGES = 10
MAX_MODELS = 1000
MAX_SECONDS = 20
MARKER = "# getonmylevel-managed-v1"
CLAUDE_MARKER = "<!-- getonmylevel-managed-v1 -->"
CLAUDE_MODELS = ("", "inherit", "sonnet", "opus", "haiku", "fable")
CLAUDE_EFFORTS = ("", "low", "medium", "high", "xhigh", "max")


def find_codex() -> str:
    """Find Codex on PATH or in a standard Windows VS Code extension directory."""
    names = ("codex.exe", "codex.cmd") if os.name == "nt" else ("codex",)
    for name in names:
        executable = shutil.which(name)
        if executable:
            return executable

    if os.name == "nt":
        architecture = "windows-arm64" if platform.machine().lower() in ("arm64", "aarch64") else "windows-x86_64"
        candidates: list[tuple[tuple[int, ...], Path]] = []
        for directory in (".vscode", ".vscode-insiders"):
            extensions = Path.home() / directory / "extensions"
            for extension in extensions.glob("openai.chatgpt-*"):
                match = re.fullmatch(r"openai\.chatgpt-(\d+(?:\.\d+)+)(?:-[\w.-]+)?", extension.name)
                if not match or not extension.is_dir():
                    continue
                executable = extension / "bin" / architecture / "codex.exe"
                if executable.is_file():
                    version = tuple(int(component) for component in match.group(1).split("."))
                    candidates.append((version, executable))
        if candidates:
            return str(max(candidates, key=lambda candidate: candidate[0])[1])

    raise FileNotFoundError(
        "Codex was not found. Install Codex and make it available on PATH"
        + (" or install the Codex VS Code extension in its standard location" if os.name == "nt" else "")
        + ", then restart the GUI."
    )


class AppServer:
    """Small bounded JSON-RPC client for `codex app-server --listen stdio://`."""

    def __init__(self) -> None:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.process = subprocess.Popen(
            [find_codex(), "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            creationflags=flags,
        )
        self.lines: queue.Queue[bytes | BaseException | None] = queue.Queue()
        self.reader = threading.Thread(target=self._read_lines, daemon=True)
        self.reader.start()
        self.next_id = 1

    def _read_lines(self) -> None:
        assert self.process.stdout is not None
        try:
            while True:
                line = self.process.stdout.readline(MAX_LINE_BYTES + 1)
                if not line:
                    self.lines.put(None)
                    return
                if len(line) > MAX_LINE_BYTES:
                    self.lines.put(ValueError("Codex app-server response exceeded the size limit."))
                    return
                self.lines.put(line)
        except BaseException as exc:
            self.lines.put(exc)

    def _send(self, payload: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(encoded) > MAX_LINE_BYTES:
            raise ValueError("Request exceeded the size limit.")
        self.process.stdin.write(encoded)
        self.process.stdin.flush()

    def _response(self, request_id: int, deadline: float) -> dict[str, Any]:
        import time

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Timed out waiting for Codex app-server.")
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError("Timed out waiting for Codex app-server.") from exc
            if line is None:
                raise RuntimeError("Codex app-server closed its output unexpectedly.")
            if isinstance(line, BaseException):
                raise line
            try:
                message = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError("Codex app-server returned invalid JSON.") from exc
            if isinstance(message, dict) and message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError("Codex app-server rejected the request.")
                result = message.get("result")
                if not isinstance(result, dict):
                    raise RuntimeError("Codex app-server returned an unexpected response.")
                return result

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        import time

        return self._response(request_id, min(self.deadline, time.monotonic() + MAX_SECONDS))

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def models(self) -> dict[str, list[str]]:
        import time

        self.deadline = time.monotonic() + MAX_SECONDS
        self.request("initialize", {"clientInfo": {"name": "getonmylevel", "title": "getonmylevel", "version": "1.0"}})
        self.notify("initialized")
        choices: dict[str, list[str]] = {}
        cursor = None
        seen_cursors: set[str] = set()
        total = 0
        for _ in range(MAX_PAGES):
            params: dict[str, Any] = {"limit": 100, "includeHidden": False}
            if cursor is not None:
                params["cursor"] = cursor
            result = self.request("model/list", params)
            data = result.get("data")
            if not isinstance(data, list):
                raise RuntimeError("Codex app-server model/list returned no model list.")
            for model in data:
                if not isinstance(model, dict):
                    continue
                if "model" in model:
                    model_id = model["model"]
                    if not isinstance(model_id, str) or not model_id.strip():
                        raise RuntimeError("Codex app-server returned an invalid model identifier.")
                else:
                    # Compatibility fallback for older responses that expose only `id`.
                    model_id = model.get("id")
                    if not isinstance(model_id, str) or not model_id.strip():
                        raise RuntimeError("Codex app-server returned a model without an identifier.")
                display = model.get("displayName")
                label = f"{display} ({model_id})" if isinstance(display, str) and display else model_id
                efforts = model.get("supportedReasoningEfforts", [])
                values: list[str] = []
                if isinstance(efforts, list):
                    for item in efforts:
                        if isinstance(item, dict) and isinstance(item.get("reasoningEffort"), str):
                            values.append(item["reasoningEffort"])
                choices[model_id] = [label, *values]
                total += 1
                if total > MAX_MODELS:
                    raise RuntimeError("Codex returned more models than the configured safety limit.")
            cursor_value = result.get("nextCursor")
            if cursor_value is None:
                return choices
            if not isinstance(cursor_value, str) or cursor_value in seen_cursors:
                raise RuntimeError("Codex app-server returned an invalid or repeated page cursor.")
            seen_cursors.add(cursor_value)
            cursor = cursor_value
        raise RuntimeError("Codex model list exceeded the page limit.")

    def close(self) -> None:
        try:
            if self.process.stdin:
                try:
                    self.notify("shutdown")
                except (BrokenPipeError, OSError, ValueError):
                    pass
                try:
                    self.process.stdin.close()
                except (OSError, ValueError):
                    pass
        finally:
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
            if self.process.stdout:
                try:
                    self.process.stdout.close()
                except OSError:
                    pass


def copilot_models() -> dict[str, list[str]]:
    """Query models through the optional Copilot SDK's compatible runtime."""
    try:
        from copilot import CopilotClient, RuntimeConnection
    except ImportError as exc:
        raise RuntimeError("Install the optional Microsoft Copilot SDK: python -m pip install microsoft-copilot-sdk") from exc
    async def query() -> dict[str, list[str]]:
        client = CopilotClient(mode="coding-agent", runtime=RuntimeConnection.for_spawned_stdio())
        try:
            await asyncio.wait_for(client.start(), timeout=MAX_SECONDS)
            auth = await asyncio.wait_for(client.get_auth_status(), timeout=MAX_SECONDS)
            if not auth.is_authenticated:
                raise RuntimeError(
                    "Copilot is not authenticated. Install GitHub Copilot CLI and run "
                    "'copilot login' in a terminal, then restart this application and refresh. "
                    "Signing in to VS Code alone may not authenticate the SDK runtime."
                )
            models = await asyncio.wait_for(client.list_models(), timeout=MAX_SECONDS)
            if len(models) > MAX_MODELS:
                raise RuntimeError("Copilot returned more models than the configured safety limit.")
            choices = {}
            for model in models:
                model_id = model.id
                if not isinstance(model_id, str) or not model_id.strip():
                    raise RuntimeError("Copilot returned a model without an identifier.")
                name = model.name
                choices[model_id] = [f"{name} ({model_id})" if isinstance(name, str) and name else model_id]
            return choices
        finally:
            await asyncio.wait_for(client.stop(), timeout=MAX_SECONDS)

    return asyncio.run(query())


def load_templates() -> dict[str, dict[str, str]]:
    templates: dict[str, dict[str, str]] = {}
    for role in common.AGENT_NAMES:
        path = TEMPLATE_ROOT / f"getonmylevel_{role}.toml"
        text = path.read_text(encoding="utf-8")
        if not text.startswith(MARKER + "\n"):
            raise ValueError(f"Agent template is missing its management marker: {path}")
        data = tomllib.loads(text[len(MARKER) + 1 :])
        if set(data) != {"name", "description", "developer_instructions"}:
            raise ValueError(f"Agent template has unexpected fields: {path}")
        if not all(isinstance(data[key], str) for key in data):
            raise ValueError(f"Agent template fields must be strings: {path}")
        templates[role] = data
    return templates


def parse_managed_file(path: Path, expected: dict[str, str]) -> tuple[str, str]:
    if common.is_link_or_reparse(path):
        raise ValueError(f"Refusing to update linked or reparse-point file: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.startswith(MARKER + "\n"):
        raise ValueError(f"Existing file is not marked as managed by this tool: {path}")
    data = tomllib.loads(text[len(MARKER) + 1 :])
    allowed_keys = {"name", "description", "developer_instructions", "model", "model_reasoning_effort"}
    if set(data) - allowed_keys:
        raise ValueError(f"Existing file has unrecognized fields and will not be changed: {path}")
    for key, value in expected.items():
        if data.get(key) != value:
            raise ValueError(f"Existing file has been edited outside model/effort settings; refusing to replace: {path}")
    for key in ("model", "model_reasoning_effort"):
        if key in data and not isinstance(data[key], str):
            raise ValueError(f"Existing {key} must be text: {path}")
    return data.get("model", ""), data.get("model_reasoning_effort", "")


def toml_string(value: str, *, allow_controls: bool = False) -> str:
    if not allow_controls and any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("Model and reasoning effort values cannot contain control characters.")
    return json.dumps(value, ensure_ascii=False)


def render_agent(expected: dict[str, str], model: str, effort: str) -> str:
    fields = [f"{key} = {toml_string(value, allow_controls=True)}" for key, value in expected.items()]
    if model:
        fields.append(f"model = {toml_string(model)}")
    if effort:
        fields.append(f"model_reasoning_effort = {toml_string(effort)}")
    return MARKER + "\n" + "\n".join(fields) + "\n"


def _claude_yaml_string(value: str) -> str:
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("Model and effort values cannot contain control characters.")
    return json.dumps(value, ensure_ascii=False)


def render_claude_agent(expected: dict[str, str], model: str, effort: str) -> str:
    fields = [f"name: {_claude_yaml_string(expected['name'])}",
              f"description: {_claude_yaml_string(expected['description'])}"]
    if model:
        fields.append(f"model: {_claude_yaml_string(model)}")
    if effort:
        fields.append(f"effort: {_claude_yaml_string(effort)}")
    return "---\n" + "\n".join(fields) + "\n---\n" + CLAUDE_MARKER + "\n" + expected["developer_instructions"].rstrip() + "\n"


def render_copilot_agent(expected: dict[str, str], model: str, effort: str = "") -> str:
    fields = [f"name: {_claude_yaml_string(expected['name'])}",
              f"description: {_claude_yaml_string(expected['description'])}"]
    if model:
        fields.append(f"model: {_claude_yaml_string(model)}")
    return "---\n" + "\n".join(fields) + "\n---\n" + COPILOT_MARKER + "\n" + expected["developer_instructions"].rstrip() + "\n"


def claude_expected(role: str, template: dict[str, str]) -> dict[str, str]:
    return {**template, "name": f"getonmylevel-{role}"}


COPILOT_MARKER = "<!-- Managed by getonmylevel for GitHub Copilot. -->"


def agent_filename(role: str, client: str) -> str:
    if role not in common.AGENT_NAMES or client not in ("codex", "claude", "copilot"):
        raise ValueError("Unknown agent role or client.")
    if client == "copilot":
        return f"getonmylevel-{role}.agent.md"
    separator = "-" if client == "claude" else "_"
    extension = "md" if client == "claude" else "toml"
    return f"getonmylevel{separator}{role}.{extension}"


def parse_copilot_managed_file(path: Path, expected: dict[str, str]) -> tuple[str, str]:
    if common.is_link_or_reparse(path):
        raise ValueError(f"Refusing to update linked or reparse-point file: {path}")
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) < 5 or lines[0] != "---":
        raise ValueError(f"Existing file is not a Copilot agent managed by this tool: {path}")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError(f"Copilot agent frontmatter is malformed: {path}") from exc
    fields = {}
    for line in lines[1:end]:
        match = re.fullmatch(r"(name|description|model): (\"(?:[^\"\\]|\\.)*\")", line)
        if not match or match.group(1) in fields:
            raise ValueError(f"Copilot agent frontmatter has unexpected or malformed fields: {path}")
        fields[match.group(1)] = json.loads(match.group(2))
    body = "\n".join(lines[end + 1:])
    expected_body = COPILOT_MARKER + "\n" + expected["developer_instructions"].rstrip()
    if fields.get("name") != expected["name"] or fields.get("description") != expected["description"] or body != expected_body:
        raise ValueError(f"Existing file was edited outside model settings; refusing to replace: {path}")
    if set(fields) - {"name", "description", "model"}:
        raise ValueError(f"Existing file has unrecognized fields: {path}")
    return fields.get("model", ""), ""


def parse_claude_managed_file(path: Path, expected: dict[str, str]) -> tuple[str, str]:
    if common.is_link_or_reparse(path):
        raise ValueError(f"Refusing to update linked or reparse-point file: {path}")
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) < 6 or lines[0] != "---":
        raise ValueError(f"Existing file is not a Claude Code agent managed by this tool: {path}")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError(f"Claude agent frontmatter is malformed: {path}") from exc
    fields = {}
    for line in lines[1:end]:
        match = re.fullmatch(r"(name|description|model|effort): (\"(?:[^\"\\]|\\.)*\")", line)
        if not match or match.group(1) in fields:
            raise ValueError(f"Claude agent frontmatter has unexpected or malformed fields: {path}")
        fields[match.group(1)] = json.loads(match.group(2))
    body = "\n".join(lines[end + 1:])
    expected_body = CLAUDE_MARKER + "\n" + expected["developer_instructions"].rstrip()
    if fields.get("name") != expected["name"] or fields.get("description") != expected["description"] or body != expected_body:
        raise ValueError(f"Existing file was edited outside model/effort settings; refusing to replace: {path}")
    if set(fields) - {"name", "description", "model", "effort"}:
        raise ValueError(f"Existing file has unrecognized fields: {path}")
    return fields.get("model", ""), fields.get("effort", "")


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def role_plan(client: str, scope: str, repo: Path | None, roles: list[str],
              models: dict[str, str] | None = None, efforts: dict[str, str] | None = None,
              *, action: str = "install") -> list[tuple[str, Path, str | None]]:
    """Validate and plan managed agent file installs, updates, or removals."""
    if action not in ("install", "update", "remove"):
        raise ValueError(f"Unknown role action: {action}")
    roles = common.validate_selection(roles, common.AGENT_NAMES, "agent role")
    if not roles:
        raise ValueError("Select at least one agent role.")
    roots = common.agent_roots(scope, repo, client)
    if repo is not None and common.canonical(repo) == REPO_ROOT.resolve():
        raise ValueError("The target repository must differ from this source checkout.")
    templates = load_templates()
    planned: list[tuple[str, Path, str | None]] = []
    models, efforts = models or {}, efforts or {}
    for root in roots:
        common.check_managed_root(root)
        for role in roles:
            path = root / agent_filename(role, client)
            if common.is_link_or_reparse(path):
                raise ValueError(f"Refusing linked or reparse-point destination path: {path}")
            expected = claude_expected(role, templates[role]) if client in ("claude", "copilot") else templates[role]
            parser = {"claude": parse_claude_managed_file, "copilot": parse_copilot_managed_file}.get(client, parse_managed_file)
            existing_model, existing_effort = ("", "")
            if path.exists():
                existing_model, existing_effort = parser(path, expected)
            if action == "remove":
                if not path.exists():
                    raise FileNotFoundError(f"Managed role file is not installed: {path}")
                planned.append((role, path, None))
                continue
            model = models.get(role, existing_model).strip()
            effort = efforts.get(role, existing_effort).strip()
            if client == "copilot" and effort:
                raise ValueError(f"GitHub Copilot does not support reasoning effort for {role}.")
            renderer = {"claude": render_claude_agent, "copilot": render_copilot_agent}.get(client, render_agent)
            planned.append((role, path, renderer(expected, model, effort)))
    return planned


def perform_role_plan(plan: list[tuple[str, Path, str | None]], client: str, action: str) -> tuple[list[str], list[str]]:
    """Apply a role plan, returning completed paths and backup paths (currently none)."""
    completed: list[str] = []
    templates = load_templates()
    parsers = {"claude": parse_claude_managed_file, "copilot": parse_copilot_managed_file}
    try:
        for role, path, content in plan:
            common.check_managed_root(path.parent)
            if common.is_link_or_reparse(path):
                raise ValueError(f"Refusing linked or reparse-point destination path: {path}")
            expected = claude_expected(role, templates[role]) if client in ("claude", "copilot") else templates[role]
            parser = parsers.get(client, parse_managed_file)
            if action == "remove":
                if not path.exists():
                    raise FileNotFoundError(f"Managed role file disappeared before removal: {path}")
                parser(path, expected)
                path.unlink()
            else:
                if path.exists():
                    parser(path, expected)
                if content is None:
                    raise ValueError(f"No content was planned for {path}")
                write_atomic(path, content)
            completed.append(str(path))
    except (OSError, ValueError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        if completed:
            raise RuntimeError(f"{exc}\nCompleted before failure:\n" + "\n".join(completed) + "\nThe operation is not transactional; those changes remain.") from exc
        raise
    return completed, []

