"""Install selected getonmylevel skills using a small Tkinter interface."""

from __future__ import annotations

from pathlib import Path
import queue
import threading
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as exc:
    print(f"Tkinter is unavailable ({exc}). Use the terminal installation instructions in README.md.")
    raise SystemExit(0)

import common
import codegraph_installer
import instruction_integration
import suggested_installers
import skill_operations


SOURCE_ROOT = Path(__file__).resolve().parent.parent / "skills"
SOURCE_REPO = SOURCE_ROOT.parent.resolve()

SKILL_DESCRIPTIONS = {
    "getonmylevel-communication": ("Communication", "Clear, concise answers that keep context and actionable detail."),
    "getonmylevel-context": ("Project context", "Find relevant code efficiently and maintain useful local architecture notes."),
    "getonmylevel-engineering": ("Engineering workflow", "Pragmatic practices for design, implementation, testing, and review."),
    "getonmylevel-design": ("Interface design", "Create deliberate, accessible interfaces with a coherent visual system."),
    "getonmylevel-good-software-engineering-practices": ("Software practices", "Build reliable, maintainable changes that fit the existing project."),
    "getonmylevel-skill-discovery": ("Skill discovery", "Find and apply available skills when they can help with the task."),
}


perform_install = skill_operations.perform_install

