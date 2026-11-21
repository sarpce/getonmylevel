"""Unified desktop interface for skill installation and agent setup."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk


BACKGROUND = "#FAFAFA"
SURFACE = "#F4F4F5"
SURFACE_ALT = "#E4E4E7"
TEXT = "#18181B"
MUTED = "#71717A"
ACCENT = "#059669"
BORDER = "#D4D4D8"


def apply_theme(root: tk.Tk) -> None:
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    root.configure(background=BACKGROUND)
    root.option_add("*Text.background", SURFACE)
    root.option_add("*Text.foreground", TEXT)
    root.option_add("*Text.insertBackground", TEXT)
    root.option_add("*Text.selectBackground", "#A7F3D0")
    root.option_add("*Text.selectForeground", TEXT)
    root.option_add("*Text.highlightBackground", ACCENT)
    root.option_add("*Text.highlightColor", ACCENT)

    style.configure(".", background=BACKGROUND, foreground=TEXT, font=("Segoe UI", 10))
    style.configure("TFrame", background=BACKGROUND)
    style.configure("Surface.TFrame", background=SURFACE)
    style.configure("Card.TFrame", background="#FFFFFF")
    style.configure("Selected.Card.TFrame", background="#ECFDF5")
    style.configure("Sidebar.TFrame", background=SURFACE)
    style.configure("Sidebar.TLabel", background=SURFACE, foreground=TEXT)
    style.configure("SidebarMuted.TLabel", background=SURFACE, foreground=MUTED)
    style.configure("SidebarRule.TFrame", background="#E4E4E7")
    style.configure("NavAccent.TFrame", background=ACCENT)
    style.configure("TLabel", background=BACKGROUND, foreground=TEXT)
    style.configure("Muted.TLabel", background=BACKGROUND, foreground=MUTED)
    style.configure("Card.TLabel", background="#FFFFFF", foreground=TEXT)
    style.configure("CardMuted.TLabel", background="#FFFFFF", foreground=MUTED)
    style.configure("Selected.CardMuted.TLabel", background="#ECFDF5", foreground=MUTED)
    style.configure("CardMarker.TLabel", background="#FFFFFF", foreground=MUTED, font=("Segoe UI", 11, "bold"))
    style.configure("Selected.CardMarker.TLabel", background="#ECFDF5", foreground=ACCENT, font=("Segoe UI", 11, "bold"))
    style.configure("TLabelframe", background=BACKGROUND, foreground=TEXT, bordercolor=BORDER, padding=10)
    style.configure("TLabelframe.Label", background=BACKGROUND, foreground=TEXT, font=("Segoe UI", 10, "bold"))
    style.configure("Card.TLabelframe", background="#FFFFFF", foreground=TEXT, bordercolor=BORDER, padding=12)
    style.configure("Card.TLabelframe.Label", background="#FFFFFF", foreground=TEXT, font=("Segoe UI", 10, "bold"))
    style.configure("Selected.Card.TLabelframe", background="#FFFFFF", foreground=TEXT, bordercolor=ACCENT, padding=12)
    style.configure("Selected.Card.TLabelframe.Label", background="#FFFFFF", foreground=TEXT, font=("Segoe UI", 10, "bold"))
    style.configure("TCheckbutton", background=BACKGROUND, foreground=TEXT, padding=(2, 4))
    style.map("TCheckbutton", background=[("active", SURFACE)], foreground=[("disabled", MUTED)])
    style.configure("Card.TCheckbutton", background="#FFFFFF", foreground=TEXT, padding=(3, 5), font=("Segoe UI", 10, "bold"), focuscolor=ACCENT)
    style.map("Card.TCheckbutton", background=[("focus", "#F4F4F5"), ("active", "#FFFFFF")], foreground=[("disabled", MUTED)])
    style.configure("Selected.Card.TCheckbutton", background="#ECFDF5", foreground=TEXT,
                    padding=(3, 5), font=("Segoe UI", 10, "bold"), focuscolor=ACCENT)
    style.map("Selected.Card.TCheckbutton", background=[("focus", "#D1FAE5"), ("active", "#ECFDF5")], foreground=[("disabled", MUTED)])
    # Keep a real ttk.Checkbutton for keyboard/accessibility semantics while drawing
    # the selected state in the card itself instead of the theme's tiny X indicator.
    style.layout("Card.TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [("Checkbutton.label", {"sticky": "nswe"})]})])
    style.layout("Selected.Card.TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [("Checkbutton.label", {"sticky": "nswe"})]})])
    style.configure("TRadiobutton", background=BACKGROUND, foreground=TEXT, padding=(2, 4))
    style.map("TRadiobutton", background=[("active", SURFACE)], foreground=[("disabled", MUTED)])
    style.configure("TEntry", fieldbackground="#FFFFFF", foreground=TEXT, insertcolor=TEXT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=6)
    style.map("TEntry", bordercolor=[("focus", ACCENT)])
    style.configure("TCombobox", fieldbackground="#FFFFFF", foreground=TEXT, padding=5,
                    arrowcolor=TEXT, bordercolor=BORDER)
    style.map("TCombobox", fieldbackground=[("readonly", SURFACE)], foreground=[("readonly", TEXT)],
              selectbackground=[("readonly", SURFACE)], selectforeground=[("readonly", TEXT)])
    style.configure("TButton", background="#FFFFFF", foreground=TEXT, bordercolor=BORDER, padding=(11, 7))
    style.map("TButton", background=[("active", SURFACE), ("disabled", SURFACE)],
              foreground=[("disabled", MUTED)])
    style.configure("Primary.TButton", background=ACCENT, foreground="#ffffff", bordercolor=ACCENT,
                    padding=(13, 8), font=("Segoe UI", 10, "bold"))
    style.map("Primary.TButton", background=[("active", "#047857"), ("disabled", SURFACE)],
              foreground=[("disabled", MUTED)])
    style.configure("Nav.TButton", background=SURFACE, foreground=TEXT, borderwidth=0, relief="flat",
                    anchor="w", padding=(12, 10), font=("Segoe UI", 10))
    style.map("Nav.TButton", background=[("active", SURFACE_ALT), ("focus", SURFACE_ALT)],
              foreground=[("active", TEXT), ("focus", TEXT)])
    style.configure("Active.Nav.TButton", background="#ECFDF5", foreground="#047857", borderwidth=0,
                    relief="flat", anchor="w", padding=(12, 10), font=("Segoe UI", 10, "bold"))
    style.map("Active.Nav.TButton", background=[("active", "#D1FAE5"), ("focus", "#ECFDF5")],
              foreground=[("active", "#047857"), ("focus", "#047857")])
    style.configure("TNotebook", background=BACKGROUND, borderwidth=0, tabmargins=0)
    style.configure("TNotebook.Tab", background=SURFACE, foreground=MUTED, padding=(18, 10),
                    bordercolor=BORDER, font=("Segoe UI", 10, "bold"))
    style.map("TNotebook.Tab", background=[("selected", "#FFFFFF"), ("active", SURFACE_ALT)],
              foreground=[("selected", ACCENT), ("active", TEXT)])
    style.configure("Vertical.TScrollbar", background=SURFACE_ALT, troughcolor=BACKGROUND,
                    bordercolor=BACKGROUND, arrowcolor=MUTED)
    style.layout("Hidden.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
    style.layout("Hidden.TNotebook.Tab", [])


def scrollable_page(parent: ttk.Frame) -> ttk.Frame:
    """Return a vertically scrollable content frame that resizes with its tab."""
    shell = ttk.Frame(parent)
    shell.pack(fill="both", expand=True)
    canvas = tk.Canvas(shell, background=BACKGROUND, highlightthickness=0, borderwidth=0)
    scrollbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
    content = ttk.Frame(canvas)
    window_id = canvas.create_window((0, 0), window=content, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def update_scroll_region(_event=None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))

    def update_content_width(event) -> None:
        canvas.itemconfigure(window_id, width=event.width)

    def is_page_widget(widget) -> bool:
        while widget is not None:
            if widget is content:
                return True
            widget = getattr(widget, "master", None)
        return False

    def scroll_page(event) -> None:
        if not is_page_widget(event.widget):
            return
        # Text previews keep their own wheel behavior; all other controls scroll the page.
        if isinstance(event.widget, tk.Text):
            return
        if getattr(event, "num", None) == 4:
            units = -1
        elif getattr(event, "num", None) == 5:
            units = 1
        else:
            delta = getattr(event, "delta", 0)
            units = -int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
        canvas.yview_scroll(units, "units")

    def keep_focus_visible(event) -> None:
        focused_widget = event.widget
        if not is_page_widget(focused_widget) or canvas.focus_get() is not focused_widget:
            return

        def reveal() -> None:
            try:
                if not focused_widget.winfo_exists() or canvas.focus_get() is not focused_widget:
                    return
                canvas.update_idletasks()
                top = canvas.canvasy(0)
                bottom = top + canvas.winfo_height()
                widget_top = focused_widget.winfo_rooty() - canvas.winfo_rooty() + top
                widget_bottom = widget_top + focused_widget.winfo_height()
                bounds = canvas.bbox("all")
                if not bounds:
                    return
                content_height = max(1, bounds[3] - bounds[1])
                if widget_top < top:
                    canvas.yview_moveto(max(0, widget_top) / content_height)
                elif widget_bottom > bottom:
                    canvas.yview_moveto(max(0, widget_bottom - canvas.winfo_height()) / content_height)
            except tk.TclError:
                # A control may be destroyed between FocusIn and this idle callback.
                return

        canvas.after_idle(reveal)

    content.bind("<Configure>", update_scroll_region)
    canvas.bind("<Configure>", update_content_width)
    # bind_all lets scrolling work while the pointer is over an embedded control.
    # Each tab handler checks widget ancestry, so only the page under the pointer moves.
    for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        canvas.bind_all(sequence, scroll_page, add="+")
    canvas.bind_all("<FocusIn>", keep_focus_visible, add="+")
    return content


def main() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"Tkinter could not open a window ({exc}). Run this command from a desktop session.")
        return

    apply_theme(root)
    root.title("getonmylevel | Skills and agents")
    root.geometry("1120x820")
    root.minsize(760, 620)
    app_shell = ttk.Frame(root)
    app_shell.pack(fill="both", expand=True)
    sidebar = ttk.Frame(app_shell, style="Sidebar.TFrame", width=214, padding=(18, 22, 14, 18))
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)
    ttk.Frame(app_shell, style="SidebarRule.TFrame", width=1).pack(side="left", fill="y")
    workspace = ttk.Frame(app_shell)
    workspace.pack(side="left", fill="both", expand=True)

    brand_row = ttk.Frame(sidebar, style="Sidebar.TFrame")
    brand_row.pack(fill="x", pady=(0, 20))
    brand_mark = tk.Label(brand_row, text="g", bg=ACCENT, fg="#FFFFFF", font=("Segoe UI", 15, "bold"),
                         width=2, height=1)
    brand_mark.pack(side="left", padx=(0, 10))
    brand_text = ttk.Frame(brand_row, style="Sidebar.TFrame")
    brand_text.pack(side="left", fill="x", expand=True)
    ttk.Label(brand_text, text="getonmylevel", style="Sidebar.TLabel", font=("Segoe UI", 12, "bold")).pack(anchor="w")
    ttk.Label(brand_text, text="Codex toolkit", style="SidebarMuted.TLabel", font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))
    ttk.Separator(sidebar, orient="horizontal").pack(fill="x", pady=(0, 18))
    ttk.Label(sidebar, text="WORKSPACE", style="SidebarMuted.TLabel", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 8))

    notebook = ttk.Notebook(workspace, style="Hidden.TNotebook", padding=0)
    notebook.pack(fill="both", expand=True)
    skills_tab = ttk.Frame(notebook, style="Surface.TFrame")
    agents_tab = ttk.Frame(notebook, style="Surface.TFrame")
    notebook.add(skills_tab, text="Skills & installation")
    notebook.add(agents_tab, text="Agents")

    navigation = []
    navigation_buttons = []

    def select_page(index: int) -> None:
        notebook.select(index)
        for current, (bar, button) in enumerate(navigation):
            selected = current == index
            bar.configure(style="NavAccent.TFrame" if selected else "SidebarRule.TFrame")
            button.configure(style="Active.Nav.TButton" if selected else "Nav.TButton")

    for index, label in enumerate(("Skills & installation", "Agent roles")):
        row = ttk.Frame(sidebar, style="Sidebar.TFrame")
        row.pack(fill="x", pady=2)
        bar = ttk.Frame(row, style="SidebarRule.TFrame", width=3)
        bar.pack(side="left", fill="y", padx=(0, 7))
        button = ttk.Button(row, text=label, style="Nav.TButton", takefocus=True,
                            command=lambda page=index: select_page(page))
        button.pack(side="left", fill="x", expand=True)
        button.bind("<Up>", lambda _event, page=index: (navigation_buttons[(page - 1) % 2].focus_set(), "break")[1])
        button.bind("<Down>", lambda _event, page=index: (navigation_buttons[(page + 1) % 2].focus_set(), "break")[1])
        navigation.append((bar, button))
        navigation_buttons.append(button)
    ttk.Frame(sidebar, style="Sidebar.TFrame").pack(fill="both", expand=True)
    ttk.Separator(sidebar, orient="horizontal").pack(fill="x", pady=(10, 10))
    ttk.Label(sidebar, text="Skills and focused agent roles\nfor your Codex workspace.", style="SidebarMuted.TLabel",
              wraplength=175, justify="left", font=("Segoe UI", 9)).pack(anchor="w")
    select_page(0)
    root.bind("<Alt-Key-1>", lambda _event: (select_page(0), "break")[1])
    root.bind("<Alt-Key-2>", lambda _event: (select_page(1), "break")[1])
    switch_page = lambda _event: (select_page(1 if notebook.index("current") == 0 else 0), "break")[1]
    root.bind("<Control-Tab>", switch_page)
    root.bind("<Control-Shift-Tab>", switch_page)

    from agents_gui import AgentConfigurator
    from install_gui import Installer

    installer = Installer(root, parent=scrollable_page(skills_tab), configure_window=False)
    try:
        AgentConfigurator(root, parent=scrollable_page(agents_tab), close_command=installer.close,
                          configure_window=False)
    except Exception as exc:
        # Keep the installer available if optional agent templates cannot load.
        messagebox.showerror("Unable to load agent templates", str(exc), parent=root)

    root.protocol("WM_DELETE_WINDOW", installer.close)
    root.mainloop()


if __name__ == "__main__":
    main()
