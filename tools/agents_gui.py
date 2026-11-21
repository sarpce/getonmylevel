"""Configure optional getonmylevel Codex agent TOMLs with explicit approval."""

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
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("getonmylevel agent configuration")
        root.geometry("980x790")
        root.minsize(760, 620)
        self.templates = load_templates()
        self.model_choices: dict[str, list[str]] = {}
        self.refresh_queue: queue.Queue[tuple[bool, Any]] = queue.Queue()
        self.scope_conflicts: dict[str, list[tuple[str, str]]] = {}

        outer = ttk.Frame(root, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Optional Codex agent roles", font=("TkDefaultFont", 16, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Configure only selected role files. Existing getonmylevel-managed model/effort values are loaded for editing.", wraplength=920).pack(anchor="w", pady=(4, 10))

        selector_row = ttk.Frame(outer)
        selector_row.pack(fill="x", pady=(0, 8))
        ttk.Label(selector_row, text="Skill session preference:").pack(side="left")
        self.preference = tk.StringVar(value="Ask")
        ttk.Combobox(selector_row, textvariable=self.preference, values=("On", "Off", "Ask"), state="readonly", width=8).pack(side="left", padx=8)
        ttk.Button(selector_row, text="Copy session instruction block", command=self.copy_selector).pack(side="left")
        ttk.Label(selector_row, text="Copy only; this tool does not edit global instructions.").pack(side="left", padx=8)

        scope_row = ttk.Frame(outer)
        scope_row.pack(fill="x")
        ttk.Label(scope_row, text="Scope:").pack(side="left")
        self.scope = tk.StringVar(value="global")
        for label, value in (("Global user", "global"), ("Repository", "repo"), ("Both", "both")):
            ttk.Radiobutton(scope_row, text=label, value=value, variable=self.scope, command=self.scope_changed).pack(side="left", padx=6)
        self.repo_path = tk.StringVar()
        ttk.Entry(outer, textvariable=self.repo_path).pack(fill="x", pady=(6, 4))
        ttk.Button(outer, text="Choose target repository…", command=self.browse_repo).pack(anchor="e")

        row = ttk.Frame(outer)
        row.pack(fill="x", pady=(10, 4))
        ttk.Label(row, text="Role", width=18).pack(side="left")
        ttk.Label(row, text="Model (blank inherits Codex default)", width=38).pack(side="left")
        ttk.Label(row, text="Reasoning effort", width=20).pack(side="left")
        self.enabled: dict[str, tk.BooleanVar] = {}
        self.model_vars: dict[str, tk.StringVar] = {}
        self.effort_vars: dict[str, tk.StringVar] = {}
        self.model_widgets: dict[str, ttk.Combobox] = {}
        self.effort_widgets: dict[str, ttk.Combobox] = {}
        for role in common.AGENT_NAMES:
            role_row = ttk.Frame(outer)
            role_row.pack(fill="x", pady=3)
            self.enabled[role] = tk.BooleanVar(value=False)
            self.model_vars[role] = tk.StringVar()
            self.effort_vars[role] = tk.StringVar()
            ttk.Checkbutton(role_row, text=role.title(), variable=self.enabled[role], command=self.refresh_preview, width=16).pack(side="left")
            model = ttk.Combobox(role_row, textvariable=self.model_vars[role], values=("",), width=42)
            model.pack(side="left", fill="x", expand=True, padx=(0, 8))
            model.bind("<<ComboboxSelected>>", lambda _event, selected_role=role: self.model_changed(selected_role))
            model.bind("<FocusOut>", lambda _event, selected_role=role: self.refresh_preview())
            self.model_widgets[role] = model
            effort = ttk.Combobox(role_row, textvariable=self.effort_vars[role], values=("",), width=18)
            effort.pack(side="left")
            effort.bind("<<ComboboxSelected>>", lambda _event: self.refresh_preview())
            effort.bind("<FocusOut>", lambda _event: self.refresh_preview())
            self.effort_widgets[role] = effort

        control_row = ttk.Frame(outer)
        control_row.pack(fill="x", pady=8)
        self.refresh_button = ttk.Button(control_row, text="Refresh available models from Codex...", command=self.refresh_models)
        self.refresh_button.pack(side="left")
        self.refresh_status = tk.StringVar(value="Model discovery is optional. You can enter values manually.")
        ttk.Label(control_row, textvariable=self.refresh_status, wraplength=620).pack(side="left", padx=10)

        ttk.Label(outer, text="Preview").pack(anchor="w", pady=(4, 4))
        self.preview = tk.Text(outer, height=12, wrap="word", state="disabled")
        self.preview.pack(fill="both", expand=True)
        button_row = ttk.Frame(outer)
        button_row.pack(fill="x", pady=(10, 0))
        ttk.Button(button_row, text="Write selected agent files…", command=self.write_selected).pack(side="right")
        ttk.Button(button_row, text="Close", command=root.destroy).pack(side="right", padx=(0, 8))
        self.scope_changed()
        self.poll_refresh()

    def browse_repo(self) -> None:
        chosen = filedialog.askdirectory(title="Choose an existing target repository")
        if chosen:
            self.repo_path.set(chosen)
            self.scope_changed()

    def selected_roots(self) -> list[Path]:
        if self.scope.get() in ("repo", "both") and not self.repo_path.get().strip():
            raise ValueError("Choose an existing target repository for repository scope.")
        repo = Path(self.repo_path.get()).expanduser() if self.scope.get() in ("repo", "both") else None
        roots = common.agent_roots(self.scope.get(), repo)
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
        block += "\n\nIndependently, on the first anticipated software-change request in a session, offer Simple or Agent-based unless already chosen, even when getonmylevel skills are Off. In Agent-based mode, offer independent Yes/No choices for reviewer and tester unless session instructions already supply them. Wait for the answers. Follow existing session and repository policy; this block cannot override higher-priority instructions or guarantee activation."
        block += "\n\nFor these questions, wait for the user's actual response before dependent work. Use a choice interface only if the client can deliver its response. For an asynchronous prompt, keep the turn active and wait if supported; do not finish the turn while the response is pending. A default, timeout, or elapsed time is not an answer. If the CLI or other client cannot wait for or deliver the response, ask in chat and end the turn with the question pending; resume dependent work after the user responds."
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
                path = root / f"getonmylevel_{role}.toml"
                if common.is_link_or_reparse(path):
                    raise ValueError(f"Refusing to update symlink: {path}")
                model = self.model_vars[role].get().strip()
                effort = self.effort_vars[role].get().strip()
                if path.exists():
                    parse_managed_file(path, templates[role])
                entries.append((role, path, render_agent(templates[role], model, effort)))
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
                    path = root / f"getonmylevel_{role}.toml"
                    if path.exists() and not path.is_symlink():
                        candidates.append(parse_managed_file(path, self.templates[role]))
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

    def refresh_models(self) -> None:
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
            lines.extend(f"  {root / f'getonmylevel_{role}.toml'}" for root in roots for role in roles)
            if roles:
                lines.append("\nModel and effort (blank means inherit Codex defaults):")
                lines.extend(f"  {role}: model={self.model_vars[role].get() or '(inherit)'}, effort={self.effort_vars[role].get() or '(inherit)'}" for role in roles)
            lines.append("\nExisting files are updated only when their marker and template text match exactly. No AGENTS.md or Codex config is edited.")
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
                    parse_managed_file(path, templates[_role])
                write_atomic(path, content)
                written.append(str(path))
            messagebox.showinfo("Configuration complete", "Written:\n" + "\n".join(written))
        except (OSError, ValueError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            details = ""
            if written:
                details = "\n\nThese files were already written before the error:\n" + "\n".join(written)
            messagebox.showerror("Configuration stopped", f"{exc}{details}\n\nEach file replacement is atomic, but the full set is not transactional.")


def main() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"Tkinter could not open a window ({exc}). Use the terminal or edit the TOML templates manually ({TEMPLATE_ROOT}).")
        return
    try:
        AgentConfigurator(root)
    except (OSError, ValueError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        messagebox.showerror("Unable to load agent templates", str(exc))
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
