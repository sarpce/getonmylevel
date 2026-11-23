"""Unified desktop interface for skill installation and agent setup."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont, messagebox, ttk


# Color roles. Pages use these names instead of literal values so the shell,
# option column, and review pane stay visually consistent.
BACKGROUND = "#FFFFFF"      # option column and cards
SIDEBAR = "#F3F4F6"         # navigation rail
ASIDE = "#F8F9FB"           # review pane
SURFACE = "#F3F4F6"         # read-only fields, hover fills
SURFACE_ALT = "#E5E7EB"     # pressed and hover fills on tinted surfaces
BORDER = "#DDE1E6"
BORDER_STRONG = "#C4CAD2"
TEXT = "#16181D"
MUTED = "#5F6672"           # >= 4.5:1 on every surface above
ACCENT = "#047857"          # >= 4.5:1 with white text
ACCENT_HOVER = "#065F46"
ACCENT_TINT = "#ECFDF5"
ACCENT_TINT_STRONG = "#D1FAE5"
SELECTION = "#A7F3D0"
DANGER = "#B42318"
DANGER_TINT = "#FEF3F2"

FONT = "Segoe UI"
MONO = "Consolas"  # replaced by the first installed monospace family in apply_theme
TITLE_FONT = (FONT, 18, "bold")
SECTION_FONT = (FONT, 11, "bold")
BODY_FONT = (FONT, 10)
STRONG_FONT = (FONT, 10, "bold")
SMALL_FONT = (FONT, 9)
OVERLINE_FONT = (FONT, 8, "bold")

PAGE_PADDING = (28, 24, 28, 28)
ASIDE_WIDTH = 344


def _pick_mono(root: tk.Tk) -> str:
    families = set(tkfont.families(root))
    for family in ("Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono", "Liberation Mono"):
        if family in families:
            return family
    return "TkFixedFont"


def apply_theme(root: tk.Tk) -> None:
    global MONO
    MONO = _pick_mono(root)
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    root.configure(background=BACKGROUND)
    root.option_add("*Text.background", BACKGROUND)
    root.option_add("*Text.foreground", TEXT)
    root.option_add("*Text.insertBackground", TEXT)
    root.option_add("*Text.selectBackground", SELECTION)
    root.option_add("*Text.selectForeground", TEXT)
    root.option_add("*TCombobox*Listbox.background", BACKGROUND)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_TINT_STRONG)
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)

    style.configure(".", background=BACKGROUND, foreground=TEXT, font=BODY_FONT, focuscolor=ACCENT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, troughcolor=SURFACE)
    style.configure("TFrame", background=BACKGROUND)
    style.configure("Surface.TFrame", background=BACKGROUND)
    style.configure("Rule.TFrame", background=BORDER)
    style.configure("TLabel", background=BACKGROUND, foreground=TEXT)
    style.configure("Muted.TLabel", background=BACKGROUND, foreground=MUTED)
    style.configure("Title.TLabel", background=BACKGROUND, foreground=TEXT, font=TITLE_FONT)
    style.configure("Section.TLabel", background=BACKGROUND, foreground=TEXT, font=SECTION_FONT)
    style.configure("Step.TLabel", background=ACCENT_TINT, foreground=ACCENT, font=OVERLINE_FONT,
                    anchor="center", padding=(6, 1))
    style.configure("Field.TLabel", background=BACKGROUND, foreground=MUTED, font=SMALL_FONT)

    # Navigation rail.
    style.configure("Sidebar.TFrame", background=SIDEBAR)
    style.configure("Sidebar.TLabel", background=SIDEBAR, foreground=TEXT)
    style.configure("SidebarMuted.TLabel", background=SIDEBAR, foreground=MUTED)
    style.configure("SidebarRule.TFrame", background=SIDEBAR)
    style.configure("NavAccent.TFrame", background=ACCENT)
    style.configure("Nav.TButton", background=SIDEBAR, foreground=TEXT, borderwidth=0, relief="flat",
                    anchor="w", padding=(12, 9), font=BODY_FONT, focuscolor=ACCENT)
    style.map("Nav.TButton", background=[("active", SURFACE_ALT), ("focus", SURFACE_ALT)],
              foreground=[("active", TEXT), ("focus", TEXT)])
    style.configure("Active.Nav.TButton", background=BACKGROUND, foreground=ACCENT, borderwidth=0,
                    relief="flat", anchor="w", padding=(12, 9), font=STRONG_FONT, focuscolor=ACCENT)
    style.map("Active.Nav.TButton", background=[("active", BACKGROUND), ("focus", BACKGROUND)],
              foreground=[("active", ACCENT_HOVER), ("focus", ACCENT_HOVER)])

    # Review pane.
    style.configure("Aside.TFrame", background=ASIDE)
    style.configure("Aside.TLabel", background=ASIDE, foreground=TEXT)
    style.configure("AsideMuted.TLabel", background=ASIDE, foreground=MUTED, font=SMALL_FONT)
    style.configure("AsideTitle.TLabel", background=ASIDE, foreground=TEXT, font=SECTION_FONT)
    style.configure("AsideOverline.TLabel", background=ASIDE, foreground=MUTED, font=OVERLINE_FONT)
    style.configure("Summary.TLabel", background=ACCENT_TINT, foreground=ACCENT_HOVER, font=STRONG_FONT,
                    padding=(10, 7))

    # Selectable tiles. The tile frame draws the selected state, so the
    # Checkbutton keeps keyboard semantics without the theme's small indicator.
    style.configure("Card.TFrame", background=BACKGROUND)
    style.configure("Selected.Card.TFrame", background=ACCENT_TINT)
    style.configure("Card.TLabel", background=BACKGROUND, foreground=TEXT)
    style.configure("CardMuted.TLabel", background=BACKGROUND, foreground=MUTED, font=SMALL_FONT)
    style.configure("Selected.CardMuted.TLabel", background=ACCENT_TINT, foreground=MUTED, font=SMALL_FONT)
    style.configure("CardMarker.TLabel", background=BACKGROUND, foreground=BORDER_STRONG, font=(FONT, 12, "bold"))
    style.configure("Selected.CardMarker.TLabel", background=ACCENT_TINT, foreground=ACCENT, font=(FONT, 12, "bold"))
    tile_layout = [("Checkbutton.padding", {"sticky": "nswe", "children": [
        ("Checkbutton.focus", {"sticky": "nswe", "children": [("Checkbutton.label", {"sticky": "nswe"})]})]})]
    for name, fill, hover in (("Card.TCheckbutton", BACKGROUND, BACKGROUND),
                              ("Selected.Card.TCheckbutton", ACCENT_TINT, ACCENT_TINT)):
        style.layout(name, tile_layout)
        style.configure(name, background=fill, foreground=TEXT, padding=(2, 3), font=STRONG_FONT, focuscolor=ACCENT)
        style.map(name, background=[("active", hover)], foreground=[("disabled", MUTED)])

    style.configure("TCheckbutton", background=BACKGROUND, foreground=TEXT, padding=(2, 4),
                    indicatorbackground=BACKGROUND, indicatorforeground=ACCENT, indicatormargin=(0, 0, 6, 0))
    style.map("TCheckbutton", background=[("active", BACKGROUND)], foreground=[("disabled", MUTED)],
              indicatorbackground=[("disabled", SURFACE), ("pressed", ACCENT_TINT)])
    style.configure("TRadiobutton", background=BACKGROUND, foreground=TEXT, padding=(2, 4),
                    indicatorbackground=BACKGROUND, indicatorforeground=ACCENT, indicatormargin=(0, 0, 6, 0))
    style.map("TRadiobutton", background=[("active", BACKGROUND)], foreground=[("disabled", MUTED)],
              indicatorbackground=[("disabled", SURFACE), ("pressed", ACCENT_TINT)])

    # Segmented control: radio semantics, button appearance.
    style.layout("Segment.TRadiobutton", [("Radiobutton.padding", {"sticky": "nswe", "children": [
        ("Radiobutton.focus", {"sticky": "nswe", "children": [("Radiobutton.label", {"sticky": "nswe"})]})]})])
    style.configure("Segment.TRadiobutton", background=SURFACE, foreground=TEXT, padding=(14, 7),
                    anchor="center", font=BODY_FONT, focuscolor=ACCENT)
    style.map("Segment.TRadiobutton",
              background=[("selected", BACKGROUND), ("active", SURFACE_ALT)],
              foreground=[("disabled", MUTED), ("selected", ACCENT)],
              font=[("selected", STRONG_FONT)])

    style.configure("TEntry", fieldbackground=BACKGROUND, foreground=TEXT, insertcolor=TEXT,
                    bordercolor=BORDER_STRONG, lightcolor=BORDER_STRONG, darkcolor=BORDER_STRONG, padding=6)
    style.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)])
    style.configure("TCombobox", fieldbackground=BACKGROUND, foreground=TEXT, padding=5, arrowcolor=MUTED,
                    bordercolor=BORDER_STRONG, lightcolor=BORDER_STRONG, darkcolor=BORDER_STRONG, background=BACKGROUND)
    style.map("TCombobox", fieldbackground=[("disabled", SURFACE), ("readonly", BACKGROUND)],
              foreground=[("disabled", MUTED), ("readonly", TEXT)],
              bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
              selectbackground=[("readonly", BACKGROUND)], selectforeground=[("readonly", TEXT)])

    style.configure("TButton", background=BACKGROUND, foreground=TEXT, bordercolor=BORDER_STRONG,
                    lightcolor=BACKGROUND, darkcolor=BACKGROUND, padding=(12, 6), focuscolor=ACCENT)
    style.map("TButton", background=[("disabled", SURFACE), ("pressed", SURFACE_ALT), ("active", SURFACE)],
              foreground=[("disabled", MUTED)], bordercolor=[("focus", ACCENT)])
    style.configure("Primary.TButton", background=ACCENT, foreground="#FFFFFF", bordercolor=ACCENT,
                    lightcolor=ACCENT, darkcolor=ACCENT, padding=(14, 9), font=STRONG_FONT, focuscolor="#FFFFFF")
    style.map("Primary.TButton", background=[("disabled", SURFACE_ALT), ("pressed", ACCENT_HOVER), ("active", ACCENT_HOVER)],
              foreground=[("disabled", MUTED)], bordercolor=[("disabled", SURFACE_ALT)],
              lightcolor=[("disabled", SURFACE_ALT), ("active", ACCENT_HOVER)],
              darkcolor=[("disabled", SURFACE_ALT), ("active", ACCENT_HOVER)])
    style.configure("Danger.TButton", background=ASIDE, foreground=DANGER, bordercolor="#F3C5C0",
                    lightcolor=ASIDE, darkcolor=ASIDE, padding=(12, 6), focuscolor=DANGER)
    style.map("Danger.TButton", background=[("disabled", ASIDE), ("pressed", "#FEE4E2"), ("active", DANGER_TINT)],
              foreground=[("disabled", MUTED)], bordercolor=[("disabled", BORDER), ("focus", DANGER)])
    style.configure("Quiet.TButton", background=ASIDE, foreground=MUTED, bordercolor=ASIDE,
                    lightcolor=ASIDE, darkcolor=ASIDE, padding=(10, 6), focuscolor=ACCENT)
    style.map("Quiet.TButton", background=[("pressed", SURFACE_ALT), ("active", SURFACE)],
              foreground=[("disabled", BORDER_STRONG), ("active", TEXT)])

    style.configure("TLabelframe", background=BACKGROUND, bordercolor=BORDER, padding=10)
    style.configure("TLabelframe.Label", background=BACKGROUND, foreground=TEXT, font=STRONG_FONT)
    style.configure("TSeparator", background=BORDER)
    style.configure("Vertical.TScrollbar", background=SURFACE_ALT, troughcolor=BACKGROUND, bordercolor=BACKGROUND,
                    lightcolor=SURFACE_ALT, darkcolor=SURFACE_ALT, arrowcolor=MUTED, gripcount=0, arrowsize=12)
    style.map("Vertical.TScrollbar", background=[("active", BORDER_STRONG)])
    style.configure("TNotebook", background=BACKGROUND, borderwidth=0, tabmargins=0)
    style.layout("Hidden.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
    style.layout("Hidden.TNotebook.Tab", [])


# Shared page building blocks -------------------------------------------------

def page_header(parent, title: str, intro: str) -> ttk.Label:
    """Pack a page title and intro; return the intro label so callers can change its text."""
    ttk.Label(parent, text=title, style="Title.TLabel").pack(anchor="w")
    intro_label = ttk.Label(parent, text=intro, style="Muted.TLabel", wraplength=720, justify="left")
    intro_label.pack(anchor="w", fill="x", pady=(4, 6))
    fit_wrap(parent, intro_label, inset=PAGE_PADDING[0] + PAGE_PADDING[2])
    return intro_label


def section(parent, step: str, title: str, description: str | None = None) -> ttk.Frame:
    """Pack a numbered section with a rule above it and return its body frame."""
    ttk.Frame(parent, style="Rule.TFrame", height=1).pack(fill="x", pady=(20, 18))
    header = ttk.Frame(parent)
    header.pack(fill="x")
    ttk.Label(header, text=step, style="Step.TLabel").pack(side="left", padx=(0, 10))
    ttk.Label(header, text=title, style="Section.TLabel").pack(side="left")
    if description:
        label = ttk.Label(parent, text=description, style="Muted.TLabel", wraplength=720, justify="left")
        label.pack(anchor="w", fill="x", pady=(6, 0))
        fit_wrap(parent, label, inset=PAGE_PADDING[0] + PAGE_PADDING[2])
    body = ttk.Frame(parent)
    body.pack(fill="x", pady=(12, 0))
    return body


def fit_wrap(container, label, inset: int = 0, minimum: int = 220) -> None:
    """Keep a label's wraplength in step with its container width."""
    container.bind("<Configure>", lambda event: label.configure(wraplength=max(minimum, event.width - inset)), add="+")


