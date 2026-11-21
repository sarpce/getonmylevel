"""Install selected getonmylevel skills using a small Tkinter interface."""

from __future__ import annotations

from pathlib import Path
import queue
import threading
import webbrowser
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as exc:
    print(f"Tkinter is unavailable ({exc}). Use the terminal installation instructions in README.md.")
    raise SystemExit(0)

import common
import suggested_installers


SOURCE_ROOT = Path(__file__).resolve().parent.parent / "skills"
SOURCE_REPO = SOURCE_ROOT.parent.resolve()


class Installer:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("getonmylevel skill installer")
        root.geometry("800x820")
        root.minsize(660, 700)

        outer = ttk.Frame(root, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Install or update getonmylevel skills", font=("TkDefaultFont", 16, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Choose skills and where to install them. Nothing is written until you select Install and confirm.").pack(anchor="w", pady=(4, 12))

        skills_box = ttk.LabelFrame(outer, text="Skills", padding=10)
        skills_box.pack(fill="x")
        self.selected = {name: tk.BooleanVar(value=True) for name in common.SKILL_NAMES}
        for name in common.SKILL_NAMES:
            ttk.Checkbutton(skills_box, text=name, variable=self.selected[name], command=self.refresh_preview).pack(anchor="w")

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
        ttk.Button(outer, text="Optional CodeGraph information...", command=self.show_codegraph_info).pack(anchor="w", pady=(8, 10))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x")
        self.skill_button = ttk.Button(buttons, text="Install or update selected skills", command=self.install)
        self.skill_button.pack(side="right")
        self.close_button = ttk.Button(buttons, text="Close", command=self.close)
        self.close_button.pack(side="right", padx=(0, 8))
        self.suggested_busy = False
        self.suggested_confirming = False
        self.suggested_queue = queue.Queue()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.scope_changed()

    def close(self) -> None:
        if self.suggested_busy or self.suggested_confirming:
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
        try:
            confirmed = messagebox.askyesno("Confirm suggested installations", confirmation)
        except tk.TclError as exc:
            self.suggested_button.configure(state="normal")
            self.skill_button.configure(state="normal")
            messagebox.showerror("Confirmation unavailable", f"Could not show the confirmation dialog: {exc}")
            return
        finally:
            self.suggested_confirming = False
        if not confirmed:
            self.suggested_button.configure(state="normal")
            self.skill_button.configure(state="normal")
            return
        self.start_suggested_install(plans)

    def start_suggested_install(self, plans: list[suggested_installers.SuggestedInstallPlan]) -> None:
        self.suggested_busy = True
        self.skill_button.configure(state="disabled")
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

    def show_codegraph_info(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Optional CodeGraph integration")
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="CodeGraph is optional and is never installed by this tool.", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Review the upstream repository and inspect your existing Codex MCP and AGENTS setup before running these commands. Installation may write global MCP configuration and AGENTS instructions.", wraplength=540).pack(anchor="w", pady=(8, 8))
        ttk.Label(frame, text="npm install -g @colbymchenry/codegraph\ncodegraph install\ncodegraph init", justify="left").pack(anchor="w", pady=(0, 8))
        ttk.Label(frame, text="https://github.com/colbymchenry/codegraph", wraplength=540).pack(anchor="w")
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Open upstream documentation...", command=lambda: webbrowser.open("https://github.com/colbymchenry/codegraph")).pack(side="left")
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="right")

    def selections(self):
        names = [name for name, var in self.selected.items() if var.get()]
        if self.scope.get() in ("repo", "both") and not self.repo_path.get().strip():
            raise ValueError("Choose an existing target repository for repository scope.")
        repo_root = Path(self.repo_path.get()).expanduser() if self.scope.get() in ("repo", "both") else None
        if repo_root is not None and common.canonical(repo_root) == SOURCE_REPO:
            raise ValueError("The target repository must differ from this source checkout.")
        roots = common.skill_roots(self.scope.get(), repo_root)
        copies = common.preflight_skill_copy(SOURCE_ROOT, names, roots)
        return names, roots, copies

    def refresh_preview(self) -> None:
        try:
            names = [name for name, var in self.selected.items() if var.get()]
            if self.scope.get() in ("repo", "both") and not self.repo_path.get().strip():
                raise ValueError("Choose an existing target repository for repository scope.")
            repo_root = Path(self.repo_path.get()).expanduser() if self.scope.get() in ("repo", "both") else None
            roots = common.skill_roots(self.scope.get(), repo_root)
            plan = common.preflight_skill_copy(SOURCE_ROOT, names, roots) if names else []
            lines = [f"Skills: {', '.join(names) if names else '(none selected)'}", "Actions:"]
            lines.extend(f"  {'Update' if operation.is_update else 'Install'}: {operation.destination}" for operation in plan)
            if any(operation.is_update for operation in plan):
                lines.append("\nUpdates replace the selected skill directory. Its previous contents are preserved in a backup.")
            lines.append("\nThe checked-out skill files are the versions this installer installs.")
            if not names:
                lines.append("Select at least one skill before installing.")
        except (OSError, ValueError) as exc:
            lines = ["Destinations:", f"  {exc}", "Choose an existing repository when repository scope is selected."]
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", "\n".join(lines))
        self.preview.configure(state="disabled")

    def install(self) -> None:
        try:
            names, roots, copies = self.selections()
            actions = [f"{'Update' if operation.is_update else 'Install'}: {operation.destination}" for operation in copies]
            confirmation = "Use the skill versions in this checkout?\n\n" + "\n".join(actions)
            if any(operation.is_update for operation in copies):
                confirmation += "\n\nUpdates replace selected directories and preserve their previous contents in backups."
            if not messagebox.askyesno("Confirm installation or update", confirmation):
                return
            result = common.copy_skills(copies)
            sections = []
            if result.installed:
                sections.append("Installed:\n" + "\n".join(result.installed))
            if result.updated:
                sections.append("Updated:\n" + "\n".join(result.updated))
            if result.backups:
                sections.append("Backups:\n" + "\n".join(result.backups))
            messagebox.showinfo("Installation complete", "\n\n".join(sections) + "\n\nNo Codex settings or global instructions were changed.")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Installation stopped", str(exc))


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
