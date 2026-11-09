#!/usr/bin/env python3
"""
TaskSplit - a LiveSplit-style overlay for your daily tasks.

This module is the engine. Run the app from  mainmenu.py  (python mainmenu.py).
Needs:  Python 3.8+ (tkinter is included). Optional: pip install pynput
        for global hotkeys that work while a game/app has focus.

Overlay controls
  Click the big timer / Ctrl+Alt+P : Start, click again to stop (click to resume)
  Split button / Ctrl+Alt+Space    : Finish the current task, move to the next
  Undo button  / Ctrl+Alt+Z        : Undo the last split
  Reset button / Ctrl+Alt+R        : Reset the run (button asks you to confirm)
  Right-click anywhere             : Menu (edit tasks, opacity, quit to menu...)
  Drag the header or task list     : Move the window
"""
import datetime
import json
import math
import os
import queue
import time
import tkinter as tk
from tkinter import font as tkfont
from types import SimpleNamespace

# ---------------------------------------------------------------- config
APP_DIR = os.path.join(os.path.expanduser("~"), ".tasksplit")
DATA_FILE = os.path.join(APP_DIR, "data.json")

W = 300            # base overlay width (everything is drawn at this scale, then zoomed)
HEADER_H = 48
ROW_H = 28
FOOT_H = 92
TIMER_H = 84
BTN = 26
BTN_GAP = 4
MAX_ROWS = 10

# overlay size presets -> zoom factor
SIZES = {"Small": 0.8, "Medium": 1.0, "Large": 1.3, "XL": 1.6}

THEMES = {
    "dark": {
        "dark": True,
        "bg": "#0d0d0d", "text": "#f2f2f2", "dim": "#8c8c8c", "sep": "#1b1b1b",
        "green": "#2ecc40", "red": "#e0301e", "gold": "#ffd500",
        "finish": "#4aa3ff", "paused": "#9a9a9a",
        "head_top": "#2d2d2d", "head_bot": "#151515", "head_line": "#2a2a2a",
        "cur_top": "#3466cc", "cur_bot": "#1a3a85", "cur_text": "#ffffff",
        "footer_line": "#2a2a2a", "upcoming": "#cfcfcf", "edge": "#2a2a2a",
        "accent": "#2f5fc4", "accent_edge": "#4a7be0", "accent_text": "#ffffff",
        "accent_hover": "#3a72e6",
        "btn_fill": "#161616", "btn_edge": "#262626", "btn_hover": "#2a2a2a",
        "btn_edge_hover": "#3a3a3a", "btn_press": "#1a1a1a",
        "btn_off_fill": "#111111", "btn_off_edge": "#1c1c1c", "btn_off_icon": "#333333",
        "icon": "#8c8c8c", "icon_hover": "#ffffff",
        "arm_fill": "#5c1b14", "arm_edge": "#b32618", "arm_icon": "#ff7a6b",
        # editor / dialogs
        "ed_bg": "#141414", "ed_panel": "#1b1b1b", "ed_edge": "#2a2a2a",
        "ed_in": "#0d0d0d", "ed_link": "#9ab8ff", "ed_muted": "#6e6e6e",
        "ed_btn": "#252525", "ed_btn_hover": "#333333", "ed_panel_hover": "#242424",
    },
    "light": {
        "dark": False,
        "bg": "#f4f5f7", "text": "#1b1d21", "dim": "#6b7280", "sep": "#e3e5e9",
        "green": "#1f9d3a", "red": "#d12a1a", "gold": "#d4a000",
        "finish": "#1e6fd9", "paused": "#7a7f88",
        "head_top": "#ffffff", "head_bot": "#e8eaee", "head_line": "#d5d8de",
        "cur_top": "#4a86ec", "cur_bot": "#2f64c9", "cur_text": "#ffffff",
        "footer_line": "#d5d8de", "upcoming": "#3a3d44", "edge": "#c9ccd3",
        "accent": "#2f6fe0", "accent_edge": "#1f55b8", "accent_text": "#ffffff",
        "accent_hover": "#4a82f0",
        "btn_fill": "#ffffff", "btn_edge": "#d0d3da", "btn_hover": "#eceef2",
        "btn_edge_hover": "#a9aeb8", "btn_press": "#e0e3e8",
        "btn_off_fill": "#eeeff2", "btn_off_edge": "#e1e3e8", "btn_off_icon": "#c3c6cd",
        "icon": "#6b7280", "icon_hover": "#000000",
        "arm_fill": "#fbe3df", "arm_edge": "#d9534a", "arm_icon": "#c0301f",
        "ed_bg": "#f4f5f7", "ed_panel": "#ffffff", "ed_edge": "#d5d8de",
        "ed_in": "#ffffff", "ed_link": "#2f64c9", "ed_muted": "#9aa0aa",
        "ed_btn": "#e3e6eb", "ed_btn_hover": "#d5d9e0", "ed_panel_hover": "#eef0f4",
    },
}

MODES = ("casual", "countdown", "normal")
MODE_INFO = {
    "casual": ("Casual", "Just a timer. Tracks how long you've studied."),
    "countdown": ("Countdown", "Pick a time. Counts down and stops at 0:00."),
    "normal": ("Normal", "Task splits. Work through a list of tasks."),
}

DEFAULT_TASKS = [
    {"name": "Morning routine", "est": 1800},
    {"name": "Study session", "est": 3600},
    {"name": "Project work", "est": 5400},
    {"name": "Exercise", "est": 2700},
    {"name": "Read / wind down", "est": 1200},
]


# ---------------------------------------------------------------- helpers
def fmt(sec, signed=False):
    neg = sec < 0
    t = int(abs(sec))
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    base = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
    if signed:
        return ("−" if neg else "+") + base
    return base


