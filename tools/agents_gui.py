"""Configure optional getonmylevel roles for Codex, Claude Code, and GitHub Copilot."""

from __future__ import annotations

import json
import asyncio
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


from agent_operations import (
    CLAUDE_EFFORTS, CLAUDE_MODELS, REPO_ROOT, AppServer, agent_filename,
    claude_expected, copilot_models, load_templates, parse_claude_managed_file,
    parse_copilot_managed_file, parse_managed_file, perform_role_plan, role_plan,
    render_copilot_agent,
)


class AgentConfigurator:
    def __init__(self, root: tk.Tk, parent=None, close_command=None, configure_window: bool = True) -> None:
        self.root = root
        if configure_window:
            root.title("getonmylevel · Skills and agents")
            root.geometry("1000x780")
            root.minsize(760, 620)
        self.templates = load_templates()
        self.client = tk.StringVar(value="codex")
        self.client_values = {"codex": {}, "claude": {}, "copilot": {}}
        self.dirty_fields: dict[str, set[tuple[str, str]]] = {"codex": set(), "claude": set(), "copilot": set()}
        self.previous_client = "codex"
        self.model_choices: dict[str, dict[str, list[str]]] = {"codex": {}, "copilot": {}}
        self.refresh_queue: queue.Queue[tuple[str, bool, Any]] = queue.Queue()
        self.refreshing = False
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
        for label, value in (("Codex", "codex"), ("Claude Code", "claude"), ("GitHub Copilot", "copilot")):
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
        self.model_labels: dict[str, ttk.Label] = {}
        self.effort_labels: dict[str, ttk.Label] = {}
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
            model_label = ttk.Label(body, text="Model · blank uses client default", style="CardMuted.TLabel")
            model_label.pack(anchor="w")
            self.model_labels[role] = model_label
            model = ttk.Combobox(body, textvariable=self.model_vars[role], values=("",), width=24)
            model.pack(fill="x", pady=(3, 8))
            model.bind("<<ComboboxSelected>>", lambda _event, selected_role=role: self.model_changed(selected_role))
            model.bind("<KeyRelease>", lambda _event, selected_role=role: self.mark_field_dirty(selected_role, "model"))
            model.bind("<FocusOut>", lambda _event, selected_role=role: self.refresh_preview())
            self.model_widgets[role] = model
            effort_label = ttk.Label(body, text="Effort · blank uses default", style="CardMuted.TLabel")
            effort_label.pack(anchor="w")
            self.effort_labels[role] = effort_label
            effort = ttk.Combobox(body, textvariable=self.effort_vars[role], values=("",), width=14)
            effort.pack(anchor="w", fill="x", pady=(3, 0))
            effort.bind("<<ComboboxSelected>>", lambda _event, selected_role=role: self.effort_changed(selected_role))
            effort.bind("<KeyRelease>", lambda _event, selected_role=role: self.mark_field_dirty(selected_role, "effort"))
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
        block += "\n\nFor every new request involving any software or code edit, always prompt the user to choose Simple or Agentic mode before editing or delegating, regardless of size or a choice made for an earlier request. Read-only investigation may continue while the answer is pending. Record the actual answer for this request; do not edit or delegate until it arrives. Simple means working directly. Agentic mode uses only the installed getonmylevel agent roles configured for the active client: getonmylevel_designer and getonmylevel_implementer, plus getonmylevel_reviewer and getonmylevel_tester only when the user opts into those roles. Claude Code uses the corresponding hyphenated names. Set each spawned agent's type to its installed getonmylevel role. A task-specific spawn name or identifier may be chosen freely; it does not change the required agent type. If a required configured role is unavailable, explain which role is missing and ask the user how to proceed. In Agentic mode, ask separately whether the user wants an independent reviewer and an independent tester; each is disabled unless selected. Wait for the actual answer to every choice before assigning roles or doing dependent work. A preselected option, default, timeout, or elapsed time is not an answer. Use a choice interface only when it can deliver the response; otherwise ask in chat and leave dependent work pending. If Agentic mode is unavailable or disallowed, explain why and do not silently switch modes; ask the user how to proceed. Respect higher-priority instructions. This block cannot override higher-priority instructions or guarantee activation."
        self.root.clipboard_clear()
        self.root.clipboard_append(block)
        messagebox.showinfo("Copied", "Session instruction block copied to the clipboard. It was not added to any global file.")

    def plan(self) -> tuple[list[str], list[Path], dict[str, dict[str, str]], list[tuple[str, Path, str]]]:
        roles = self.selected_roles()
        roots = self.selected_roots()
        repo = Path(self.repo_path.get()).expanduser() if self.scope.get() in ("repo", "both") else None
        if self.client.get() == "claude":
            dirty = self.dirty_fields["claude"]
            models = {role: self.model_vars[role].get() for role in roles if (role, "model") in dirty}
            efforts = {role: self.effort_vars[role].get() for role in roles if (role, "effort") in dirty}
        else:
            # Keep the established Codex and Copilot form semantics unchanged.
            models = {role: self.model_vars[role].get() for role in roles}
            efforts = {role: self.effort_vars[role].get() for role in roles}
        planned = role_plan(self.client.get(), self.scope.get(), repo, roles, models, efforts)
        entries = planned
        return roles, roots, self.templates, entries

    def mark_field_dirty(self, role: str, field: str) -> None:
        self.dirty_fields[self.client.get()].add((role, field))

    def effort_changed(self, role: str) -> None:
        self.mark_field_dirty(role, "effort")
        self.refresh_preview()

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
                        parser = {"claude": parse_claude_managed_file, "copilot": parse_copilot_managed_file}.get(self.client.get(), parse_managed_file)
                        expected = claude_expected(role, self.templates[role]) if self.client.get() in ("claude", "copilot") else self.templates[role]
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
            self.mark_field_dirty(role, "model")
            self.effort_widgets[role]["values"] = CLAUDE_EFFORTS
            self.refresh_preview()
            return
        model_text = self.model_vars[role].get()
        selected_id = None
        choices = self.model_choices[self.client.get()]
        for model_id, values in choices.items():
            if model_text == model_id or model_text == values[0]:
                selected_id = model_id
                break
        if selected_id is not None:
            self.model_vars[role].set(selected_id)
            efforts = [""] + choices[selected_id][1:]
            self.effort_widgets[role]["values"] = efforts
            if self.effort_vars[role].get() not in efforts:
                self.effort_vars[role].set("")
        self.refresh_preview()

    def client_changed(self) -> None:
        previous = self.previous_client
        for role in common.AGENT_NAMES:
            self.client_values[previous][role] = (self.model_vars[role].get(), self.effort_vars[role].get())
        client = self.client.get()
        claude = client == "claude"
        copilot = client == "copilot"
        if claude:
            intro = "Add focused helpers to Claude Code. Set each role's model and effort independently."
            status = ("Aliases and Claude API IDs are suggestions, not an availability check; enter any supported model ID. Blank model omits the field; "
                      "inherit explicitly uses the spawning conversation's model. Blank effort omits the field and follows Claude Code's runtime resolution. "
                      "Effort support varies by model and may be capped or lowered by Claude Code.")
        elif copilot:
            intro = "Add custom agents for GitHub Copilot CLI and VS Code. Set a model or leave it blank to inherit the default."
            status = "Model discovery is optional. You can enter values manually; reasoning effort is not available."
        else:
            intro = "Add focused helpers to Codex. Choose a role, then set its model and reasoning effort."
            status = "Model discovery is optional. You can enter values manually."
        self.intro_label.configure(text=intro)
        self.refresh_button.configure(text="Built-in suggestions; manual entry available" if claude else f"Refresh available models from {'Copilot' if copilot else 'Codex'}...")
        self.refresh_button.configure(state="disabled" if claude or self.refreshing else "normal")
        self.refresh_status.set(status)
        for role in common.AGENT_NAMES:
            model, effort = self.client_values[client].get(role, ("", ""))
            self.model_vars[role].set(model)
            self.effort_vars[role].set("" if copilot else effort)
            if claude:
                self.model_labels[role].configure(text="Model · blank omits; inherit uses parent model")
                self.effort_labels[role].configure(text="Effort · blank omits; Claude resolves at runtime")
            elif copilot:
                self.model_labels[role].configure(text="Model · blank uses client default")
                self.effort_labels[role].configure(text="Effort · not supported")
            else:
                self.model_labels[role].configure(text="Model · blank uses client default")
                self.effort_labels[role].configure(text="Effort · blank uses default")
            if claude:
                self.model_widgets[role]["values"] = CLAUDE_MODELS
                self.effort_widgets[role]["values"] = CLAUDE_EFFORTS
                self.effort_widgets[role].configure(state="normal")
            elif copilot:
                self.model_widgets[role]["values"] = [""] + [details[0] for details in self.model_choices["copilot"].values()]
                self.effort_widgets[role].configure(state="disabled")
            else:
                self.model_widgets[role]["values"] = [""] + [details[0] for details in self.model_choices["codex"].values()]
                self.effort_widgets[role]["values"] = [""] + list(dict.fromkeys(e for values in self.model_choices["codex"].values() for e in values[1:]))
                self.effort_widgets[role].configure(state="normal")
        self.previous_client = client
        self.scope_changed()

    def refresh_models(self) -> None:
        client = self.client.get()
        if client == "claude" or self.refreshing:
            return
        self.refreshing = True
        self.refresh_button.configure(state="disabled")
        self.refresh_status.set(f"Querying {client.capitalize()} for available models…")
        def worker() -> None:
            server = None
            try:
                if client == "copilot":
                    models = copilot_models()
                else:
                    server = AppServer()
                    models = server.models()
                self.refresh_queue.put((client, True, models))
            except Exception as exc:
                self.refresh_queue.put((client, False, str(exc)))
            finally:
                if server is not None:
                    server.close()

        threading.Thread(target=worker, daemon=True).start()

    def poll_refresh(self) -> None:
        try:
            client, ok, value = self.refresh_queue.get_nowait()
        except queue.Empty:
            self.root.after(150, self.poll_refresh)
            return
        self.refreshing = False
        if ok:
            self.model_choices[client] = value
        if client != self.client.get():
            self.refresh_button.configure(state="disabled" if self.client.get() == "claude" else "normal")
            self.root.after(150, self.poll_refresh)
            return
        if ok:
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
                if self.client.get() == "copilot":
                    lines.append("\nModel (blank means inherit client default):")
                    lines.extend(f"  {role}: model={self.model_vars[role].get() or '(inherit)'}" for role in roles)
                elif self.client.get() == "claude":
                    # Use the same planner as the write action so invalid selections and
                    # unmanaged or edited destination files are visible before confirmation.
                    _planned_roles, _planned_roots, _templates, entries = self.plan()
                    lines.append("\nClaude Code fields (blank omits the frontmatter field):")
                    for role, path, content in entries:
                        frontmatter = content.split("---\n", 2)[1]
                        values = {}
                        for field in frontmatter.splitlines():
                            key, separator, value = field.partition(": ")
                            if separator:
                                values[key] = json.loads(value)
                        lines.append(
                            f"  {role} ({path}): model={values.get('model', '(omitted; Claude resolves at runtime)')}, "
                            f"effort={values.get('effort', '(omitted; Claude resolves at runtime)')}"
                        )
                    lines.append("Explicit model=inherit follows the spawning conversation's model. Effort support varies by model; Claude Code may lower unsupported levels or apply account/policy caps.")
                else:
                    lines.append("\nModel and effort (blank means inherit client defaults):")
                    lines.extend(f"  {role}: model={self.model_vars[role].get() or '(inherit)'}, effort={self.effort_vars[role].get() or '(inherit)'}" for role in roles)
            lines.append("\nExisting files are updated only when their marker and template text match exactly. No instruction file or client config is edited.")
            for role in roles:
                if role in self.scope_conflicts:
                    lines.append(f"Warning: existing values differ for {role}: {self.scope_conflicts[role]!r}. Choose values explicitly to unify them.")
        except (OSError, ValueError, RuntimeError, UnicodeError, tomllib.TOMLDecodeError) as exc:
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
            written, _backups = perform_role_plan(entries, self.client.get(), "install")
            messagebox.showinfo("Configuration complete", "Written:\n" + "\n".join(written))
        except (OSError, ValueError, RuntimeError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            details = ""
            if written:
                details = "\n\nThese files were already written before the error:\n" + "\n".join(written)
            messagebox.showerror("Configuration stopped", f"{exc}{details}\n\nEach file replacement is atomic, but the full set is not transactional.")


def main() -> None:
    from gui import main as launch
    launch()


if __name__ == "__main__":
    main()
