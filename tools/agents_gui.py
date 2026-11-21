"""Configure optional getonmylevel Codex agents or Claude Code subagents."""

from __future__ import annotations

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
try:
    import tkinter as tk
    import tomllib
    from tkinter import filedialog, messagebox, ttk
except ImportError as exc:
    print(f"Tkinter or tomllib is unavailable ({exc}). Use the terminal instructions in README.md or edit the TOML templates manually.")
    raise SystemExit(0)
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


def claude_expected(role: str, template: dict[str, str]) -> dict[str, str]:
    return {**template, "name": f"getonmylevel-{role}"}


def agent_filename(role: str, client: str) -> str:
    if role not in common.AGENT_NAMES or client not in ("codex", "claude"):
        raise ValueError("Unknown agent role or client.")
    separator = "-" if client == "claude" else "_"
    extension = "md" if client == "claude" else "toml"
    return f"getonmylevel{separator}{role}.{extension}"


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


class AgentConfigurator:
    def __init__(self, root: tk.Tk, parent=None, close_command=None, configure_window: bool = True) -> None:
        self.root = root
        if configure_window:
            root.title("getonmylevel · Skills and agents")
            root.geometry("1000x780")
            root.minsize(760, 620)
        self.templates = load_templates()
        self.client = tk.StringVar(value="codex")
        self.client_values = {"codex": {}, "claude": {}}
        self.model_choices: dict[str, list[str]] = {}
        self.refresh_queue: queue.Queue[tuple[bool, Any]] = queue.Queue()
        self.scope_conflicts: dict[str, list[tuple[str, str]]] = {}

        outer = ttk.Frame(parent or root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Agent roles", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        self.intro_label = ttk.Label(outer, text="Add focused helpers to Codex. Choose a role, then set its model and reasoning effort.",
                                     style="Muted.TLabel", wraplength=900)
        self.intro_label.pack(anchor="w", pady=(5, 16))

        client_row = ttk.Frame(outer)
        client_row.pack(fill="x", pady=(0, 8))
        ttk.Label(client_row, text="Client:").pack(side="left")
        for label, value in (("Codex", "codex"), ("Claude Code", "claude")):
            ttk.Radiobutton(client_row, text=label, value=value, variable=self.client,
                            command=self.client_changed).pack(side="left", padx=6)

        selector_row = ttk.Frame(outer)
        selector_row.pack(fill="x", pady=(0, 8))
        ttk.Label(selector_row, text="Skill session preference:").pack(side="left")
        self.preference = tk.StringVar(value="Ask")
        ttk.Combobox(selector_row, textvariable=self.preference, values=("On", "Off", "Ask"), state="readonly", width=8).pack(side="left", padx=8)
        ttk.Button(selector_row, text="Copy session instruction block", command=self.copy_selector).pack(side="left")
        ttk.Label(outer, text="Copies a block to the clipboard; global instructions are left unchanged.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 8))

        scope_row = ttk.Frame(outer)
        scope_row.pack(fill="x")
        ttk.Label(scope_row, text="Scope:").pack(side="left")
        self.scope = tk.StringVar(value="global")
        for label, value in (("Global user", "global"), ("Repository", "repo"), ("Both", "both")):
            ttk.Radiobutton(scope_row, text=label, value=value, variable=self.scope, command=self.scope_changed).pack(side="left", padx=6)
        self.repo_path = tk.StringVar()
        repo_row = ttk.Frame(outer)
        repo_row.pack(fill="x", pady=(8, 0))
        ttk.Entry(repo_row, textvariable=self.repo_path).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(repo_row, text="Browse…", command=self.browse_repo).pack(side="left")

        ttk.Label(outer, text="Available roles", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(16, 8))
        self.role_grid = ttk.Frame(outer)
        self.role_grid.pack(fill="x")
        self.enabled: dict[str, tk.BooleanVar] = {}
        self.model_vars: dict[str, tk.StringVar] = {}
        self.effort_vars: dict[str, tk.StringVar] = {}
        self.model_widgets: dict[str, ttk.Combobox] = {}
        self.effort_widgets: dict[str, ttk.Combobox] = {}
        self.role_cards = {}
        self.role_card_bodies = {}
        self.role_card_title_rows = {}
        self.role_card_markers = {}
        self.role_card_checks = {}
        self.role_card_descriptions = {}
        for role in common.AGENT_NAMES:
            card = tk.Frame(self.role_grid, background="#FFFFFF", highlightthickness=1,
                            highlightbackground="#D4D4D8", highlightcolor="#059669")
            body = ttk.Frame(card, style="Card.TFrame", padding=12)
            body.pack(fill="both", expand=True)
            self.enabled[role] = tk.BooleanVar(value=False)
            self.model_vars[role] = tk.StringVar()
            self.effort_vars[role] = tk.StringVar()
            title_row = ttk.Frame(body, style="Card.TFrame")
            title_row.pack(fill="x")
            marker = ttk.Label(title_row, text="○", style="CardMarker.TLabel", width=2, anchor="center")
            marker.pack(side="left", padx=(0, 4))
            check = ttk.Checkbutton(title_row, text=role.title(), variable=self.enabled[role], command=self.refresh_preview,
                                    style="Card.TCheckbutton")
            check.pack(side="left", anchor="w", fill="x", expand=True)
            description = ttk.Label(body, text=self.templates[role]["description"], style="CardMuted.TLabel",
                                    wraplength=280, justify="left")
            description.pack(anchor="w", fill="x", pady=(4, 10))
            ttk.Label(body, text="Model · blank uses client default", style="CardMuted.TLabel").pack(anchor="w")
            model = ttk.Combobox(body, textvariable=self.model_vars[role], values=("",), width=24)
            model.pack(fill="x", pady=(3, 8))
            model.bind("<<ComboboxSelected>>", lambda _event, selected_role=role: self.model_changed(selected_role))
            model.bind("<FocusOut>", lambda _event, selected_role=role: self.refresh_preview())
            self.model_widgets[role] = model
            ttk.Label(body, text="Effort · blank uses default", style="CardMuted.TLabel").pack(anchor="w")
            effort = ttk.Combobox(body, textvariable=self.effort_vars[role], values=("",), width=14)
            effort.pack(anchor="w", fill="x", pady=(3, 0))
            effort.bind("<<ComboboxSelected>>", lambda _event: self.refresh_preview())
            effort.bind("<FocusOut>", lambda _event: self.refresh_preview())
            self.effort_widgets[role] = effort
            self.role_cards[role] = card
            self.role_card_bodies[role] = body
            self.role_card_title_rows[role] = title_row
            self.role_card_markers[role] = marker
            self.role_card_checks[role] = check
            self.role_card_descriptions[role] = description
            self.enabled[role].trace_add("write", lambda *_args, selected_role=role: self.update_role_card(selected_role))
            self.update_role_card(role)
        self.role_grid.bind("<Configure>", self.reflow_role_cards)

        control_row = ttk.Frame(outer)
        control_row.pack(fill="x", pady=8)
        self.refresh_button = ttk.Button(control_row, text="Refresh available models from Codex...", command=self.refresh_models)
        self.refresh_button.pack(anchor="w")
        self.refresh_status = tk.StringVar(value="Model discovery is optional. You can enter values manually.")
        ttk.Label(control_row, textvariable=self.refresh_status, style="Muted.TLabel", wraplength=620).pack(anchor="w", pady=(5, 0))

        ttk.Label(outer, text="Preview").pack(anchor="w", pady=(4, 4))
        self.preview = tk.Text(outer, height=12, wrap="word", state="disabled", borderwidth=1,
                               highlightthickness=1, highlightbackground="#D4D4D8", highlightcolor="#059669",
                               padx=10, pady=8)
        self.preview.pack(fill="both", expand=True)
        button_row = ttk.Frame(outer)
        button_row.pack(fill="x", pady=(10, 0))
        ttk.Button(button_row, text="Write selected agent files…", command=self.write_selected,
                   style="Primary.TButton").pack(side="right")
        ttk.Button(button_row, text="Close", command=close_command or root.destroy).pack(side="right", padx=(0, 8))
        self.scope_changed()
        self.poll_refresh()
        outer.bind("<Configure>", self.fit_page_copy)

    def fit_page_copy(self, event) -> None:
        self.intro_label.configure(wraplength=max(240, event.width - 36))

    def update_role_card(self, role: str) -> None:
        selected = self.enabled[role].get()
        self.role_cards[role].configure(highlightbackground="#D4D4D8")
        self.role_card_bodies[role].configure(style="Selected.Card.TFrame" if selected else "Card.TFrame")
        self.role_card_title_rows[role].configure(style="Selected.Card.TFrame" if selected else "Card.TFrame")
        self.role_card_descriptions[role].configure(style="Selected.CardMuted.TLabel" if selected else "CardMuted.TLabel")
        self.role_card_markers[role].configure(text="✓" if selected else "○",
                                               style="Selected.CardMarker.TLabel" if selected else "CardMarker.TLabel")
        self.role_card_checks[role].configure(style="Selected.Card.TCheckbutton" if selected else "Card.TCheckbutton")

    def reflow_role_cards(self, event=None) -> None:
        width = event.width if event is not None else self.role_grid.winfo_width()
        columns = 2 if width >= 500 else 1
        for card in self.role_cards.values():
            card.grid_forget()
        for column in range(2):
            self.role_grid.columnconfigure(column, weight=0, minsize=0, uniform="")
        for column in range(columns):
            self.role_grid.columnconfigure(column, weight=1, uniform="role-card")
        for index, role in enumerate(self.role_cards):
            card = self.role_cards[role]
            card.grid(row=index // columns, column=index % columns, sticky="nsew",
                      padx=(0 if index % columns == 0 else 6, 6 if index % columns < columns - 1 else 0),
                      pady=(0, 12))
            card_width = max(220, (width - 12 * (columns - 1)) // columns)
            self.role_card_descriptions[role].configure(wraplength=max(190, card_width - 36))

    def browse_repo(self) -> None:
        chosen = filedialog.askdirectory(title="Choose an existing target repository")
        if chosen:
            self.repo_path.set(chosen)
            self.scope_changed()

    def selected_roots(self) -> list[Path]:
        if self.scope.get() in ("repo", "both") and not self.repo_path.get().strip():
            raise ValueError("Choose an existing target repository for repository scope.")
        repo = Path(self.repo_path.get()).expanduser() if self.scope.get() in ("repo", "both") else None
        roots = common.agent_roots(self.scope.get(), repo, self.client.get())
        if repo is not None and common.canonical(repo) == REPO_ROOT.resolve():
            raise ValueError("The target repository must differ from this source checkout.")
        return roots

    def selected_roles(self) -> list[str]:
        return [role for role in common.AGENT_NAMES if self.enabled[role].get()]

    def copy_selector(self) -> None:
        preference = self.preference.get()
        block = {
            "On": "For this session, use all installed getonmylevel skills unless the user explicitly selects a different set.",
            "Off": "For this session, use no getonmylevel skills unless the user explicitly selects one or more.",
            "Ask": "At the start of each interactive conversation, unless the user already specifies a selection, offer All installed getonmylevel skills, Select individually, or None. Wait for the selection before dependent work. Honor explicit selections and later changes. In unattended runs, do not prompt; use an explicit selection or none.",
        }[preference]
        block += " Honor user changes to the preference or selection at any point in the conversation."
        block += "\n\nProceed directly with straightforward software changes without an up-front workflow choice. Use agent-based work when explicitly requested or useful under the active session's delegation rules. Preserve user control over independent review and testing: ask separately when relevant, and keep each disabled unless selected. Wait for actual answers before dependent work. Respect higher-priority instructions."
        block += "\n\nFor the skill-selection choice, use a choice interface when it can deliver the answer and wait for the user's actual response before dependent work. For independent review or testing, use a choice interface when available and wait for each actual answer. Never treat a preselected option, timeout, or elapsed time as an answer. If no usable popup exists, ask in chat and leave dependent work pending until the user responds. This block cannot override higher-priority instructions or guarantee activation."
        self.root.clipboard_clear()
        self.root.clipboard_append(block)
        messagebox.showinfo("Copied", "Session instruction block copied to the clipboard. It was not added to any global file.")

    def plan(self) -> tuple[list[str], list[Path], dict[str, dict[str, str]], list[tuple[str, Path, str]]]:
        roles = common.validate_selection(self.selected_roles(), common.AGENT_NAMES, "agent role")
        roots = self.selected_roots()
        templates = self.templates
        entries: list[tuple[str, Path, str]] = []
        for root in roots:
            common.check_managed_root(root)
            for role in roles:
                path = root / agent_filename(role, self.client.get())
                if common.is_link_or_reparse(path):
                    raise ValueError(f"Refusing to update symlink: {path}")
                model = self.model_vars[role].get().strip()
                effort = self.effort_vars[role].get().strip()
                expected = claude_expected(role, templates[role]) if self.client.get() == "claude" else templates[role]
                if path.exists():
                    (parse_claude_managed_file if self.client.get() == "claude" else parse_managed_file)(path, expected)
                renderer = render_claude_agent if self.client.get() == "claude" else render_agent
                entries.append((role, path, renderer(expected, model, effort)))
        return roles, roots, templates, entries

    def scope_changed(self) -> None:
        self.load_existing_values()
        self.refresh_preview()

    def load_existing_values(self) -> None:
        try:
            roots = self.selected_roots()
            self.scope_conflicts = {}
            for role in common.AGENT_NAMES:
                candidates = []
                for root in roots:
                    path = root / agent_filename(role, self.client.get())
                    if path.exists() and not path.is_symlink():
                        parser = parse_claude_managed_file if self.client.get() == "claude" else parse_managed_file
                        expected = claude_expected(role, self.templates[role]) if self.client.get() == "claude" else self.templates[role]
                        candidates.append(parser(path, expected))
                if candidates and len(set(candidates)) == 1:
                    model, effort = candidates[0]
                    self.model_vars[role].set(model)
                    self.effort_vars[role].set(effort)
                elif candidates:
                    self.scope_conflicts[role] = candidates
        except (OSError, ValueError, tomllib.TOMLDecodeError):
            # Preview displays the issue. Do not change values on a failed read.
            pass

    def model_changed(self, role: str) -> None:
        if self.client.get() == "claude":
            self.effort_widgets[role]["values"] = CLAUDE_EFFORTS
            self.refresh_preview()
            return
        model_text = self.model_vars[role].get()
        selected_id = None
        for model_id, values in self.model_choices.items():
            if model_text == model_id or model_text == values[0]:
                selected_id = model_id
                break
        if selected_id is not None:
            self.model_vars[role].set(selected_id)
            efforts = [""] + self.model_choices[selected_id][1:]
            self.effort_widgets[role]["values"] = efforts
            if self.effort_vars[role].get() not in efforts:
                self.effort_vars[role].set("")
        self.refresh_preview()

    def client_changed(self) -> None:
        previous = "claude" if self.client.get() == "codex" else "codex"
        for role in common.AGENT_NAMES:
            self.client_values[previous][role] = (self.model_vars[role].get(), self.effort_vars[role].get())
        claude = self.client.get() == "claude"
        self.intro_label.configure(text="Add focused helpers to Claude Code. Set each role’s model and effort, or leave them blank to inherit defaults." if claude else "Add focused helpers to Codex. Choose a role, then set its model and reasoning effort.")
        self.refresh_button.configure(text="Claude Code models are entered manually" if claude else "Refresh available models from Codex...")
        self.refresh_button.configure(state="disabled" if claude else "normal")
        self.refresh_status.set("Claude Code has no local model discovery here. Suggested aliases are shown; enter any model ID supported by your account." if claude else "Model discovery is optional. You can enter values manually.")
        for role in common.AGENT_NAMES:
            model, effort = self.client_values[self.client.get()].get(role, ("", ""))
            self.model_vars[role].set(model)
            self.effort_vars[role].set(effort)
            if claude:
                self.model_widgets[role]["values"] = CLAUDE_MODELS
                self.effort_widgets[role]["values"] = CLAUDE_EFFORTS
            else:
                self.model_widgets[role]["values"] = [""] + [details[0] for details in self.model_choices.values()]
                self.effort_widgets[role]["values"] = [""] + list(dict.fromkeys(e for values in self.model_choices.values() for e in values[1:]))
        self.scope_changed()

    def refresh_models(self) -> None:
        if self.client.get() == "claude":
            return
        self.refresh_button.configure(state="disabled")
        self.refresh_status.set("Querying the local Codex app-server…")
        def worker() -> None:
            server = None
            try:
                server = AppServer()
                models = server.models()
                self.refresh_queue.put((True, models))
            except Exception as exc:
                self.refresh_queue.put((False, str(exc)))
            finally:
                if server is not None:
                    server.close()

        threading.Thread(target=worker, daemon=True).start()

    def poll_refresh(self) -> None:
        try:
            ok, value = self.refresh_queue.get_nowait()
        except queue.Empty:
            self.root.after(150, self.poll_refresh)
            return
        if ok:
            self.model_choices = value
            labels = [""] + [details[0] for details in value.values()]
            for role in common.AGENT_NAMES:
                self.model_widgets[role]["values"] = labels
            self.refresh_status.set(f"Loaded {len(value)} models. Discovery does not guarantee access or entitlement.")
        else:
            self.refresh_status.set("Model discovery unavailable; manual entry remains available.")
            messagebox.showwarning("Model discovery unavailable", f"{value}\n\nEnter model and effort values manually. A listed model does not guarantee access or entitlement.")
        self.refresh_button.configure(state="normal")
        self.refresh_preview()
        self.root.after(150, self.poll_refresh)

    def refresh_preview(self) -> None:
        try:
            roles = self.selected_roles()
            roots = self.selected_roots()
            lines = [f"Selected roles: {', '.join(roles) if roles else '(none selected)'}", "Destinations:"]
            lines.extend(f"  {root / agent_filename(role, self.client.get())}" for root in roots for role in roles)
            if roles:
                lines.append("\nModel and effort (blank means inherit client defaults):")
                lines.extend(f"  {role}: model={self.model_vars[role].get() or '(inherit)'}, effort={self.effort_vars[role].get() or '(inherit)'}" for role in roles)
            lines.append("\nExisting files are updated only when their marker and template text match exactly. No instruction file or client config is edited.")
            for role in roles:
                if role in self.scope_conflicts:
                    lines.append(f"Warning: existing values differ for {role}: {self.scope_conflicts[role]!r}. Choose values explicitly to unify them.")
        except (OSError, ValueError) as exc:
            lines = [f"Cannot prepare destinations: {exc}"]
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", "\n".join(lines))
        self.preview.configure(state="disabled")

    def write_selected(self) -> None:
        written: list[str] = []
        try:
            roles, roots, templates, entries = self.plan()
            preview = "\n".join(str(path) for _, path, _ in entries)
            if not messagebox.askyesno("Confirm configuration", "Write these files?\n\n" + preview):
                return
            for _role, path, content in entries:
                common.check_managed_root(path.parent)
                if common.is_link_or_reparse(path):
                    raise ValueError(f"Refusing linked or reparse-point destination path: {path}")
                if path.exists():
                    expected = claude_expected(_role, templates[_role]) if self.client.get() == "claude" else templates[_role]
                    (parse_claude_managed_file if self.client.get() == "claude" else parse_managed_file)(path, expected)
                write_atomic(path, content)
                written.append(str(path))
            messagebox.showinfo("Configuration complete", "Written:\n" + "\n".join(written))
        except (OSError, ValueError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            details = ""
            if written:
                details = "\n\nThese files were already written before the error:\n" + "\n".join(written)
            messagebox.showerror("Configuration stopped", f"{exc}{details}\n\nEach file replacement is atomic, but the full set is not transactional.")


def main() -> None:
    from gui import main as launch
    launch()


if __name__ == "__main__":
    main()