def segmented(parent, variable: tk.StringVar, options, command) -> list[ttk.Radiobutton]:
    """Pack a segmented radio control and return its buttons (arrow keys move between them)."""
    frame = tk.Frame(parent, background=BORDER, highlightthickness=0, padx=1, pady=1)
    frame.pack(anchor="w")
    buttons = []
    for value, label in options:
        button = ttk.Radiobutton(frame, text=label, value=value, variable=variable, command=command,
                                 style="Segment.TRadiobutton", takefocus=True)
        button.pack(side="left", padx=(0 if not buttons else 1, 0))
        buttons.append(button)

    def move(offset: int) -> str:
        enabled = [b for b in buttons if not b.instate(["disabled"])]
        current = next((b for b in enabled if str(b.cget("value")) == variable.get()), None)
        if not enabled:
            return "break"
        index = (enabled.index(current) + offset) % len(enabled) if current in enabled else 0
        enabled[index].invoke()
        enabled[index].focus_set()
        return "break"

    for button in buttons:
        for key, offset in (("<Left>", -1), ("<Up>", -1), ("<Right>", 1), ("<Down>", 1)):
            button.bind(key, lambda _event, step=offset: move(step))
    return buttons


def tile(parent) -> tuple[tk.Frame, ttk.Frame]:
    """Return a bordered tile and its padded body; the caller places the tile."""
    card = tk.Frame(parent, background=BACKGROUND, highlightthickness=1,
                    highlightbackground=BORDER, highlightcolor=BORDER)
    body = ttk.Frame(card, style="Card.TFrame", padding=(14, 12))
    body.pack(fill="both", expand=True)
    return card, body