class Installer:
    def __init__(self, root: tk.Tk, parent=None, configure_window: bool = True) -> None:
        self.root = root
        self.client = tk.StringVar(value="codex")
        if configure_window:
            root.title("getonmylevel · Skills and agents")
            root.geometry("1000x780")
            root.minsize(760, 620)

        outer = ttk.Frame(parent or root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Skills and tools", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        self.intro_label = ttk.Label(outer, text="Choose the capabilities you want to add. Review every destination before applying changes.",
                                     style="Muted.TLabel", wraplength=900)
        self.intro_label.pack(anchor="w", pady=(5, 16))
        client_row = ttk.Frame(outer)
        client_row.pack(fill="x", pady=(0, 8))
        ttk.Label(client_row, text="Client:").pack(side="left")
        self.client_buttons = []
        for label, value in (("Codex", "codex"), ("Claude Code", "claude")):
            button = ttk.Radiobutton(client_row, text=label, value=value, variable=self.client,
                                     command=self.client_changed)
            button.pack(side="left", padx=6)
            self.client_buttons.append(button)

        ttk.Label(outer, text="Core skills", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        self.skills_grid = ttk.Frame(outer)
        self.skills_grid.pack(fill="x")
        self.selected = {name: tk.BooleanVar(value=True) for name in common.SKILL_NAMES}
        self.skill_checks = []
        self.skill_cards = {}
        self.skill_card_bodies = {}
        self.skill_card_title_rows = {}
        self.skill_card_markers = {}
        self.skill_card_checkbuttons = {}
        self.skill_card_descriptions = {}
        for name in common.SKILL_NAMES:
            title, description = SKILL_DESCRIPTIONS[name]
            card = tk.Frame(self.skills_grid, background="#FFFFFF", highlightthickness=1,
                            highlightbackground="#D4D4D8", highlightcolor="#059669")
            body = ttk.Frame(card, style="Card.TFrame", padding=12)
            body.pack(fill="both", expand=True)
            title_row = ttk.Frame(body, style="Card.TFrame")
            title_row.pack(fill="x")
            marker = ttk.Label(title_row, text="○", style="CardMarker.TLabel", width=2, anchor="center")
            marker.pack(side="left", padx=(0, 4))
            check = ttk.Checkbutton(title_row, text=title, variable=self.selected[name], style="Card.TCheckbutton",
                                    command=self.refresh_preview)
            check.pack(side="left", anchor="w", fill="x", expand=True)
            detail = ttk.Label(body, text=description, style="CardMuted.TLabel", wraplength=260,
                               justify="left")
            detail.pack(anchor="w", fill="x", pady=(5, 0))
            self.skill_cards[name] = card
            self.skill_card_bodies[name] = body
            self.skill_card_title_rows[name] = title_row
            self.skill_card_markers[name] = marker
            self.skill_card_checkbuttons[name] = check
            self.skill_card_descriptions[name] = detail
            self.skill_checks.append(check)
            self.selected[name].trace_add("write", lambda *_args, key=name: self.update_skill_card(key))
        self.skills_grid.bind("<Configure>", self.reflow_skill_cards)

        codegraph_card = ttk.LabelFrame(outer, text="Recommended tool", style="Card.TLabelframe")
        codegraph_card.pack(fill="x", pady=(12, 0))
        self.codegraph_selected = tk.BooleanVar(value=False)
        self.codegraph_by_client = {"codex": False, "claude": False}
        codegraph_row = ttk.Frame(codegraph_card, style="Card.TFrame")
        codegraph_row.pack(fill="x")
        self.codegraph_marker = ttk.Label(codegraph_row, text="○", style="CardMarker.TLabel", width=2, anchor="center")
        self.codegraph_marker.pack(side="left", padx=(0, 4))
        self.codegraph_check = ttk.Checkbutton(codegraph_row, text="CodeGraph · global client integration",
                                               variable=self.codegraph_selected, command=self.refresh_preview,
                                               style="Card.TCheckbutton")
        self.codegraph_check.pack(side="left", anchor="w")
        self.codegraph_selected.trace_add("write", self.update_codegraph_marker)
        self.codegraph_selected.trace_add("write", self.remember_codegraph_selection)
        self.codegraph_description = ttk.Label(codegraph_card, text="Optional: install CodeGraph if needed and configure the selected client globally after confirmation.",
                                               style="CardMuted.TLabel", wraplength=600)
        self.codegraph_description.pack(anchor="w", padx=(26, 0), pady=(2, 0))

        scope_box = ttk.LabelFrame(outer, text="Install location", padding=10)
        scope_box.pack(fill="x", pady=(10, 0))
        self.scope = tk.StringVar(value="user")
        for label, value in (("User-wide", "user"), ("Target repository", "repo"), ("Both", "both")):
            ttk.Radiobutton(scope_box, text=label, value=value, variable=self.scope, command=self.scope_changed).pack(side="left", padx=(0, 12))
        repo_row = ttk.Frame(scope_box)
        repo_row.pack(fill="x", pady=(8, 0))
        self.repo_path = tk.StringVar()
        ttk.Label(repo_row, text="Target repository:").pack(side="left")
        ttk.Entry(repo_row, textvariable=self.repo_path).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(repo_row, text="Browse…", command=self.browse_repo).pack(side="left")

        self.activation_box = ttk.LabelFrame(outer, text="Active by default", padding=8)
        self.activation_box.pack(fill="x", pady=(10, 0))
        ttk.Label(self.activation_box, text="Choose skills to read when relevant. Installed files remain available when unchecked.").pack(anchor="w")
        self.activation_rows = ttk.Frame(self.activation_box)
        self.activation_rows.pack(fill="x")
        self.activation_vars = {}
        self.activation_cache = {}
        self.activation_key = None
        self.activation_button = ttk.Button(self.activation_box, text="Apply active skills...", command=self.apply_activation)
        self.activation_button.pack(anchor="e")
        self.repo_path.trace_add("write", lambda *_: self.load_activation())

        suggested_box = ttk.LabelFrame(outer, text="Suggested skillsets and tools", padding=8)
        suggested_box.pack(fill="x", pady=(10, 0))
        self.suggested_description = ttk.Label(suggested_box, text="Optional user-wide Codex skills and tools. These suggested installers do not configure Claude Code.",
                                               wraplength=600, style="Muted.TLabel")
        self.suggested_description.pack(anchor="w")
        self.suggested_selected = {item.id: tk.BooleanVar(value=False) for item in suggested_installers.SUGGESTED_ITEMS}
        self.suggested_checks = []
        self.suggested_labels = {}
        self.suggested_actions = {}
        for item in suggested_installers.SUGGESTED_ITEMS:
            check = ttk.Checkbutton(suggested_box, text=item.name, variable=self.suggested_selected[item.id])
            check.pack(anchor="w")
            detail = ttk.Label(suggested_box, text=item.description, wraplength=680)
            detail.pack(anchor="w", padx=(24, 0))
            self.suggested_checks.append(check)
            self.suggested_labels[item.id] = (check, detail)
        self.suggested_refresh_button = ttk.Button(suggested_box, text="Refresh status", command=self.refresh_suggested_status)
        self.suggested_refresh_button.pack(anchor="e")
        self.suggested_button = ttk.Button(suggested_box, text="Apply selected changes...", command=self.install_suggestions)
        self.suggested_button.pack(anchor="e", pady=(4, 0))

        ttk.Label(outer, text="Preview").pack(anchor="w", pady=(12, 4))
        self.preview = tk.Text(outer, height=9, wrap="word", state="disabled", borderwidth=1,
                               highlightthickness=1, highlightbackground="#394454", highlightcolor="#68a7ff",
                               padx=10, pady=8)
        self.preview.pack(fill="both", expand=True)

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x")
        self.skill_button = ttk.Button(buttons, text="Install or update selected skills", command=self.install)
        self.skill_button.configure(style="Primary.TButton")
        self.skill_button.pack(side="right")
        self.remove_button = ttk.Button(buttons, text="Remove getonmylevel instructions", command=self.remove_instructions)
        self.remove_button.pack(side="right", padx=(0, 8))
        self.remove_skills_button = ttk.Button(buttons, text="Remove selected skills", command=self.remove_skills)
        self.remove_skills_button.pack(side="right", padx=(0, 8))
        self.close_button = ttk.Button(buttons, text="Close", command=self.close)
        self.close_button.pack(side="right", padx=(0, 8))
        self.suggested_busy = False
        self.suggested_confirming = False
        self.suggested_queue = queue.Queue()
        self.install_queue = queue.Queue()
        self.install_busy = False
        self.refresh_suggested_status()
        for name in common.SKILL_NAMES:
            self.update_skill_card(name)
        outer.bind("<Configure>", self.fit_page_copy)
        if configure_window:
            root.protocol("WM_DELETE_WINDOW", self.close)
        self.load_activation()
        self.refresh_preview()

    def selected_client(self) -> str:
        client = getattr(self, "client", None)
        return client.get() if client is not None else "codex"

    def update_skill_card(self, name: str) -> None:
        card = self.skill_cards[name]
        selected = self.selected[name].get()
        card.configure(highlightbackground="#D4D4D8")
        self.skill_card_bodies[name].configure(style="Selected.Card.TFrame" if selected else "Card.TFrame")
        self.skill_card_title_rows[name].configure(style="Selected.Card.TFrame" if selected else "Card.TFrame")
        self.skill_card_descriptions[name].configure(style="Selected.CardMuted.TLabel" if selected else "CardMuted.TLabel")
        self.skill_card_markers[name].configure(text="✓" if selected else "○",
                                                style="Selected.CardMarker.TLabel" if selected else "CardMarker.TLabel")
        self.skill_card_checkbuttons[name].configure(style="Selected.Card.TCheckbutton" if selected else "Card.TCheckbutton")
        self.refresh_preview()

    def fit_page_copy(self, event) -> None:
        width = max(240, event.width - 36)
        self.intro_label.configure(wraplength=width)
        self.codegraph_description.configure(wraplength=max(220, width - 72))
        self.suggested_description.configure(wraplength=max(220, width - 24))

    def update_codegraph_marker(self, *_args) -> None:
        selected = self.codegraph_selected.get()
        self.codegraph_marker.configure(text="✓" if selected else "○",
                                        style="Selected.CardMarker.TLabel" if selected else "CardMarker.TLabel")

    def remember_codegraph_selection(self, *_args) -> None:
        self.codegraph_by_client[self.client.get()] = self.codegraph_selected.get()

    def reflow_skill_cards(self, event=None) -> None:
        width = event.width if event is not None else self.skills_grid.winfo_width()
        columns = 3 if width >= 740 else 2 if width >= 480 else 1
        for child in self.skill_cards.values():
            child.grid_forget()
        for column in range(3):
            self.skills_grid.columnconfigure(column, weight=0, minsize=0, uniform="")
        for column in range(columns):
            self.skills_grid.columnconfigure(column, weight=1, uniform="skill-card")
        card_width = max(220, (width - 12 * (columns - 1)) // columns)
        for index, name in enumerate(self.skill_cards):
            card = self.skill_cards[name]
            card.grid(row=index // columns, column=index % columns, sticky="nsew",
                      padx=(0 if index % columns == 0 else 6, 6 if index % columns < columns - 1 else 0),
                      pady=(0, 12))
            self.skill_card_descriptions[name].configure(wraplength=max(180, card_width - 36))

    def client_changed(self) -> None:
        self.load_activation()
        claude = self.client.get() == "claude"
        self.codegraph_selected.set(self.codegraph_by_client[self.client.get()])
        self.codegraph_check.configure(state="normal")
        for check in self.suggested_checks:
            check.configure(state="disabled" if claude else "normal")
        self.suggested_button.configure(state="disabled" if claude else "normal")
        self.suggested_refresh_button.configure(state="disabled" if claude else "normal")
        self.refresh_preview()

    def close(self) -> None:
        if self.suggested_busy or self.suggested_confirming or self.install_busy:
            messagebox.showinfo("Installation in progress", "Finish or cancel the suggested installation before closing.")
            return
        self.root.destroy()

    def install_suggestions(self) -> None:
        if self.suggested_busy or self.suggested_confirming:
            return
        selected = [item_id for item_id, variable in self.suggested_selected.items() if variable.get()]
        if not selected:
            messagebox.showinfo("No suggestions selected", "Select an item first.")
            return
        status = suggested_installers.suggested_status()
        installs, removals, errors = [], [], []
        for item_id in selected:
            if status[item_id]:
                if item_id == "rtk":
                    errors.append(f"RTK is detected at {status[item_id]}. Remove it manually using its package manager.")
                    continue
                plan, error = suggested_installers.plan_removal(item_id)
                if error:
                    errors.append(error)
                elif plan:
                    removals.append(plan)
            else:
                plans, error = suggested_installers.plan_selected([item_id])
                if error:
                    errors.append(error)
                elif plans:
                    installs.extend(plans)
        if errors:
            messagebox.showwarning("Suggested items unavailable", "\n\n".join(errors))
            self.refresh_suggested_status()
            return
        actions = [plan.confirmation_text for plan in (*installs, *removals)]
        confirmation = "Review these changes for the current user:\n\n" + "\n\n".join(actions)
        if installs:
            confirmation += "\n\nSelected commits and package versions are shown above. Commits are checked before use. Selected installers may download files; CLI-Anything executes upstream code with your privileges. RTK requires manual installation because package-manager commands float."
        confirmation += "\n\nCanceling makes no changes."
        self.suggested_confirming = True
        self.suggested_button.configure(state="disabled")
        self.skill_button.configure(state="disabled")
        self.remove_button.configure(state="disabled")
        self.remove_skills_button.configure(state="disabled")
        try:
            confirmed = messagebox.askyesno("Confirm suggested changes", confirmation)
        except tk.TclError as exc:
            self.suggested_button.configure(state="normal")
            self.skill_button.configure(state="normal")
            self.remove_button.configure(state="normal")
            self.remove_skills_button.configure(state="normal")
            messagebox.showerror("Confirmation unavailable", f"Could not show the confirmation dialog: {exc}")
            return
        finally:
            self.suggested_confirming = False
        if not confirmed:
            self.suggested_button.configure(state="normal")
            self.skill_button.configure(state="normal")
            self.remove_button.configure(state="normal")
            self.remove_skills_button.configure(state="normal")
            return
        self.start_suggested_install(installs, removals)

    def start_suggested_install(self, plans: list[suggested_installers.SuggestedInstallPlan], removals=()) -> None:
        self.suggested_busy = True
        self.skill_button.configure(state="disabled")
        self.remove_button.configure(state="disabled")
        self.remove_skills_button.configure(state="disabled")
        self.close_button.configure(state="disabled")
        self.suggested_button.configure(state="disabled")
        self.suggested_refresh_button.configure(state="disabled")
        for check in self.suggested_checks:
            check.configure(state="disabled")
        self.suggested_status = tk.Toplevel(self.root)
        self.suggested_status.title("Applying suggested changes")
        self.suggested_status.transient(self.root)
        self.suggested_status.protocol("WM_DELETE_WINDOW", lambda: None)
        ttk.Label(self.suggested_status, text="Applying selected changes. The interface remains available while operations run.",
                  padding=16, wraplength=420).pack()

        def worker() -> None:
            try:
                result = suggested_installers.install_selected(plans)
                result.extend(suggested_installers.remove_selected(list(removals)))
            except Exception as exc:
                result = [("Suggested changes", False, f"Worker failed; partial changes may remain: {exc}")]
            self.suggested_queue.put(result)

        try:
            threading.Thread(target=worker, daemon=True).start()
        except (RuntimeError, OSError) as exc:
            self.finish_suggested_install()
            self.suggested_status.destroy()
            messagebox.showerror("Operation could not start", f"Could not start the worker: {exc}")
            return
        self.root.after(100, self.poll_suggested_result)

    def finish_suggested_install(self) -> None:
        self.suggested_busy = False
        self.skill_button.configure(state="normal")
        self.remove_button.configure(state="normal")
        self.remove_skills_button.configure(state="normal")
        self.close_button.configure(state="normal")
        self.suggested_button.configure(state="normal")
        self.suggested_refresh_button.configure(state="normal")
        for check in self.suggested_checks:
            check.configure(state="normal")
        self.refresh_suggested_status()

    def poll_suggested_result(self) -> None:
        try:
            results = self.suggested_queue.get_nowait()
        except queue.Empty:
            self.root.after(100, self.poll_suggested_result)
            return
        self.suggested_status.destroy()
        self.finish_suggested_install()
        sections = [f"{'Completed' if success else 'Failed'}: {name}\n{detail}" for name, success, detail in results]
        has_failures = any(not success for _, success, _ in results)
        title = "Suggested changes completed with issues" if has_failures else "Suggested changes complete"
        message = "\n\n".join(sections)
        (messagebox.showwarning if has_failures else messagebox.showinfo)(title, message)
        for variable in self.suggested_selected.values():
            variable.set(False)
        self.refresh_suggested_status()

    def refresh_suggested_status(self) -> None:
        status = suggested_installers.suggested_status()
        by_id = {item.id: item for item in suggested_installers.SUGGESTED_ITEMS}
        for item_id, (check, detail) in self.suggested_labels.items():
            item = by_id[item_id]
            locations = status[item_id]
            action = "manual" if item_id == "rtk" else "remove" if locations else "install"
            if self.suggested_actions.get(item_id) not in (None, action):
                self.suggested_selected[item_id].set(False)
            self.suggested_actions[item_id] = action
            if item_id == "rtk" and locations:
                detail.configure(text=f"{item.description} Installed at {locations}. Remove manually with your package manager.")
                check.configure(text=f"{item.name} (manual removal)", state="disabled")
                self.suggested_selected[item_id].set(False)
            elif item_id == "rtk":
                detail.configure(text=f"{item.description} Not detected on PATH. Automatic installation is unavailable because package-manager versions move; install a reviewed version manually from {suggested_installers.RTK_INSTALL_URL}.")
                check.configure(text=f"{item.name} (manual installation only)", state="disabled")
                self.suggested_selected[item_id].set(False)
            elif locations:
                detail.configure(text="Installed at: " + ", ".join(map(str, locations)))
                check.configure(text=f"Remove {item.name}", state="disabled" if self.suggested_busy else "normal")
            else:
                detail.configure(text=f"Not installed in supported locations. {item.description}")
                check.configure(text=f"Install {item.name}", state="disabled" if self.suggested_busy else "normal")
        self.suggested_refresh_button.configure(state="disabled" if self.suggested_busy else "normal")

    def scope_changed(self) -> None:
        self.load_activation()
        self.refresh_preview()

    def browse_repo(self) -> None:
        chosen = filedialog.askdirectory(title="Choose an existing target repository")
        if chosen:
            self.repo_path.set(chosen)
            self.refresh_preview()

    def load_activation(self) -> None:
        if not hasattr(self, "activation_rows"):
            return
        if self.activation_key is not None:
            self.activation_cache[self.activation_key] = {scope: [n for n, v in variables.items() if v.get()]
                                                          for scope, variables in self.activation_vars.items()}
        for widget in self.activation_rows.winfo_children():
            widget.destroy()
        self.activation_vars = {}
        repo_text = self.repo_path.get().strip()
        key = (self.selected_client(), self.scope.get(), repo_text)
        self.activation_key = key
        try:
            repo = Path(repo_text).expanduser() if repo_text and self.scope.get() in ("repo", "both") else None
            existing = instruction_integration.active_skills(self.scope.get(), repo, self.selected_client())
            selections = self.activation_cache.get(key, existing)
            for scope in existing:
                row = ttk.Frame(self.activation_rows)
                row.pack(fill="x")
                ttk.Label(row, text="User-wide:" if scope == "user" else "Repository:").grid(row=0, column=0, sticky="w", padx=(0, 8))
                self.activation_vars[scope] = {}
                for index, name in enumerate(common.SKILL_NAMES):
                    var = tk.BooleanVar(value=name in selections.get(scope, []))
                    self.activation_vars[scope][name] = var
                    ttk.Checkbutton(row, text=SKILL_DESCRIPTIONS[name][0], variable=var,
                                    command=self.refresh_preview).grid(row=index // 3, column=index % 3 + 1, sticky="w", padx=(0, 8))
        except (OSError, ValueError) as exc:
            ttk.Label(self.activation_rows, text=str(exc)).pack(anchor="w")
        self.refresh_preview()

    def activation_plan(self):
        if not self.activation_vars:
            raise ValueError("Choose a valid client and scope for activation.")
        selections = {scope: [name for name, var in variables.items() if var.get()]
                      for scope, variables in self.activation_vars.items()}
        return selections, *skill_operations.plan_activation(selections, self.repo_path.get(), self.selected_client())

    def apply_activation(self) -> None:
        try:
            selections, copies, plans = self.activation_plan()
            lines = [f"{scope}: {', '.join(names) or '(none)'}" for scope, names in selections.items()]
            lines += [f"Required installation: {copy.destination}" for copy in copies]
            lines += [f"{plan.action}: {plan.path}" for plan in plans]
            if not messagebox.askyesno("Confirm active skills", "Apply these default skill selections?\n\n" + "\n".join(lines)):
                return
            _, written = perform_install(copies, plans, self.selected_client())
            self.activation_cache.pop(self.activation_key, None)
            self.activation_key = None
            self.load_activation()
            messagebox.showinfo("Active skills updated", "Updated instruction files:\n" + ("\n".join(map(str, written)) or "None"))
        except (OSError, ValueError, RuntimeError) as exc:
            self.show_install_error(exc)

    def selections(self):
        client = self.selected_client()
        names = [name for name, var in self.selected.items() if var.get()]
        wants_codegraph = getattr(self, "codegraph_selected", None)
        wants_codegraph = wants_codegraph.get() if wants_codegraph is not None else False
        if not names and not wants_codegraph:
            raise ValueError("Select at least one core skill or CodeGraph.")
        roots, copies, instruction_plans = [], [], []
        if names:
            if self.scope.get() in ("repo", "both") and not self.repo_path.get().strip():
                raise ValueError("Choose an existing target repository for repository scope.")
            repo_root = Path(self.repo_path.get()).expanduser() if self.scope.get() in ("repo", "both") else None
            if repo_root is not None and common.canonical(repo_root) == SOURCE_REPO:
                raise ValueError("The target repository must differ from this source checkout.")
            roots, copies, instruction_plans = skill_operations.plan_install(names, self.scope.get(), repo_root, client)
        codegraph_plan = codegraph_installer.plan_install(client) if wants_codegraph else None
        return names, roots, copies, instruction_plans, codegraph_plan

    def remove_skills(self) -> None:
        try:
            names = [name for name, var in self.selected.items() if var.get()]
            paths, plans = skill_operations.plan_remove(names, self.scope.get(), self.repo_path.get(), self.selected_client())
            actions = [str(path) for path, _ in paths] + [str(plan.path) for plan in plans]
            if not actions:
                messagebox.showinfo("Nothing to remove", "No selected skills or instruction references were found.")
                return
            if not messagebox.askyesno("Confirm skill removal", "Remove selected skills and their instruction references? Skill directories are preserved in backups.\n\n" + "\n".join(actions)):
                return
            backups, written = skill_operations.perform_remove(paths, plans, self.selected_client())
            self.refresh_preview()
            messagebox.showinfo("Skills removed", "Backups:\n" + ("\n".join(backups) or "None") + "\n\nInstructions updated:\n" + ("\n".join(map(str, written)) or "None"))
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Removal stopped", str(exc))

    def remove_instructions(self) -> None:
        try:
            if self.scope.get() in ("repo", "both") and not self.repo_path.get().strip():
                raise ValueError("Choose an existing target repository for repository scope.")
            repo_root = Path(self.repo_path.get()).expanduser() if self.scope.get() in ("repo", "both") else None
            if repo_root is not None and common.canonical(repo_root) == SOURCE_REPO:
                raise ValueError("The target repository must differ from this source checkout.")
            plans = instruction_integration.plan_instruction_removals(self.scope.get(), repo_root, self.selected_client())
            if not plans:
                messagebox.showinfo("Instructions already clear", "No getonmylevel-managed instruction blocks were found in the selected scope.")
                return
            paths = "\n".join(str(plan.path) for plan in plans)
            confirmation = ("Remove the getonmylevel-managed instruction blocks from these files?\n\n"
                            f"{paths}\n\nOther instructions and installed skill files will remain.")
            if not messagebox.askyesno("Confirm instruction removal", confirmation):
                return
            written = instruction_integration.write_instruction_removals(plans, self.selected_client())
            self.refresh_preview()
            messagebox.showinfo("Instructions removed", "Removed managed instructions from:\n" + "\n".join(map(str, written)))
        except (OSError, ValueError) as exc:
            details = str(exc)
            if isinstance(exc, instruction_integration.InstructionWriteError):
                details += "\n\nThe instruction operation is not transactional."
                if exc.written:
                    details += "\nFiles already changed: " + ", ".join(map(str, exc.written))
                details += "\nFailed file: " + str(exc.path)
            messagebox.showerror("Instruction removal stopped", details)

    def refresh_preview(self) -> None:
        try:
            client = self.selected_client()
            names = [name for name, var in self.selected.items() if var.get()]
            wants_codegraph = getattr(self, "codegraph_selected", None)
            wants_codegraph = wants_codegraph.get() if wants_codegraph is not None else False
            roots = []
            repo_root = None
            if names:
                if self.scope.get() in ("repo", "both") and not self.repo_path.get().strip():
                    raise ValueError("Choose an existing target repository for repository scope.")
                repo_root = Path(self.repo_path.get()).expanduser() if self.scope.get() in ("repo", "both") else None
                roots = common.skill_roots(self.scope.get(), repo_root, client)
            plan = common.preflight_skill_copy(SOURCE_ROOT, names, roots) if names else []
            lines = [f"Skills: {', '.join(names) if names else '(none selected)'}", "Actions:"]
            lines.extend(f"  {'Update' if operation.is_update else 'Install'}: {operation.destination}" for operation in plan)
            if any(operation.is_update for operation in plan):
                lines.append("\nUpdates replace the selected skill directory. Its previous contents are preserved in a backup.")
            if names:
                lines.append("\nThe checked-out skill files are the versions this installer installs.")
            if getattr(self, "activation_vars", None):
                selections, required, activation_plans = self.activation_plan()
                lines.append("\nActive by default:")
                lines.extend(f"  {scope}: {', '.join(selected) or '(none)'}" for scope, selected in selections.items())
                lines.extend(f"  Required installation: {item.destination}" for item in required)
                lines.extend(f"  {item.action}: {item.path}" for item in activation_plans)
            if wants_codegraph:
                codegraph_plan = codegraph_installer.plan_install(self.selected_client())
                client_name = "Claude Code" if self.selected_client() == "claude" else "Codex"
                lines.extend(["", "CodeGraph: optional user-wide tool", codegraph_plan.details,
                              f"  Configures {client_name} globally, including MCP configuration and managed instructions.",
                              f"  No project indexing or initialization will run. Restart {client_name} if needed."])
                lines.append("  Commands/actions:")
                lines.extend("    " + " ".join(command) for command in codegraph_plan.commands)
            if not names and not wants_codegraph:
                lines.append("Select at least one core skill or CodeGraph before installing.")
        except (OSError, ValueError, RuntimeError) as exc:
            lines = ["Installation preview:", f"  {exc}"]
            if names:
                lines.append("Choose an existing repository when repository scope is selected.")
            if wants_codegraph:
                lines.append("CodeGraph setup is unavailable until its prerequisites are available.")
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", "\n".join(lines))
        self.preview.configure(state="disabled")

    def install(self) -> None:
        if self.install_busy:
            return
        try:
            names, roots, copies, instruction_plans, codegraph_plan = self.selections()
            actions = [f"{'Update' if operation.is_update else 'Install'}: {operation.destination}" for operation in copies]
            actions.extend(f"Instructions ({item.action.lower()}): {item.path}" for item in instruction_plans)
            confirmation = "Review the selected installation or update."
            if actions:
                confirmation += "\n\n" + "\n".join(actions)
            if any(operation.is_update for operation in copies):
                confirmation += "\n\nUpdates replace selected directories and preserve their previous contents in backups."
            client = self.selected_client()
            client_name = "Claude Code" if client == "claude" else "Codex"

            if codegraph_plan:
                confirmation += (f"\n\nCodeGraph is an optional user-wide tool. It may download packages and will configure {client_name} globally, including its MCP configuration and managed instructions. "
                                 f"No project will be initialized or indexed. Restart {client_name} if needed.\n\n" + codegraph_plan.details +
                                 "\nCommands/actions:\n" + "\n".join("  " + " ".join(command) for command in codegraph_plan.commands))
            if not messagebox.askyesno("Confirm installation or update", confirmation):
                return
            self.start_install_worker(names, copies, instruction_plans, codegraph_plan, client)
        except (OSError, ValueError, RuntimeError) as exc:
            self.show_install_error(exc, locals().get("instruction_plans"))

    def start_install_worker(self, names, copies, instruction_plans, codegraph_plan, client) -> None:
        self.install_busy = True
        for widget in (self.skill_button, self.remove_button, self.remove_skills_button, self.close_button, self.suggested_button, self.codegraph_check, self.activation_button, *self.client_buttons, *self.skill_checks):
            widget.configure(state="disabled")
        self.install_status = tk.Toplevel(self.root)
        self.install_status.title("Installing selected components")
        self.install_status.transient(self.root)
        self.install_status.protocol("WM_DELETE_WINDOW", lambda: None)
        ttk.Label(self.install_status, text="Installing selected skills and tools. Changes may remain if a later step fails.",
                  padding=16, wraplength=420).pack()

        def worker() -> None:
            skill_stage_complete = False
            try:
                result, written = perform_install(copies, instruction_plans, client) if names else (common.SkillCopyResult((), (), ()), [])
                skill_stage_complete = True
                codegraph_result = codegraph_installer.install(codegraph_plan) if codegraph_plan else None
                sections = []
                if result.installed:
                    sections.append("Installed:\n" + "\n".join(result.installed))
                if result.updated:
                    sections.append("Updated:\n" + "\n".join(result.updated))
                if result.backups:
                    sections.append("Backups:\n" + "\n".join(result.backups))
                if written:
                    sections.append("Instruction files updated:\n" + "\n".join(map(str, written)))
                unchanged = [str(item.path) for item in instruction_plans if item.path not in written]
                if unchanged:
                    sections.append("Instruction files already current:\n" + "\n".join(unchanged))
                if codegraph_result:
                    sections.append("CodeGraph:\n" + codegraph_result)
                self.install_queue.put((True, "\n\n".join(sections) or "Nothing required changes."))
            except Exception as exc:
                message = str(exc)
                if isinstance(exc, instruction_integration.InstructionWriteError):
                    message += "\n\nSkills may already be installed or updated. The instruction operation is not transactional."
                    if exc.written:
                        message += "\nInstruction files already written: " + ", ".join(map(str, exc.written))
                    message += "\nFailed instruction file: " + str(exc.path)
                if codegraph_plan and skill_stage_complete:
                    message = "Skills and their instruction updates completed; CodeGraph setup failed and partial CodeGraph changes may remain. " + message
                elif codegraph_plan:
                    message += "\nCodeGraph setup was not started because the skill stage failed."
                self.install_queue.put((False, message))

        try:
            threading.Thread(target=worker, daemon=True).start()
        except (RuntimeError, OSError) as exc:
            self.finish_install_worker()
            self.install_status.destroy()
            messagebox.showerror("Installation could not start", f"Could not start the installation worker: {exc}")
            return
        self.root.after(100, self.poll_install_result)

    def finish_install_worker(self) -> None:
        self.install_busy = False
        for widget in (self.skill_button, self.remove_button, self.remove_skills_button, self.close_button, self.suggested_button, self.codegraph_check, self.activation_button, *self.client_buttons, *self.skill_checks):
            widget.configure(state="normal")
        claude = self.client.get() == "claude"
        self.suggested_button.configure(state="disabled" if claude else "normal")
        self.suggested_refresh_button.configure(state="disabled" if claude else "normal")

    def poll_install_result(self) -> None:
        try:
            success, message = self.install_queue.get_nowait()
        except queue.Empty:
            self.root.after(100, self.poll_install_result)
            return
        self.install_status.destroy()
        self.finish_install_worker()
        if success:
            messagebox.showinfo("Installation complete", message)
        else:
            messagebox.showerror("Installation stopped", message)

    def show_install_error(self, exc, instruction_plans=None) -> None:
        details = str(exc)
        if isinstance(exc, common.SkillCopyError):
            parts = []
            if exc.installed:
                parts.append("Skills already installed: " + ", ".join(exc.installed))
            if exc.updated:
                parts.append("Skills already updated: " + ", ".join(exc.updated))
            if exc.backups:
                parts.append("Backups: " + ", ".join(exc.backups))
            if parts:
                details += "\n\n" + "\n".join(parts) + "\nInstructions were not written because skill copying failed."
        elif isinstance(exc, instruction_integration.InstructionWriteError):
            details += "\n\nSkills may already be installed or updated. The instruction operation is not transactional."
            if exc.written:
                details += "\nInstruction files already written: " + ", ".join(map(str, exc.written))
            details += "\nFailed instruction file: " + str(exc.path)
        elif instruction_plans:
            details += "\n\nSkill and instruction changes may be partial: " + ", ".join(str(item.path) for item in instruction_plans)
        messagebox.showerror("Installation stopped", details)


def main() -> None:
    from gui import main as launch
    launch()


if __name__ == "__main__":
    main()