def lerp(c0, c1, t):
    a = [int(c0[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def vgrad(c, x0, y0, x1, y1, c0, c1):
    """Vertical gradient on canvas `c` (floats are fine)."""
    h = max(1, y1 - y0)
    y = y0
    while y < y1:
        c.create_rectangle(x0, y, x1, min(y + 2, y1), outline="",
                           fill=lerp(c0, c1, (y - y0) / h))
        y += 2


def make_fonts(scale=1.0):
    """All fonts the app uses. Call after a Tk root exists."""
    fams = set(tkfont.families())
    base = next((f for f in ("Segoe UI", "SF Pro Display", "Helvetica Neue",
                             "DejaVu Sans", "Arial") if f in fams), "TkDefaultFont")

    def F(size, weight="normal"):
        return tkfont.Font(family=base, size=max(6, int(round(size * scale))), weight=weight)

    return SimpleNamespace(
        title=F(11, "bold"), sub=F(8), row=F(10), rowb=F(10, "bold"),
        big=F(30, "bold"), bigdec=F(17, "bold"), seg=F(13), lbl=F(9),
        h1=F(16, "bold"), menu=F(13), clock=F(28, "bold"), clockdec=F(16, "bold"))


def dark_titlebar(win, dark=True):
    """Windows 10/11: match the native title bar to the theme (ignored elsewhere)."""
    try:
        import ctypes
        win.update()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        on = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(on), 4) == 0:
                break
    except Exception:
        pass


# ---------------------------------------------------------------- data
def default_data():
    return {
        "settings": {"theme": "dark", "size": "Medium", "opacity": 0.85},
        "library": [],      # [{"name", "title", "subtitle", "tasks": [{"name","est"}]}]
        "last": {"title": "Daily Tasks", "subtitle": "Any% Today",
                 "tasks": [dict(t) for t in DEFAULT_TASKS]},
        "last_casual": {"title": "Study Session"},
        "last_countdown": {"title": "Focus Session", "seconds": 1500},
        "best": {},         # best segment time per task name
        "pos": None,        # overlay window position
        "snapshot": None,   # run in progress (what the main menu's Continue loads)
    }


def load_data():
    d = default_data()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            # migrate the old single-list format
            if "tasks" in raw and "last" not in raw:
                raw["last"] = {"title": raw.get("title", "Daily Tasks"),
                               "subtitle": raw.get("subtitle", ""),
                               "tasks": raw["tasks"]}
            if "opacity" in raw:
                raw.setdefault("settings", {}).setdefault("opacity", raw["opacity"])
            for k in d:
                if k in raw:
                    if isinstance(d[k], dict) and isinstance(raw[k], dict):
                        d[k].update(raw[k])
                    else:
                        d[k] = raw[k]
    except Exception:
        pass
    if d["settings"].get("theme") not in THEMES:
        d["settings"]["theme"] = "dark"
    if d["settings"].get("size") not in SIZES:
        d["settings"]["size"] = "Medium"
    if not isinstance(d["library"], list):
        d["library"] = []
    return d


def save_data(d):
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
        os.replace(tmp, DATA_FILE)
    except Exception:
        pass


def get_snapshot():
    """The saved run in progress, or None if there isn't a usable one."""
    s = load_data().get("snapshot")
    try:
        if isinstance(s, dict):
            float(s.get("elapsed", 0))
            [float(x) for x in s.get("splits", [])]
            mode = s.get("mode", "normal")
            if mode == "normal":
                ok = (isinstance(s.get("tasks"), list) and bool(s["tasks"])
                      and all(isinstance(t, dict) and t.get("name") for t in s["tasks"]))
            elif mode == "casual":
                ok = True
            elif mode == "countdown":
                ok = float(s.get("duration", 0)) > 0
            else:
                ok = False
            if ok:
                return s
    except (TypeError, ValueError):
        pass
    return None


# ---------------------------------------------------------------- themed widgets
def _entry(parent, var, th, f, **kw):
    return tk.Entry(parent, textvariable=var, bg=th["ed_in"], fg=th["text"],
                    insertbackground=th["text"], relief="flat", font=f.row,
                    highlightthickness=1, highlightbackground=th["ed_edge"],
                    highlightcolor=th["cur_top"], **kw)


def _caption(parent, text, th, f, bg=None):
    return tk.Label(parent, text=text, bg=bg or th["ed_bg"], fg=th["dim"],
                    font=f.lbl, anchor="w")


def _ibtn(parent, text, cmd, th, f, hover=None):
    base = th["ed_muted"]
    hover = hover or th["text"]
    l = tk.Label(parent, text=text, width=2, bg=parent["bg"], fg=base,
                 font=f.rowb, cursor="hand2")
    l.bind("<Button-1>", lambda e: cmd())
    l.bind("<Enter>", lambda e: l.config(fg=hover))
    l.bind("<Leave>", lambda e: l.config(fg=base))
    return l


def _button(parent, text, cmd, fill, hover, fg, f, padx=20, pady=7):
    l = tk.Label(parent, text=text, bg=fill, fg=fg, font=f.rowb,
                 padx=padx, pady=pady, cursor="hand2")
    l.bind("<Button-1>", lambda e: cmd())
    l.bind("<Enter>", lambda e: l.config(bg=hover))
    l.bind("<Leave>", lambda e: l.config(bg=fill))
    return l


def _header(win, th, f, heading, sub):
    hdr = tk.Canvas(win, height=58, bg=th["ed_bg"], highlightthickness=0)
    hdr.pack(fill="x")

    def paint(e=None):
        hdr.delete("all")
        w = max(1, hdr.winfo_width())
        vgrad(hdr, 0, 0, w, 58, th["head_top"], th["head_bot"])
        hdr.create_text(18, 23, anchor="w", text=heading, font=f.title, fill=th["text"])
        hdr.create_text(18, 42, anchor="w", text=sub, font=f.sub, fill=th["dim"])
        hdr.create_line(0, 57, w, 57, fill=th["head_line"])

    hdr.bind("<Configure>", paint)
    return hdr


def _scroll_area(parent, win, th):
    wrap = tk.Frame(parent, bg=th["ed_panel"], highlightthickness=1,
                    highlightbackground=th["ed_edge"])
    cv = tk.Canvas(wrap, bg=th["ed_panel"], highlightthickness=0)
    cv.pack(fill="both", expand=True)
    inner = tk.Frame(cv, bg=th["ed_panel"])
    iid = cv.create_window(0, 0, anchor="nw", window=inner)
    inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
    cv.bind("<Configure>", lambda e: cv.itemconfigure(iid, width=e.width))

    def on_wheel(e):
        if getattr(e, "num", 0) == 4:
            d = -1
        elif getattr(e, "num", 0) == 5:
            d = 1
        else:
            d = -1 if e.delta > 0 else 1
        if inner.winfo_height() > cv.winfo_height():
            cv.yview_scroll(d, "units")

    for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        win.bind(ev, on_wheel)
    return wrap, cv, inner


def _place_window(win, root, ww, wh):
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    wh = min(wh, sh - 120)
    x = (sw - ww) // 2
    y = max(20, (sh - wh) // 2 - 20)
    win.geometry(f"{ww}x{wh}+{x}+{y}")


# ---------------------------------------------------------------- task editor
class TaskEditor:
    """Edit a task list. Used for 'Start New', opened library sets, and the
    overlay's right-click 'Edit tasks'. Has a Save-to-library button with a
    name + confirm/cancel step. on_confirm(title, subtitle, tasks) is called
    when the action button is pressed."""

    def __init__(self, root, th, f, title, subtitle, tasks, action_text, on_confirm,
                 heading="Edit Tasks", subheading="Name your list and set up your tasks"):
        self.root, self.th, self.f = root, th, f
        self.on_confirm = on_confirm
        self._closed = False
        self._status_job = None
        win = self.win = tk.Toplevel(root)
        win.title(heading)
        win.configure(bg=th["ed_bg"])
        win.attributes("-topmost", True)
        win.minsize(420, 500)
        _place_window(win, root, 430, 660)
        dark_titlebar(win, th["dark"])
        win.protocol("WM_DELETE_WINDOW", self.close)

        _header(win, th, f, heading, subheading)

        # footer first so it never gets squeezed out
        foot = tk.Frame(win, bg=th["ed_bg"])
        foot.pack(side="bottom", fill="x", padx=18, pady=16)
        self.btnrow = tk.Frame(foot, bg=th["ed_bg"])
        self.btnrow.pack(fill="x")

        body = tk.Frame(win, bg=th["ed_bg"])
        body.pack(fill="both", expand=True, padx=18, pady=(16, 0))

        self.title_var = tk.StringVar(value=title)
        self.sub_var = tk.StringVar(value=subtitle)
        _caption(body, "TITLE", th, f).pack(anchor="w")
        _entry(body, self.title_var, th, f).pack(fill="x", ipady=6, pady=(3, 12))
        _caption(body, "SUBTITLE  (shown after the date)", th, f).pack(anchor="w")
        _entry(body, self.sub_var, th, f).pack(fill="x", ipady=6, pady=(3, 18))

        top = tk.Frame(body, bg=th["ed_bg"])
        top.pack(fill="x")
        _caption(top, "TASKS", th, f).pack(side="left")
        _caption(top, "MIN = estimate for green / red", th, f).pack(side="right")

        add = tk.Label(body, text="+  Add task", bg=th["ed_panel"], fg=th["ed_link"],
                       font=f.rowb, pady=14, cursor="hand2",
                       highlightthickness=1, highlightbackground=th["ed_edge"])
        add.pack(side="bottom", fill="x", pady=(8, 0))
        add.bind("<Button-1>", lambda e: self.add_end())
        add.bind("<Enter>", lambda e: add.config(bg=th["ed_panel_hover"]))
        add.bind("<Leave>", lambda e: add.config(bg=th["ed_panel"]))

        wrap, self.cv, self.inner = _scroll_area(body, win, th)
        wrap.pack(fill="both", expand=True, pady=(6, 0))

        self.rows = []
        for t in tasks:
            est = f"{t['est'] / 60:g}" if t.get("est") else ""
            self.rows.append({"name": tk.StringVar(value=t.get("name", "")),
                              "min": tk.StringVar(value=est)})
        self.render()

        # --- save-to-library bar (hidden until 'Save set' is clicked)
        self.bar = tk.Frame(foot, bg=th["ed_panel"], highlightthickness=1,
                            highlightbackground=th["ed_edge"])
        tk.Label(self.bar, text="SAVE AS", bg=th["ed_panel"], fg=th["dim"],
                 font=f.lbl).pack(side="left", padx=(10, 6), pady=8)
        self.cancel_save_btn = _button(self.bar, "Cancel", self.hide_bar, th["ed_btn"],
                                       th["ed_btn_hover"], th["text"], f, padx=12, pady=4)
        self.cancel_save_btn.pack(side="right", padx=(0, 8))
        self.confirm_save_btn = _button(self.bar, "Save", self.do_save, th["accent"],
                                        th["accent_hover"], th["accent_text"], f,
                                        padx=12, pady=4)
        self.confirm_save_btn.pack(side="right", padx=(0, 6))
        self.name_var = tk.StringVar()
        self.name_var.trace_add("write", lambda *a: self._name_changed())
        self.name_entry = _entry(self.bar, self.name_var, th, f)
        self.name_entry.pack(side="left", fill="x", expand=True, ipady=4, pady=8,
                             padx=(0, 8))
        self.name_entry.bind("<Return>", lambda e: self.do_save())
        self.name_entry.bind("<Escape>", lambda e: (self.hide_bar(), "break")[1])

        # --- buttons
        _button(self.btnrow, "Save set", self.toggle_bar, th["ed_btn"],
                th["ed_btn_hover"], th["text"], f, padx=14).pack(side="left")
        self.status = tk.Label(self.btnrow, text="", bg=th["ed_bg"], fg=th["green"],
                               font=f.lbl)
        self.status.pack(side="left", padx=10)
        _button(self.btnrow, action_text, self.confirm, th["accent"],
                th["accent_hover"], th["accent_text"], f).pack(side="right")
        _button(self.btnrow, "Cancel", self.close, th["ed_btn"], th["ed_btn_hover"],
                th["text"], f).pack(side="right", padx=(0, 8))

        win.bind("<Escape>", lambda e: self.close())
        win.bind("<Control-Return>", lambda e: self.confirm())
        win.after(60, win.focus_force)

    # ---- window state
    def alive(self):
        if self._closed:
            return False
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def focus(self):
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except tk.TclError:
            pass

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def flash(self, text, color=None):
        if self._closed:
            return
        if self._status_job:
            try:
                self.win.after_cancel(self._status_job)
            except tk.TclError:
                pass
        self.status.config(text=text, fg=color or self.th["green"])
        self._status_job = self.win.after(2800, lambda: (
            self.status.config(text="") if not self._closed else None))

    # ---- rows
    def render(self, focus=None):
        th, f, inner = self.th, self.f, self.inner
        for w in inner.winfo_children():
            w.destroy()
        inner.columnconfigure(1, weight=1)
        ents = []
        for i, r in enumerate(self.rows):
            tk.Label(inner, text=str(i + 1), width=2, bg=th["ed_panel"],
                     fg=th["ed_muted"], font=f.lbl).grid(row=i, column=0,
                                                         padx=(8, 2), pady=4)
            e = _entry(inner, r["name"], th, f)
            e.grid(row=i, column=1, sticky="ew", ipady=4, padx=2)
            m = _entry(inner, r["min"], th, f, width=5, justify="center")
            m.grid(row=i, column=2, padx=4, ipady=4)
            _ibtn(inner, "↑", lambda i=i: self.move(i, -1), th, f).grid(row=i, column=3)
            _ibtn(inner, "↓", lambda i=i: self.move(i, 1), th, f).grid(row=i, column=4)
            _ibtn(inner, "×", lambda i=i: self.remove(i), th, f,
                  hover=th["red"]).grid(row=i, column=5, padx=(0, 6))
            e.bind("<Return>", lambda ev, i=i: self.add_after(i))
            ents.append(e)
        if not self.rows:
            tk.Label(inner, text="No tasks yet — add one below", bg=th["ed_panel"],
                     fg=th["dim"], font=f.row, pady=24).grid(
                row=0, column=0, columnspan=6, sticky="ew")
        if focus is not None and 0 <= focus < len(ents):
            ents[focus].focus_set()
            ents[focus].icursor("end")

    @staticmethod
    def _new_row():
        return {"name": tk.StringVar(), "min": tk.StringVar()}

    def move(self, i, d):
        j = i + d
        if 0 <= j < len(self.rows):
            self.rows[i], self.rows[j] = self.rows[j], self.rows[i]
            self.render(focus=j)

    def remove(self, i):
        del self.rows[i]
        self.render(focus=min(i, len(self.rows) - 1) if self.rows else None)

    def add_after(self, i):
        self.rows.insert(i + 1, self._new_row())
        self.render(focus=i + 1)

    def add_end(self):
        self.rows.append(self._new_row())
        self.render(focus=len(self.rows) - 1)
        self.cv.update_idletasks()
        self.cv.yview_moveto(1)

    # ---- reading the form
    def collect(self):
        tasks = []
        for r in self.rows:
            name = r["name"].get().strip()
            if not name:
                continue
            est = None
            txt = r["min"].get().strip().replace(",", ".")
            if txt:
                try:
                    v = float(txt)
                    est = int(v * 60) if v > 0 else None
                except ValueError:
                    est = None
            tasks.append({"name": name, "est": est})
        return (self.title_var.get().strip() or "Daily Tasks",
                self.sub_var.get().strip(), tasks)

    # ---- confirm (Start / Apply)
    def confirm(self):
        title, sub, tasks = self.collect()
        if not tasks:
            self.flash("Add at least one task", self.th["red"])
            return
        self.close()
        self.on_confirm(title, sub, tasks)

    # ---- save to library (name + confirm/cancel)
    def toggle_bar(self):
        if self.bar.winfo_ismapped():
            self.hide_bar()
        else:
            self.show_bar()

    def show_bar(self):
        _, _, tasks = self.collect()
        if not tasks:
            self.flash("Add at least one task first", self.th["red"])
            return
        self.name_var.set(self.title_var.get().strip() or "My tasks")
        self.bar.pack(fill="x", pady=(0, 10), before=self.btnrow)
        self.name_entry.focus_set()
        self.name_entry.select_range(0, "end")
        self.name_entry.icursor("end")

    def hide_bar(self):
        self.bar.pack_forget()

    def _name_changed(self):
        name = self.name_var.get().strip().lower()
        exists = any(s.get("name", "").lower() == name for s in load_data()["library"])
        self.confirm_save_btn.config(text="Overwrite" if exists else "Save")

    def do_save(self):
        name = self.name_var.get().strip()
        if not name:
            self.flash("Give it a name", self.th["red"])
            return
        title, sub, tasks = self.collect()
        if not tasks:
            self.flash("Add at least one task first", self.th["red"])
            self.hide_bar()
            return
        d = load_data()
        entry = {"name": name, "title": title, "subtitle": sub, "tasks": tasks}
        for i, s in enumerate(d["library"]):
            if s.get("name", "").lower() == name.lower():
                d["library"][i] = entry
                verb = "Updated"
                break
        else:
            d["library"].append(entry)
            verb = "Saved"
        save_data(d)
        self.hide_bar()
        self.flash(f"{verb} “{name[:22]}”")


# ---------------------------------------------------------------- library
class LibraryDialog:
    """Browse saved task sets. on_pick(set) gets {'name','title','subtitle','tasks'}."""

    def __init__(self, root, th, f, on_pick, action_text="Open"):
        self.root, self.th, self.f = root, th, f
        self.on_pick, self.action_text = on_pick, action_text
        self._closed = False
        self._armed = None
        self._arm_job = None
        win = self.win = tk.Toplevel(root)
        win.title("Saved Tasks")
        win.configure(bg=th["ed_bg"])
        win.attributes("-topmost", True)
        win.minsize(400, 380)
        _place_window(win, root, 420, 560)
        dark_titlebar(win, th["dark"])
        win.protocol("WM_DELETE_WINDOW", self.close)

        _header(win, th, f, "Saved Tasks", "Pick a set to open it in the editor")

        foot = tk.Frame(win, bg=th["ed_bg"])
        foot.pack(side="bottom", fill="x", padx=18, pady=16)
        _button(foot, "Close", self.close, th["ed_btn"], th["ed_btn_hover"],
                th["text"], f).pack(side="right")

        body = tk.Frame(win, bg=th["ed_bg"])
        body.pack(fill="both", expand=True, padx=18, pady=(16, 0))
        wrap, self.cv, self.inner = _scroll_area(body, win, th)
        wrap.pack(fill="both", expand=True)
        self.render()
        win.bind("<Escape>", lambda e: self.close())
        win.after(60, win.focus_force)

    def alive(self):
        if self._closed:
            return False
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def focus(self):
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except tk.TclError:
            pass

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def render(self):
        th, f, inner = self.th, self.f, self.inner
        for w in inner.winfo_children():
            w.destroy()
        inner.columnconfigure(0, weight=1)
        lib = load_data()["library"]
        if not lib:
            tk.Label(inner, text="Nothing saved yet.\nUse “Save set” in the task editor.",
                     bg=th["ed_panel"], fg=th["dim"], font=f.row, pady=40,
                     justify="center").grid(row=0, column=0, sticky="ew")
            return
        for i, s in enumerate(lib):
            name = s.get("name", "Untitled")
            tasks = s.get("tasks", [])
            total = sum(t.get("est") or 0 for t in tasks)
            sub = f"{len(tasks)} task{'s' if len(tasks) != 1 else ''}"
            if total:
                sub += f"  •  {fmt(total)} planned"
            row = tk.Frame(inner, bg=th["ed_panel"])
            row.grid(row=i * 2, column=0, sticky="ew")
            row.columnconfigure(0, weight=1)
            txt = tk.Frame(row, bg=th["ed_panel"])
            txt.grid(row=0, column=0, sticky="w", padx=(14, 6), pady=10)
            shown = name if len(name) <= 26 else name[:25].rstrip() + "…"
            tk.Label(txt, text=shown, bg=th["ed_panel"], fg=th["text"],
                     font=f.rowb, anchor="w").pack(anchor="w")
            tk.Label(txt, text=sub, bg=th["ed_panel"], fg=th["dim"],
                     font=f.lbl, anchor="w").pack(anchor="w")
            _button(row, self.action_text, lambda s=s: self.pick(s), th["accent"],
                    th["accent_hover"], th["accent_text"], f, padx=14, pady=4
                    ).grid(row=0, column=1, padx=4)
            armed = self._armed == name
            d = tk.Label(row, text="Sure?" if armed else "×", width=5 if armed else 2,
                         bg=th["ed_panel"], fg=th["red"] if armed else th["ed_muted"],
                         font=f.rowb, cursor="hand2")
            d.bind("<Button-1>", lambda e, n=name: self.delete(n))
            d.bind("<Enter>", lambda e, d=d: d.config(fg=th["red"]))
            d.bind("<Leave>", lambda e, d=d, a=armed: d.config(
                fg=th["red"] if a else th["ed_muted"]))
            d.grid(row=0, column=2, padx=(0, 10))
            tk.Frame(inner, bg=th["ed_edge"], height=1).grid(row=i * 2 + 1, column=0,
                                                              sticky="ew")

    def delete(self, name):
        if self._arm_job:
            try:
                self.win.after_cancel(self._arm_job)
            except tk.TclError:
                pass
            self._arm_job = None
        if self._armed == name:                 # second click -> really delete
            self._armed = None
            d = load_data()
            d["library"] = [s for s in d["library"] if s.get("name") != name]
            save_data(d)
        else:                                   # first click -> ask to confirm
            self._armed = name
            self._arm_job = self.win.after(2500, self._disarm)
        self.render()

    def _disarm(self):
        self._armed = None
        self._arm_job = None
        if not self._closed:
            self.render()

    def pick(self, s):
        self.close()
        self.on_pick(s)


# ---------------------------------------------------------------- new-run dialogs
class _Dialog:
    """alive / focus / close shared by the small dialogs."""
    _closed = False

    def alive(self):
        if self._closed:
            return False
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def focus(self):
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except tk.TclError:
            pass

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.win.destroy()
        except tk.TclError:
            pass


class ModeDialog(_Dialog):
    """'Start New' -> pick Casual / Countdown / Normal. on_pick(mode) is called."""

    def __init__(self, root, th, f, on_pick):
        self.th, self.f, self.on_pick = th, f, on_pick
        win = self.win = tk.Toplevel(root)
        win.title("New Run")
        win.configure(bg=th["ed_bg"])
        win.attributes("-topmost", True)
        win.minsize(400, 440)
        _place_window(win, root, 430, 470)
        dark_titlebar(win, th["dark"])
        win.protocol("WM_DELETE_WINDOW", self.close)
        _header(win, th, f, "New Run", "Choose a mode")

        foot = tk.Frame(win, bg=th["ed_bg"])
        foot.pack(side="bottom", fill="x", padx=18, pady=16)
        _button(foot, "Cancel", self.close, th["ed_btn"], th["ed_btn_hover"],
                th["text"], f).pack(side="right")
        tk.Label(foot, text="press 1 / 2 / 3", bg=th["ed_bg"], fg=th["ed_muted"],
                 font=f.lbl).pack(side="left")

        body = tk.Frame(win, bg=th["ed_bg"])
        body.pack(fill="both", expand=True, padx=18, pady=(16, 0))
        accents = {"casual": th["green"], "countdown": th["gold"], "normal": th["finish"]}
        for n, mode in enumerate(MODES, 1):
            self._card(body, mode, n, accents[mode])
        win.bind("<Escape>", lambda e: self.close())
        for n, mode in enumerate(MODES, 1):
            win.bind(str(n), lambda e, m=mode: self.pick(m))
        win.after(60, win.focus_force)

    def _card(self, parent, mode, n, accent):
        th, f = self.th, self.f
        title, desc = MODE_INFO[mode]
        card = tk.Frame(parent, bg=th["ed_panel"], highlightthickness=1,
                        highlightbackground=th["ed_edge"], cursor="hand2")
        card.pack(fill="x", pady=(0, 10))
        strip = tk.Frame(card, bg=accent, width=5)
        strip.pack(side="left", fill="y")
        inner = tk.Frame(card, bg=th["ed_panel"])
        inner.pack(side="left", fill="both", expand=True, padx=14, pady=14)
        t = tk.Label(inner, text=title, bg=th["ed_panel"], fg=th["text"], font=f.menu,
                     anchor="w")
        t.pack(anchor="w")
        d = tk.Label(inner, text=desc, bg=th["ed_panel"], fg=th["dim"], font=f.lbl,
                     anchor="w", justify="left", wraplength=300)
        d.pack(anchor="w", pady=(3, 0))
        k = tk.Label(card, text=str(n), bg=th["ed_panel"], fg=th["ed_muted"], font=f.rowb,
                     padx=14)
        k.pack(side="right")
        paint = [card, inner, t, d, k]

        def hover(on):
            bg = th["ed_panel_hover"] if on else th["ed_panel"]
            for w in paint:
                w.config(bg=bg)
            card.config(highlightbackground=accent if on else th["ed_edge"])

        for w in paint + [strip]:
            w.bind("<Enter>", lambda e: hover(True))
            w.bind("<Leave>", lambda e: hover(False))
            w.bind("<Button-1>", lambda e, m=mode: self.pick(m))

    def pick(self, mode):
        self.close()
        self.on_pick(mode)


class QuickSetup(_Dialog):
    """Casual: just a title.  Countdown: a title + a time.
    on_confirm(title, seconds) / on_back() are called."""

    PRESETS = (15, 25, 45, 60, 90)          # minutes, countdown quick-pick chips

    def __init__(self, root, th, f, mode, title, seconds, on_confirm, on_back):
        self.mode, self.th, self.f = mode, th, f
        self.on_confirm, self.on_back = on_confirm, on_back
        self._job = None
        cd = mode == "countdown"
        win = self.win = tk.Toplevel(root)
        win.title(MODE_INFO[mode][0])
        win.configure(bg=th["ed_bg"])
        win.attributes("-topmost", True)
        win.minsize(400, 400 if cd else 300)
        _place_window(win, root, 430, 440 if cd else 330)
        dark_titlebar(win, th["dark"])
        win.protocol("WM_DELETE_WINDOW", self.close)
        _header(win, th, f, MODE_INFO[mode][0],
                "Name it and set the time" if cd else "Name your study session")

        foot = tk.Frame(win, bg=th["ed_bg"])
        foot.pack(side="bottom", fill="x", padx=18, pady=16)
        _button(foot, "Start", self.confirm, th["accent"], th["accent_hover"],
                th["accent_text"], f).pack(side="right")
        _button(foot, "Back", self.back, th["ed_btn"], th["ed_btn_hover"],
                th["text"], f).pack(side="right", padx=(0, 8))
        self.status = tk.Label(foot, text="", bg=th["ed_bg"], fg=th["red"], font=f.lbl)
        self.status.pack(side="left")

        body = tk.Frame(win, bg=th["ed_bg"])
        body.pack(fill="both", expand=True, padx=18, pady=(18, 0))
        self.title_var = tk.StringVar(value=title)
        _caption(body, "TITLE", th, f).pack(anchor="w")
        te = _entry(body, self.title_var, th, f)
        te.pack(fill="x", ipady=6, pady=(3, 18))
        te.bind("<Return>", lambda e: self.confirm())
        self.vars = None
        if cd:
            _caption(body, "TIME", th, f).pack(anchor="w")
            row = tk.Frame(body, bg=th["ed_bg"])
            row.pack(anchor="w", pady=(4, 10))
            seconds = int(seconds or 0)
            self.vars = {"h": tk.StringVar(value=str(seconds // 3600)),
                         "m": tk.StringVar(value=str(seconds % 3600 // 60)),
                         "s": tk.StringVar(value=str(seconds % 60))}
            for key in "hms":
                e = _entry(row, self.vars[key], th, f, width=4, justify="center")
                e.pack(side="left", ipady=6)
                e.bind("<Return>", lambda ev: self.confirm())
                tk.Label(row, text=key, bg=th["ed_bg"], fg=th["dim"], font=f.row).pack(
                    side="left", padx=(4, 14))
            chips = tk.Frame(body, bg=th["ed_bg"])
            chips.pack(anchor="w")
            for m in self.PRESETS:
                lbl = f"{m // 60}h" if m % 60 == 0 else (f"{m // 60}h{m % 60}" if m > 60 else f"{m}m")
                _button(chips, lbl, lambda m=m: self.set_minutes(m), th["ed_btn"],
                        th["ed_btn_hover"], th["text"], f, padx=10, pady=4).pack(
                    side="left", padx=(0, 6))
        win.bind("<Escape>", lambda e: self.close())
        win.after(60, lambda: (win.focus_force(), te.focus_set(), te.select_range(0, "end")))

    def set_minutes(self, m):
        self.vars["h"].set(str(m // 60))
        self.vars["m"].set(str(m % 60))
        self.vars["s"].set("0")

    def flash(self, text):
        self.status.config(text=text)
        if self._job:
            try:
                self.win.after_cancel(self._job)
            except tk.TclError:
                pass
        self._job = self.win.after(2800, lambda: None if self._closed else
                                   self.status.config(text=""))

    def total_seconds(self):
        """Seconds from the h/m/s boxes, or None if they aren't valid numbers."""
        try:
            h, m, sec = (int(self.vars[k].get().strip() or 0) for k in "hms")
        except ValueError:
            return None
        if min(h, m, sec) < 0:
            return None
        return min(h * 3600 + m * 60 + sec, 99 * 3600 + 59 * 60 + 59)

    def confirm(self):
        title = self.title_var.get().strip() or ("Focus Session" if self.vars else "Study Session")
        secs = 0
        if self.vars:
            secs = self.total_seconds()
            if secs is None:
                self.flash("Time must be whole numbers")
                return
            if secs <= 0:
                self.flash("Set a time above 0")
                return
        self.close()
        self.on_confirm(title, secs)

    def back(self):
        self.close()
        self.on_back()


# ---------------------------------------------------------------- overlay
class TaskSplit:
    def __init__(self, title="Daily Tasks", subtitle="", tasks=None, snapshot=None,
                 mode="normal", duration=0):
        d = load_data()
        st = d["settings"]
        self.th = THEMES[st["theme"]]
        self.s = SIZES[st["size"]]
        self.opacity = float(st.get("opacity", 0.85))
        self.pos = d.get("pos")
        self.best = dict(d.get("best", {}))
        self._best_before = None

        self.title = title or "Daily Tasks"
        self.subtitle = subtitle or ""
        self.tasks = [dict(t) for t in (DEFAULT_TASKS if tasks is None else tasks)]
        self.mode = mode if mode in MODES else "normal"
        self.duration = float(duration or 0)        # countdown length in seconds
        if self.mode != "normal":
            self.tasks = []
        self.splits, self.golds = [], []
        self.acc, self.t0 = 0.0, None
        self._bell_done = False
        self._cleared = False            # set by Reset: lets save() drop the snapshot
        self._last_autosave = time.monotonic()
        if snapshot:
            self.restore(snapshot)

        self.q = queue.Queue()
        self.hover = None
        self.pressing = None
        self._target = None
        self._moved = False
        self._press = (0, 0, 0, 0)
        self.reset_armed = 0.0
        self._editor = None
        self._alive = True
        self.hk = None

        self.root = tk.Tk()
        self.root.title("TaskSplit")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", self.opacity)
        self.root.configure(bg=self.th["bg"])

        self.f = make_fonts(self.s)      # overlay fonts follow the size setting
        self.fe = make_fonts(1.0)        # dialogs stay normal size

        self.canvas = tk.Canvas(self.root, width=int(W * self.s),
                                height=int(self.height() * self.s),
                                bg=self.th["bg"], highlightthickness=0, bd=0)
        self.canvas.pack()
        self.apply_geometry(first=True)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Leave>", self.on_leave)
        for b in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
            self.canvas.bind(b, self.show_menu)

        self.build_menu()
        self.start_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.tick()

    # ------------------------------------------------------------ state
    def snapshot(self):
        return {"mode": self.mode, "duration": self.duration,
                "title": self.title, "subtitle": self.subtitle,
                "tasks": self.tasks, "splits": self.splits, "golds": self.golds,
                "elapsed": self.elapsed(), "best_before": self._best_before,
                "saved_at": datetime.datetime.now().isoformat(timespec="seconds")}

    def restore(self, s):
        """Load a snapshot. The clock comes back PAUSED at the saved time."""
        self.title = s.get("title") or "Daily Tasks"
        self.subtitle = s.get("subtitle") or ""
        m = s.get("mode", "normal")
        self.mode = m if m in MODES else "normal"
        self.duration = float(s.get("duration", 0) or 0)
        self.tasks = [dict(t) for t in s.get("tasks", [])] if self.mode == "normal" else []
        self.splits = [float(x) for x in s.get("splits", [])][:len(self.tasks)]
        g = [bool(x) for x in s.get("golds", [])][:len(self.splits)]
        self.golds = g + [False] * (len(self.splits) - len(g))
        self.acc = max(float(s.get("elapsed", 0)), self.splits[-1] if self.splits else 0.0)
        self.t0 = None
        bb = s.get("best_before")
        self._best_before = dict(bb) if isinstance(bb, dict) else None
        if self.mode == "countdown" and self.duration > 0:
            self.acc = min(self.acc, self.duration)
        self._bell_done = self.finished             # don't ring again for a finished run

    def save(self):
        """Read-modify-write so we never clobber the library / settings.
        Also keeps the 'Continue' snapshot up to date while a run is in progress."""
        try:
            d = load_data()
            d["best"] = self.best
            d["settings"]["opacity"] = self.opacity
            d["pos"] = [self.root.winfo_x(), self.root.winfo_y()]
            if self.started:
                d["snapshot"] = self.snapshot()
            elif self._cleared:         # run was reset -> nothing to continue
                d["snapshot"] = None
            save_data(d)
        except Exception:
            pass

    def elapsed(self):
        raw = self.acc + (time.monotonic() - self.t0 if self.t0 else 0.0)
        if self.mode == "countdown" and self.duration > 0:
            return min(raw, self.duration)
        return raw

    @property
    def started(self):
        return self.t0 is not None or self.acc > 0 or bool(self.splits)

    @property
    def finished(self):
        if self.mode == "casual":
            return False
        if self.mode == "countdown":
            return self.duration > 0 and self.elapsed() >= self.duration - 1e-9
        return bool(self.tasks) and len(self.splits) >= len(self.tasks)

    @property
    def running(self):
        return self.t0 is not None

    def seg_elapsed(self):
        return self.elapsed() - (self.splits[-1] if self.splits else 0.0)

    def seg_time(self, i):
        prev = self.splits[i - 1] if i > 0 else 0.0
        return self.splits[i] - prev

    # ------------------------------------------------------------ actions
    def split(self):
        if self.mode != "normal" or not self.tasks or not self.running or self.finished:
            return
        cum = self.elapsed()
        prev = self.splits[-1] if self.splits else 0.0
        name = self.tasks[len(self.splits)]["name"]
        seg = cum - prev
        self.golds.append(name in self.best and seg < self.best[name])
        self.splits.append(cum)
        if self.finished:
            self.acc = cum
            self.t0 = None
            self._best_before = dict(self.best)
            self.commit_bests()
        self.save()

    def commit_bests(self):
        for i, t in enumerate(self.tasks):
            seg = self.seg_time(i)
            if t["name"] not in self.best or seg < self.best[t["name"]]:
                self.best[t["name"]] = seg

    def undo(self):
        if not self.splits:
            return
        was_finished = self.finished
        self.splits.pop()
        if self.golds:
            self.golds.pop()
        if was_finished:
            if self._best_before is not None:
                self.best = self._best_before
                self._best_before = None
            self.t0 = time.monotonic()  # keep the clock going
        self.save()

    def pause(self):
        if self.running:
            self.acc += time.monotonic() - self.t0
            self.t0 = None
        elif not self.finished and (self.tasks or self.mode != "normal"):
            self.t0 = time.monotonic()  # start, or resume after stop
        self.save()

    def reset(self):
        self.splits, self.golds, self.acc, self.t0 = [], [], 0.0, None
        self._best_before = None
        self._bell_done = False
        self._cleared = True
        self.save()

    def apply_tasks(self, title, subtitle, tasks):
        was_finished = self.finished
        self.tasks = tasks
        self.title = title
        self.subtitle = subtitle
        self.splits = self.splits[:len(self.tasks)]
        self.golds = self.golds[:len(self.splits)]
        if was_finished and not self.finished and self.t0 is None:
            self.t0 = time.monotonic()
        self.apply_geometry()
        self.save()

    # ------------------------------------------------------------ window
    def n_rows(self):
        if self.mode != "normal":
            return 0                    # casual / countdown: just header + big timer
        return max(1, min(len(self.tasks), MAX_ROWS))

    def height(self):
        return HEADER_H + self.n_rows() * ROW_H + FOOT_H

    def apply_geometry(self, first=False):
        pw, ph = int(W * self.s), int(self.height() * self.s)
        self.canvas.config(width=pw, height=ph)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        if first:
            x, y = (self.pos if self.pos else (sw - pw - 24, 120))
        else:
            x, y = self.root.winfo_x(), self.root.winfo_y()
        x = max(0, min(int(x), sw - pw))
        y = max(0, min(int(y), sh - ph - 40))
        self.root.geometry(f"{pw}x{ph}+{x}+{y}")

    # --- buttons / hit testing (all in base, unscaled coordinates)
    def button_rects(self):
        fy = self.height() - FOOT_H
        y0 = fy + 11
        rects = {}
        names = ("undo", "reset", "split") if self.mode == "normal" else ("reset",)
        for k, name in enumerate(names):
            x0 = 12 + k * (BTN + BTN_GAP)
            rects[name] = (x0, y0, x0 + BTN, y0 + BTN)
        return rects

    def enabled(self, name):
        if name == "undo":
            return bool(self.splits)
        if name == "reset":
            return self.started
        if name == "split":
            return self.running and not self.finished
        return True

    def hit(self, x, y):
        x, y = x / self.s, y / self.s
        for name, (x0, y0, x1, y1) in self.button_rects().items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return name
        fy = self.height() - FOOT_H
        if fy <= y <= fy + TIMER_H:
            return "timer"
        return None

    def reset_click(self):
        if time.monotonic() < self.reset_armed:
            self.reset_armed = 0.0
            self.reset()
        else:
            self.reset_armed = time.monotonic() + 2.5  # ask to confirm

    def on_motion(self, e):
        h = self.hit(e.x, e.y)
        if h and not self.enabled(h):
            h = None
        if h != self.hover:
            self.hover = h
            self.canvas.config(cursor="hand2" if h else "")

    def on_leave(self, e):
        self.hover = None
        self.canvas.config(cursor="")

    def on_press(self, e):
        self._press = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())
        self._moved = False
        t = self.hit(e.x, e.y)
        self._target = t if (t and self.enabled(t)) else None
        self.pressing = self._target

    def on_drag(self, e):
        if self._target:
            return
        px, py, wx, wy = self._press
        dx, dy = e.x_root - px, e.y_root - py
        if abs(dx) + abs(dy) > 4:
            self._moved = True
        if self._moved:
            self.root.geometry(f"+{wx + dx}+{wy + dy}")

    def on_release(self, e):
        t, self._target, self.pressing = self._target, None, None
        if t:
            if self.hit(e.x, e.y) == t:
                {"timer": self.pause, "undo": self.undo,
                 "reset": self.reset_click, "split": self.split}[t]()
        elif self._moved:
            self.save()

    # ------------------------------------------------------------ menu
    def build_menu(self):
        normal = self.mode == "normal"
        m = tk.Menu(self.root, tearoff=0)
        if normal:
            m.add_command(label="Split (next task)", command=self.split)
        m.add_command(label="Start / Stop timer", command=self.pause)
        if normal:
            m.add_command(label="Undo split", command=self.undo)
        m.add_command(label="Reset run", command=self.reset)
        m.add_separator()
        if normal:
            m.add_command(label="Edit tasks\u2026", command=self.edit_tasks)
        om = tk.Menu(m, tearoff=0)
        self.op_var = tk.IntVar(value=int(round(self.opacity * 100)))
        for pct in (40, 55, 70, 85, 100):
            om.add_radiobutton(label=f"{pct}%", value=pct, variable=self.op_var,
                               command=lambda p=pct: self.set_opacity(p))
        m.add_cascade(label="Opacity", menu=om)
        self.top_var = tk.BooleanVar(value=True)
        m.add_checkbutton(label="Always on top", variable=self.top_var,
                          command=lambda: self.root.attributes("-topmost", self.top_var.get()))
        m.add_separator()
        m.add_command(label="Quit to main menu", command=self.quit)
        self.menu = m

    def show_menu(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def set_opacity(self, pct):
        self.opacity = pct / 100
        self.root.attributes("-alpha", self.opacity)
        self.save()

    def edit_tasks(self):
        if self._editor is not None and self._editor.alive():
            self._editor.focus()
            return
        self._editor = TaskEditor(
            self.root, self.th, self.fe, self.title, self.subtitle, self.tasks,
            "Apply", self.apply_tasks, heading="Edit Tasks",
            subheading="Changes apply to this run")

    # ------------------------------------------------------------ hotkeys
    def start_hotkeys(self):
        try:
            from pynput import keyboard as pk
            put = self.q.put
            self.hk = pk.GlobalHotKeys({
                "<ctrl>+<alt>+<space>": lambda: put("split"),
                "<ctrl>+<alt>+z": lambda: put("undo"),
                "<ctrl>+<alt>+p": lambda: put("pause"),
                "<ctrl>+<alt>+r": lambda: put("reset"),
            })
            self.hk.daemon = True
            self.hk.start()
        except Exception:
            self.hk = None  # hotkeys are optional

    # ------------------------------------------------------------ drawing
    def mw(self, font, text):
        """Text width in base (unscaled) canvas units."""
        return font.measure(text) / self.s

    def fit(self, text, font, width):
        """Trim text with an ellipsis so it fits `width` base units."""
        limit = width * self.s
        if font.measure(text) <= limit:
            return text
        while text and font.measure(text + "…") > limit:
            text = text[:-1]
        return text.rstrip() + "…"

    def draw(self):
        c, th, f = self.canvas, self.th, self.f
        c.delete("all")
        total_h = self.height()
        n = len(self.tasks)
        cur = len(self.splits)
        el = self.elapsed()

        # header
        vgrad(c, 0, 0, W, HEADER_H, th["head_top"], th["head_bot"])
        c.create_text(12, 17, anchor="w", font=f.title, fill=th["text"],
                      text=self.fit(self.title or "Daily Tasks", f.title, W - 70))
        sub = datetime.date.today().strftime("%a %d %b").upper()
        if self.subtitle:
            sub += "  •  " + self.subtitle
        c.create_text(12, 34, anchor="w", font=f.sub, fill=th["dim"],
                      text=self.fit(sub, f.sub, W - 24))
        if self.mode == "normal":
            c.create_text(W - 12, 24, anchor="e", text=f"{min(cur, n)}/{n}", font=f.title,
                          fill=th["finish"] if self.finished else th["text"])
        else:
            c.create_text(W - 12, 22, anchor="e", text=self.mode.upper(), font=f.sub,
                          fill=th["finish"] if self.finished else th["dim"])

        # rows
        if n == 0 and self.mode == "normal":
            c.create_text(W / 2, HEADER_H + ROW_H / 2, text="Right-click → Edit tasks",
                          font=f.row, fill=th["dim"])
        start = 0
        if n > MAX_ROWS:
            start = max(0, min(cur - 3, n - MAX_ROWS))
        for r in range(self.n_rows()):
            i = start + r
            if i >= n:
                break
            y0 = HEADER_H + r * ROW_H
            y1 = y0 + ROW_H
            t = self.tasks[i]
            est = t.get("est")
            is_cur = (i == cur and not self.finished)
            if is_cur:
                vgrad(c, 0, y0, W, y1, th["cur_top"], th["cur_bot"])
            else:
                c.create_line(0, y1 - 1, W, y1 - 1, fill=th["sep"])

            name_col = th["cur_text"] if is_cur else th["text"]
            time_txt, time_col = "", th["dim"]
            delta_txt, delta_col = "", th["green"]
            if i < cur:  # completed
                seg = self.seg_time(i)
                time_txt, time_col = fmt(seg), th["text"]
                if est:
                    diff = seg - est
                    delta_txt = fmt(diff, signed=True)
                    delta_col = th["green"] if diff <= 0 else th["red"]
                if i < len(self.golds) and self.golds[i]:
                    delta_col = th["gold"]
                    if not delta_txt:
                        delta_txt = "★"
            elif is_cur:
                seg = self.seg_elapsed()
                time_txt, time_col = fmt(seg), th["cur_text"]
                if est and seg > est:
                    delta_txt, delta_col = fmt(seg - est, signed=True), th["red"]
            else:  # upcoming
                time_txt = fmt(est) if est else "—"
                name_col = th["upcoming"]

            mid = (y0 + y1) / 2
            tx = W - 12
            c.create_text(tx, mid, anchor="e", text=time_txt, font=f.row, fill=time_col)
            dx = tx - self.mw(f.row, "0:00:00") - 6
            if delta_txt:
                c.create_text(dx, mid, anchor="e", text=delta_txt, font=f.rowb,
                              fill=delta_col)
            c.create_text(12, mid, anchor="w",
                          text=self.fit(t["name"], f.row, max(40, dx - 24 - 50)),
                          font=f.rowb if is_cur else f.row, fill=name_col)

        # footer
        fy = total_h - FOOT_H
        c.create_line(0, fy, W, fy, fill=th["footer_line"])
        rem = max(0.0, self.duration - el) if self.mode == "countdown" else 0.0
        if self.finished:
            col = th["finish"]
        elif not self.running:
            col = th["paused"]
        elif self.mode == "casual":
            col = th["green"]
        elif self.mode == "countdown":
            col = th["red"] if rem <= 10 else th["green"]
        else:
            planned = sum((self.tasks[i].get("est") or 0) for i in range(min(cur + 1, n)))
            col = th["green"] if (planned == 0 or el <= planned) else th["red"]

        shown = rem if self.mode == "countdown" else el     # countdown shows time LEFT
        cs = int((shown - int(shown)) * 100)
        main = fmt(shown)
        dec = f".{cs:02d}"
        right = W - 12
        base_y = fy + 42
        c.create_text(right, base_y, anchor="se", text=dec, font=f.bigdec, fill=col)
        c.create_text(right - self.mw(f.bigdec, dec), base_y + 2, anchor="se",
                      text=main, font=f.big, fill=col)

        armed = time.monotonic() < self.reset_armed
        done_txt = "Time's up!" if self.mode == "countdown" else "Done!"
        label = "Not started" if not self.started else (
            done_txt if self.finished else ("Running" if self.running else "Paused"))
        hints = {"undo": "Undo", "reset": "Reset run", "split": "Next task",
                 "timer": "Stop" if self.running else ("Resume" if self.started else "Start")}
        lbl_col = th["dim"]
        if armed:
            label, lbl_col = "Click again to reset", th["arm_icon"]
        elif self.hover in hints and not (self.hover == "timer" and self.finished):
            label = hints[self.hover]
        c.create_text(12, fy + 58, anchor="w", text=label.upper(), font=f.lbl, fill=lbl_col)
        if self.mode == "normal" and self.started and not self.finished:
            sg = self.seg_elapsed()
            sc = int((sg - int(sg)) * 100)
            c.create_text(right, fy + 72, anchor="e", text=f"{fmt(sg)}.{sc:02d}",
                          font=f.seg, fill=th["text"])
            c.create_text(12, fy + 72, anchor="w", text="CURRENT TASK", font=f.lbl,
                          fill=th["dim"])
        elif not self.started:
            c.create_text(right, fy + 72, anchor="e", text="click timer to start",
                          font=f.lbl, fill=th["dim"])

        elif self.mode == "countdown" and self.started:
            ec = int((el - int(el)) * 100)
            c.create_text(right, fy + 72, anchor="e", text=f"{fmt(el)}.{ec:02d}",
                          font=f.seg, fill=th["text"])
            c.create_text(12, fy + 72, anchor="w", text="ELAPSED", font=f.lbl, fill=th["dim"])

        # small, subtle icon buttons
        for name, (x0, y0, x1, y1) in self.button_rects().items():
            on = self.enabled(name)
            hov = on and self.hover == name
            prs = on and self.pressing == name
            if not on:
                fill, edge, ic = th["btn_off_fill"], th["btn_off_edge"], th["btn_off_icon"]
            elif name == "reset" and armed:
                fill, edge, ic = th["arm_fill"], th["arm_edge"], th["arm_icon"]
            else:
                fill = th["btn_press"] if prs else th["btn_hover"] if hov else th["btn_fill"]
                edge = th["btn_edge_hover"] if hov else th["btn_edge"]
                ic = th["icon_hover"] if hov else (th["finish"] if name == "split"
                                                  else th["icon"])
            c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=edge)
            self.icon(name, (x0 + x1) / 2, (y0 + y1) / 2 + (1 if prs else 0), ic)

        c.create_rectangle(0, 0, W - 1, total_h - 1, outline=th["edge"])
        if self.s != 1:
            c.scale("all", 0, 0, self.s, self.s)

    def arc_arrow(self, cx, cy, r, t0, t1, col):
        pts = []
        for k in range(19):
            t = math.radians(t0 + (t1 - t0) * k / 18)
            pts += [cx + r * math.cos(t), cy - r * math.sin(t)]
        self.canvas.create_line(*pts, fill=col, width=2 * self.s, smooth=True)
        t = math.radians(t1)
        ex, ey = cx + r * math.cos(t), cy - r * math.sin(t)
        tx, ty = -math.sin(t), -math.cos(t)  # direction of travel
        nx, ny = -ty, tx
        k = 4.5
        self.canvas.create_polygon(
            ex + tx * k, ey + ty * k,
            ex - tx + nx * k, ey - ty + ny * k,
            ex - tx - nx * k, ey - ty - ny * k,
            fill=col, outline=col)

    def icon(self, name, cx, cy, col):
        c = self.canvas
        if name == "undo":      # curved back arrow
            self.arc_arrow(cx, cy + 1, 5, 10, 195, col)
        elif name == "reset":   # circular arrow
            self.arc_arrow(cx, cy, 5, 55, 325, col)
        elif name == "split":   # skip-to-next
            c.create_polygon(cx - 5, cy - 5, cx - 5, cy + 5, cx + 3, cy,
                             fill=col, outline=col)
            c.create_rectangle(cx + 4, cy - 5, cx + 6, cy + 5, fill=col, outline=col)

    # ------------------------------------------------------------ loop
    def tick(self):
        if not self._alive:
            return
        try:
            while True:
                getattr(self, self.q.get_nowait())()
        except queue.Empty:
            pass
        if self.mode == "countdown" and self.running and self.finished:
            self.acc, self.t0 = self.duration, None          # freeze at 0.00
            if not self._bell_done:
                self._bell_done = True
                try:
                    self.root.bell()
                except Exception:
                    pass
            self.save()
        self.draw()
        if self.running and time.monotonic() - self._last_autosave > 5:
            self._last_autosave = time.monotonic()
            self.save()                 # autosave so a crash can't lose the run
        self.root.after(50, self.tick)

    def quit(self):
        """Close the overlay (run is saved as a snapshot); mainmenu.py then
        shows the main menu again, where Continue picks it back up."""
        if not self._alive:
            return
        self._alive = False
        self.save()
        if self.hk is not None:
            try:
                self.hk.stop()
            except Exception:
                pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    import mainmenu
    mainmenu.main()