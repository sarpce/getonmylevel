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


SOURCE_ROOT = Path(__file__).resolve().parent.parent / "skills"
SOURCE_REPO = SOURCE_ROOT.parent.resolve()


def perform_install(copies, instruction_plans):
    """Copy skills before writing their default-use instructions."""
    result = common.copy_skills(copies)
    written = instruction_integration.write_instruction_updates(instruction_plans)
    return result, written


class Installer:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("getonmylevel skill installer")
        root.geometry("800x820")
        root.minsize(660, 700)

        outer = ttk.Frame(root, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Install or update getonmylevel skills", font=("TkDefaultFont", 16, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Choose skills and where to install them, or remove getonmylevel-managed instructions. Changes require confirmation.").pack(anchor="w", pady=(4, 12))

        skills_box = ttk.LabelFrame(outer, text="Core skills", padding=10)
        skills_box.pack(fill="x")
        self.selected = {name: tk.BooleanVar(value=True) for name in common.SKILL_NAMES}
        self.skill_checks = []
        for name in common.SKILL_NAMES:
            check = ttk.Checkbutton(skills_box, text=name, variable=self.selected[name], command=self.refresh_preview)
            check.pack(anchor="w")
            self.skill_checks.append(check)
        self.codegraph_selected = tk.BooleanVar(value=False)
        self.codegraph_check = ttk.Checkbutton(skills_box, text="CodeGraph (optional global Codex integration)",
                                               variable=self.codegraph_selected, command=self.refresh_preview)
        self.codegraph_check.pack(anchor="w", pady=(5, 0))
        self.selected["getonmylevel-context"].trace_add("write", self.context_selection_changed)

        scope_box = ttk.LabelFrame(outer, text="Installation scope", padding=10)
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

        suggested_box = ttk.LabelFrame(outer, text="Suggested skillsets and tools", padding=8)
        suggested_box.pack(fill="x", pady=(10, 0))
        ttk.Label(suggested_box, text="Optional user-wide installs. Select any combination; all selected items are reviewed before installation.",
                  wraplength=700).pack(anchor="w")
        self.suggested_selected = {item.id: tk.BooleanVar(value=False) for item in suggested_installers.SUGGESTED_ITEMS}
        self.suggested_checks = []
        for item in suggested_installers.SUGGESTED_ITEMS:
            check = ttk.Checkbutton(suggested_box, text=f"{item.name} — {item.description}",
                                    variable=self.suggested_selected[item.id])
            check.pack(anchor="w")
            self.suggested_checks.append(check)
        self.suggested_button = ttk.Button(suggested_box, text="Install selected suggestions…",
                                           command=self.install_suggestions)
        self.suggested_button.pack(anchor="e", pady=(4, 0))

        ttk.Label(outer, text="Preview").pack(anchor="w", pady=(12, 4))
        self.preview = tk.Text(outer, height=9, wrap="word", state="disabled")
        self.preview.pack(fill="both", expand=True)

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x")
        self.skill_button = ttk.Button(buttons, text="Install or update selected skills", command=self.install)
        self.skill_button.pack(side="right")
        self.remove_button = ttk.Button(buttons, text="Remove getonmylevel instructions", command=self.remove_instructions)
        self.remove_button.pack(side="right", padx=(0, 8))
        self.close_button = ttk.Button(buttons, text="Close", command=self.close)
        self.close_button.pack(side="right", padx=(0, 8))
        self.suggested_busy = False
        self.suggested_confirming = False
        self.suggested_queue = queue.Queue()
        self.install_queue = queue.Queue()
        self.install_busy = False
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.context_selection_changed()

    def context_selection_changed(self, *_args) -> None:
        if self.selected["getonmylevel-context"].get():
            self.codegraph_selected.set(True)
            self.codegraph_check.configure(state="disabled")
        else:
            self.codegraph_check.configure(state="normal")
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
        plans, error = suggested_installers.plan_selected(selected)
        if error:
            messagebox.showwarning("Suggested items unavailable", error)
            return
        assert plans is not None
        confirmation = "Install these suggested items for the current user?\n\n"
        confirmation += "\n\n".join(plan.confirmation_text for plan in plans)
        confirmation += ("\n\nUpstream default branches are not pinned. Selected installers may download files or execute upstream code with your privileges. "
                         "Canceling makes no changes.")
        self.suggested_confirming = True
        self.suggested_button.configure(state="disabled")
        self.skill_button.configure(state="disabled")
        self.remove_button.configure(state="disabled")
        try:
            confirmed = messagebox.askyesno("Confirm suggested installations", confirmation)
        except tk.TclError as exc:
            self.suggested_button.configure(state="normal")
            self.skill_button.configure(state="normal")
            self.remove_button.configure(state="normal")
            messagebox.showerror("Confirmation unavailable", f"Could not show the confirmation dialog: {exc}")
            return
        finally:
            self.suggested_confirming = False
        if not confirmed:
            self.suggested_button.configure(state="normal")
            self.skill_button.configure(state="normal")
            self.remove_button.configure(state="normal")
            return
        self.start_suggested_install(plans)

    def start_suggested_install(self, plans: list[suggested_installers.SuggestedInstallPlan]) -> None:
        self.suggested_busy = True
        self.skill_button.configure(state="disabled")
        self.remove_button.configure(state="disabled")
        self.close_button.configure(state="disabled")
        self.suggested_button.configure(state="disabled")
        for check in self.suggested_checks:
            check.configure(state="disabled")
        self.suggested_status = tk.Toplevel(self.root)
        self.suggested_status.title("Installing suggested items")
        self.suggested_status.transient(self.root)
        self.suggested_status.protocol("WM_DELETE_WINDOW", lambda: None)
        ttk.Label(self.suggested_status, text="Installing selected suggestions. The interface remains available while installers run.",
                  padding=16, wraplength=420).pack()

        def worker() -> None:
            try:
                result = suggested_installers.install_selected(plans)
            except Exception as exc:
                result = [("Suggested installations", False, f"Worker failed; partial changes may remain: {exc}")]
            self.suggested_queue.put(result)

        try:
            threading.Thread(target=worker, daemon=True).start()
        except (RuntimeError, OSError) as exc:
            self.finish_suggested_install()
            self.suggested_status.destroy()
            messagebox.showerror("Installation could not start", f"Could not start the installation worker: {exc}")
            return
        self.root.after(100, self.poll_suggested_result)

    def finish_suggested_install(self) -> None:
        self.suggested_busy = False
        self.skill_button.configure(state="normal")
        self.remove_button.configure(state="normal")
        self.close_button.configure(state="normal")
        self.suggested_button.configure(state="normal")
        for check in self.suggested_checks:
            check.configure(state="normal")

    def poll_suggested_result(self) -> None:
        try:
            results = self.suggested_queue.get_nowait()
        except queue.Empty:
            self.root.after(100, self.poll_suggested_result)
            return
        self.suggested_status.destroy()
        self.finish_suggested_install()
        sections = [f"{'Installed' if success else 'Failed'}: {name}\n{detail}" for name, success, detail in results]
        has_failures = any(not success for _, success, _ in results)
        title = "Suggested installations completed with issues" if has_failures else "Suggested installations complete"
        message = "\n\n".join(sections)
        (messagebox.showwarning if has_failures else messagebox.showinfo)(title, message)

    def scope_changed(self) -> None:
        self.refresh_preview()

    def browse_repo(self) -> None:
        chosen = filedialog.askdirectory(title="Choose an existing target repository")
        if chosen:
            self.repo_path.set(chosen)
            self.refresh_preview()

    def selections(self):
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
            roots = common.skill_roots(self.scope.get(), repo_root)
            copies = common.preflight_skill_copy(SOURCE_ROOT, names, roots)
            instruction_plans = instruction_integration.plan_instruction_updates(self.scope.get(), repo_root, names)
        codegraph_plan = codegraph_installer.plan_install() if wants_codegraph else None
        return names, roots, copies, instruction_plans, codegraph_plan

    def remove_instructions(self) -> None:
        try:
            if self.scope.get() in ("repo", "both") and not self.repo_path.get().strip():
                raise ValueError("Choose an existing target repository for repository scope.")
            repo_root = Path(self.repo_path.get()).expanduser() if self.scope.get() in ("repo", "both") else None
            if repo_root is not None and common.canonical(repo_root) == SOURCE_REPO:
                raise ValueError("The target repository must differ from this source checkout.")
            plans = instruction_integration.plan_instruction_removals(self.scope.get(), repo_root)
            if not plans:
                messagebox.showinfo("Instructions already clear", "No getonmylevel-managed instruction blocks were found in the selected scope.")
                return
            paths = "\n".join(str(plan.path) for plan in plans)
            confirmation = ("Remove the getonmylevel-managed instruction blocks from these files?\n\n"
                            f"{paths}\n\nOther instructions and installed skill files will remain.")
            if not messagebox.askyesno("Confirm instruction removal", confirmation):
                return
            written = instruction_integration.write_instruction_removals(plans)
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
            names = [name for name, var in self.selected.items() if var.get()]
            wants_codegraph = getattr(self, "codegraph_selected", None)
            wants_codegraph = wants_codegraph.get() if wants_codegraph is not None else False
            roots = []
            repo_root = None
            if names:
                if self.scope.get() in ("repo", "both") and not self.repo_path.get().strip():
                    raise ValueError("Choose an existing target repository for repository scope.")
                repo_root = Path(self.repo_path.get()).expanduser() if self.scope.get() in ("repo", "both") else None
                roots = common.skill_roots(self.scope.get(), repo_root)
            plan = common.preflight_skill_copy(SOURCE_ROOT, names, roots) if names else []
            instruction_plans = instruction_integration.plan_instruction_updates(self.scope.get(), repo_root, names) if names else []
            lines = [f"Skills: {', '.join(names) if names else '(none selected)'}", "Actions:"]
            lines.extend(f"  {'Update' if operation.is_update else 'Install'}: {operation.destination}" for operation in plan)
            if any(operation.is_update for operation in plan):
                lines.append("\nUpdates replace the selected skill directory. Its previous contents are preserved in a backup.")
            lines.append("\nThe checked-out skill files are the versions this installer installs.")
            if instruction_plans:
                lines.append("\nCodex default-use instructions (existing text is preserved):")
                lines.extend(f"  {item.action}: {item.path}" for item in instruction_plans)
                lines.append("The managed instruction asks Codex to read these skills by default when relevant. A new conversation may be needed; higher-priority instructions still apply.")
            if wants_codegraph:
                codegraph_plan = codegraph_installer.plan_install()
                lines.extend(["", "CodeGraph: optional user-wide external dependency", codegraph_plan.details,
                              "  Configure Codex globally: codegraph install --target=codex --location=global --yes",
                              "  No project indexing or initialization will run. Restart Codex if needed."])
                if codegraph_plan.npm_install:
                    lines.append("  Planned package install: npm install -g @colbymchenry/codegraph")
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
            confirmation = "Use the skill versions in this checkout?\n\n" + "\n".join(actions)
            if any(operation.is_update for operation in copies):
                confirmation += "\n\nUpdates replace selected directories and preserve their previous contents in backups."
            confirmation += "\n\nCodex will be instructed to read these skills by default when relevant. Existing instruction text is preserved. A new conversation may be needed; higher-priority instructions still apply."
            if codegraph_plan:
                confirmation += ("\n\nCodeGraph is an optional user-wide external dependency. It may download packages and will configure Codex globally, including Codex MCP configuration and managed instructions. "
                                 "No project will be initialized or indexed. Restart Codex if needed.\n\n" + codegraph_plan.details +
                                 "\nCommands/actions:\n" + "\n".join("  " + " ".join(command) for command in codegraph_plan.commands))
            if not messagebox.askyesno("Confirm installation or update", confirmation):
                return
            self.start_install_worker(names, copies, instruction_plans, codegraph_plan)
        except (OSError, ValueError, RuntimeError) as exc:
            self.show_install_error(exc, locals().get("instruction_plans"))

    def start_install_worker(self, names, copies, instruction_plans, codegraph_plan) -> None:
        self.install_busy = True
        for widget in (self.skill_button, self.remove_button, self.close_button, self.suggested_button, self.codegraph_check, *self.skill_checks):
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
                result, written = perform_install(copies, instruction_plans) if names else (common.SkillCopyResult((), (), ()), [])
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
        for widget in (self.skill_button, self.remove_button, self.close_button, self.suggested_button, *self.skill_checks):
            widget.configure(state="normal")
        self.context_selection_changed()

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
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"Tkinter could not open a window ({exc}). Use the terminal installation instructions in README.md.")
        return
    Installer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
