"""Install selected getonmylevel skills using a small Tkinter interface."""

from __future__ import annotations

from pathlib import Path
import webbrowser
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as exc:
    print(f"Tkinter is unavailable ({exc}). Use the terminal installation instructions in README.md.")
    raise SystemExit(0)

import common


SOURCE_ROOT = Path(__file__).resolve().parent.parent / "skills"
SOURCE_REPO = SOURCE_ROOT.parent.resolve()


class Installer:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("getonmylevel skill installer")
        root.geometry("760x690")
        root.minsize(620, 560)

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

        ttk.Label(outer, text="Preview").pack(anchor="w", pady=(12, 4))
        self.preview = tk.Text(outer, height=9, wrap="word", state="disabled")
        self.preview.pack(fill="both", expand=True)
        ttk.Button(outer, text="Optional CodeGraph information...", command=self.show_codegraph_info).pack(anchor="w", pady=(8, 10))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Install or update selected skills", command=self.install).pack(side="right")
        ttk.Button(buttons, text="Close", command=root.destroy).pack(side="right", padx=(0, 8))
        self.scope_changed()

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