def set_tile_selected(card: tk.Frame, selected: bool) -> None:
    color = ACCENT if selected else BORDER
    card.configure(highlightbackground=color, highlightcolor=color,
                   background=ACCENT_TINT if selected else BACKGROUND)


def preview_text(parent, height: int) -> tk.Text:
    """Pack a read-only, scrollable monospace preview filling the remaining space."""
    frame = tk.Frame(parent, background=BACKGROUND, highlightthickness=1,
                     highlightbackground=BORDER, highlightcolor=BORDER)
    frame.pack(fill="both", expand=True)
    text = tk.Text(frame, height=height, wrap="word", state="disabled", borderwidth=0, highlightthickness=0,
                   padx=12, pady=10, font=(MONO, 9), spacing1=1, spacing3=1, background=BACKGROUND, foreground=TEXT,
                   cursor="arrow", takefocus=True)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)
    return text


def review_header(parent, title: str, note: str) -> ttk.Label:
    """Pack the review pane header and return its summary label."""
    ttk.Label(parent, text="REVIEW", style="AsideOverline.TLabel").pack(anchor="w")
    ttk.Label(parent, text=title, style="AsideTitle.TLabel").pack(anchor="w", pady=(2, 2))
    ttk.Label(parent, text=note, style="AsideMuted.TLabel", wraplength=ASIDE_WIDTH - 48,
              justify="left").pack(anchor="w", pady=(0, 12))
    summary = ttk.Label(parent, text="", style="Summary.TLabel", wraplength=ASIDE_WIDTH - 68, justify="left")
    summary.pack(fill="x", pady=(0, 10))
    return summary


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


def workbench(tab: ttk.Frame) -> tuple[ttk.Frame, ttk.Frame]:
    """Split a tab into a scrollable option column and a fixed review pane."""
    aside = ttk.Frame(tab, style="Aside.TFrame", width=ASIDE_WIDTH, padding=(20, 24, 20, 20))
    aside.pack(side="right", fill="y")
    aside.pack_propagate(False)
    ttk.Frame(tab, style="Rule.TFrame", width=1).pack(side="right", fill="y")
    options = ttk.Frame(tab)
    options.pack(side="left", fill="both", expand=True)
    return scrollable_page(options), aside


def main() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"Tkinter could not open a window ({exc}). Run this command from a desktop session.")
        return

    apply_theme(root)
    root.title("getonmylevel | Skills and agents")
    root.geometry("1280x840")
    root.minsize(1040, 640)
    app_shell = ttk.Frame(root)
    app_shell.pack(fill="both", expand=True)
    sidebar = ttk.Frame(app_shell, style="Sidebar.TFrame", width=212, padding=(16, 22, 16, 18))
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)
    ttk.Frame(app_shell, style="Rule.TFrame", width=1).pack(side="left", fill="y")
    workspace = ttk.Frame(app_shell)
    workspace.pack(side="left", fill="both", expand=True)

    brand_row = ttk.Frame(sidebar, style="Sidebar.TFrame")
    brand_row.pack(fill="x", pady=(0, 24))
    brand_mark = tk.Label(brand_row, text="g", bg=ACCENT, fg="#FFFFFF", font=(FONT, 14, "bold"),
                          width=2, height=1)
    brand_mark.pack(side="left", padx=(0, 10))
    brand_text = ttk.Frame(brand_row, style="Sidebar.TFrame")
    brand_text.pack(side="left", fill="x", expand=True)
    ttk.Label(brand_text, text="getonmylevel", style="Sidebar.TLabel", font=(FONT, 12, "bold")).pack(anchor="w")
    ttk.Label(brand_text, text="Skills and agent roles", style="SidebarMuted.TLabel", font=SMALL_FONT).pack(anchor="w")
    ttk.Label(sidebar, text="SETUP", style="SidebarMuted.TLabel", font=OVERLINE_FONT).pack(anchor="w", padx=(4, 0), pady=(0, 6))

    notebook = ttk.Notebook(workspace, style="Hidden.TNotebook", padding=0)
    notebook.pack(fill="both", expand=True)
    skills_tab = ttk.Frame(notebook, style="Surface.TFrame")
    agents_tab = ttk.Frame(notebook, style="Surface.TFrame")
    notebook.add(skills_tab, text="Skills & tools")
    notebook.add(agents_tab, text="Agent roles")

    navigation = []
    navigation_buttons = []

    def select_page(index: int) -> None:
        notebook.select(index)
        for current, (bar, button) in enumerate(navigation):
            selected = current == index
            bar.configure(style="NavAccent.TFrame" if selected else "SidebarRule.TFrame")
            button.configure(style="Active.Nav.TButton" if selected else "Nav.TButton")

    for index, label in enumerate(("Skills & tools", "Agent roles")):
        row = ttk.Frame(sidebar, style="Sidebar.TFrame")
        row.pack(fill="x", pady=1)
        bar = ttk.Frame(row, style="SidebarRule.TFrame", width=3)
        bar.pack(side="left", fill="y")
        button = ttk.Button(row, text=label, style="Nav.TButton", takefocus=True,
                            command=lambda page=index: select_page(page))
        button.pack(side="left", fill="x", expand=True)
        button.bind("<Up>", lambda _event, page=index: (navigation_buttons[(page - 1) % 2].focus_set(), "break")[1])
        button.bind("<Down>", lambda _event, page=index: (navigation_buttons[(page + 1) % 2].focus_set(), "break")[1])
        navigation.append((bar, button))
        navigation_buttons.append(button)
    ttk.Frame(sidebar, style="Sidebar.TFrame").pack(fill="both", expand=True)
    ttk.Label(sidebar, text="Codex · Claude Code · GitHub Copilot · OpenCode", style="SidebarMuted.TLabel",
              wraplength=176, justify="left", font=SMALL_FONT).pack(anchor="w", padx=(4, 0))
    ttk.Label(sidebar, text="Alt+1 / Alt+2 or Ctrl+Tab to switch", style="SidebarMuted.TLabel",
              wraplength=176, justify="left", font=SMALL_FONT).pack(anchor="w", padx=(4, 0), pady=(6, 0))
    select_page(0)
    root.bind("<Alt-Key-1>", lambda _event: (select_page(0), "break")[1])
    root.bind("<Alt-Key-2>", lambda _event: (select_page(1), "break")[1])
    switch_page = lambda _event: (select_page(1 if notebook.index("current") == 0 else 0), "break")[1]
    root.bind("<Control-Tab>", switch_page)
    root.bind("<Control-Shift-Tab>", switch_page)

    from agents_gui import AgentConfigurator
    from install_gui import Installer

    skills_page, skills_aside = workbench(skills_tab)
    installer = Installer(root, parent=skills_page, aside=skills_aside, configure_window=False)
    agents_page, agents_aside = workbench(agents_tab)
    try:
        AgentConfigurator(root, parent=agents_page, aside=agents_aside, close_command=installer.close,
                          configure_window=False)
    except Exception as exc:
        # Keep the installer available if optional agent templates cannot load.
        messagebox.showerror("Unable to load agent templates", str(exc), parent=root)

    root.protocol("WM_DELETE_WINDOW", installer.close)
    root.mainloop()


if __name__ == "__main__":
    main()
