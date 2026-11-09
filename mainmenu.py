#!/usr/bin/env python3
"""
TaskSplit - main menu.   Run this file:   python mainmenu.py

Keep it in the same folder as tsv2.py.
  Continue     -> pick up the run you left off (greyed out if there is none)
  Start New    -> task editor -> Start -> the speedrun overlay opens
               (right-click the overlay -> "Quit to main menu" saves your run)
  Saved Tasks  -> your library of saved task sets (save from any task editor)
  Settings     -> overlay size + dark / light theme
  AFK (page 2) -> pick a reason, an image pops up in the middle of your screen

The menu is a real window: it shows on the taskbar and has its own custom
minimize / close buttons in the top-right corner (no maximize - it can't resize).
  Quit         -> close the app
"""
import datetime
import math
import os
import random
import re
import sys
import tkinter as tk
from fractions import Fraction

import tsv2 as ts

# ===================================================================
#  LOGO SETTINGS  -  tweak these to taste
# ===================================================================
# Put your image(s) in a folder called  resources  next to mainmenu.py
# (PNG, transparent bg).
# It looks for  logo_dark.png / logo_light.png  (matching the theme) first,
# then falls back to a single  logo.png  for both themes. If none exist,
# the plain text title "TaskSplit" is shown instead.
LOGO_DIR = "resources"      # folder (next to mainmenu.py) that holds the logo files
LOGO_FILE = "logo"          # base name -> logo_dark.png, logo_light.png, logo.png
LOGO_SCALE = 0.28            # size multiplier: 0.5 = half size, 2.0 = double
LOGO_X = 6                 # pixels from the LEFT edge of the window (bigger = right)
LOGO_Y = -1                  # vertical nudge: negative = up, positive = down
LOGO_CENTER = False         # True = ignore LOGO_X and centre it horizontally
# ===================================================================

# ===================================================================
#  AFK SETTINGS  -  tweak these to taste
# ===================================================================
# Each prompt is  ("text shown in the list", "image file name", RANDOM)
#
#   RANDOM = False -> always shows  <name>.png  (e.g. bathroom.png)
#   RANDOM = True  -> picks a random one of  <name>.png, <name>1.png, <name>2.png ...
#                     (never the same one twice in a row, if there is more than one)
#
# >>> TO TURN RANDOMIZING ON/OFF FOR A PROMPT, CHANGE True / False ON ITS LINE <<<
#
# Put the images in  resources/afk/  e.g.  resources/afk/bathroom1.png
# (.png always works; .jpg/.jpeg/.webp/.bmp also work if Pillow is installed).
AFK_DIR = os.path.join("resources", "afk")
AFK_PROMPTS = [
    #  label                   file name      random?
    ("Unspecified Reason",    "unspecified",  False),
    ("Bathroom Break",        "bathroom",     True),
    ("Food Break",            "food",         True),
    ("Drink / Water",         "drink",        False),
    ("Phone Call",            "phone",        False),
    ("Someone At The Door",   "door",         False),
    ("Stretch Break",         "stretch",      True),
    ("Quick Nap",             "nap",          False),
    ("Be Right Back",         "brb",          True),
]
AFK_SCREEN_FRACTION = 0.5   # image fits inside this fraction of the screen (0.5 = 50%)
AFK_UPSCALE = True          # True = small images are enlarged to reach that size
# ===================================================================

# ===================================================================
#  WINDOW SETTINGS
# ===================================================================
MENU_ALWAYS_ON_TOP = False  # True = menu floats above every other window
WIN_BTN_W, WIN_BTN_H = 40, 28   # size of the custom minimize / close buttons
# Optional taskbar icon: put  icon.ico  (Windows) and/or  icon.png  in  resources/
# ===================================================================

HEADER = 80
ROW = 58
PAGER_H = 36                # height of the page bar under the buttons
ITEMS = ("continue", "start", "library", "settings", "quit")
LABELS = {"continue": "Continue", "start": "Start New", "library": "Saved Tasks",
          "settings": "Settings", "quit": "Quit",
          "afk": "AFK", "ph3": "Placeholder 3", "ph4": "Placeholder 4"}

# Horizontal pages. Each page is a tuple of button names (max len(ITEMS) per page).
# To add a button to a page, add its name here + a label in LABELS + a case in act().
PAGES = [
    ITEMS,
    ("afk",),
    ("ph3",),
    ("ph4",),
]
PAGE_TITLES = [("TaskSplit", "DAILY TASK SPLITS"),
               ("Away", "AFK SCREENS"),
               ("Page 3", "PLACEHOLDER PAGE"),
               ("Page 4", "PLACEHOLDER PAGE")]

BODY_H = len(ITEMS) * ROW                       # area the button rows live in
CLOCK_H = 94                                    # clock footer (page 1 only)
W, H = 340, HEADER + BODY_H + CLOCK_H + PAGER_H  # page bar sits at the very bottom


def resource(name):
    """Find a bundled file, both from the .py and inside a PyInstaller exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def scale_image(img, scale):
    """Scale a tk.PhotoImage by any factor (smooth with Pillow, else zoom/subsample)."""
    if abs(scale - 1.0) < 0.01:
        return img
    fr = Fraction(scale).limit_denominator(8)
    return img.zoom(fr.numerator, fr.numerator).subsample(fr.denominator, fr.denominator)


AFK_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")


def find_images(base):
    """All files for a prompt: base.png, base1.png, base2.png ... (sorted, exact name first)."""
    folder = resource(AFK_DIR)
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    pat = re.compile(re.escape(base) + r"(\d*)", re.I)
    found = []
    for fn in names:
        stem, ext = os.path.splitext(fn)
        m = pat.fullmatch(stem)
        if m and ext.lower() in AFK_EXTS:
            n = int(m.group(1)) if m.group(1) else 0
            found.append((n, ext.lower() != ".png", fn))
    found.sort()
    return [os.path.join(folder, fn) for _, _, fn in found]


def find_image(base):
    """First image for a prompt (the plain  <base>.png  if it exists), or None."""
    imgs = find_images(base)
    return imgs[0] if imgs else None


def pick_image(base, randomize, last=None):
    """Which file to show: a random one (not `last` again) or always the first."""
    imgs = find_images(base)
    if not imgs:
        return None
    if randomize and len(imgs) > 1:
        choices = [p for p in imgs if p != last] or imgs
        return random.choice(choices)
    return imgs[0]


def detach_owner(win):
    """Windows only: make a popup independent of the main window, so it stays visible
    when the main window is minimized. Harmless no-op elsewhere."""
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        f = ctypes.windll.user32.SetWindowLongPtrW
        f.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        f.restype = ctypes.c_void_p
        f(hwnd, -8, None)                       # GWLP_HWNDPARENT -> no owner
    except Exception:
        pass


def prompt_info(i):
    """(label, file base name, randomize?) for AFK_PROMPTS[i]; RANDOM defaults to False."""
    p = AFK_PROMPTS[i]
    return p[0], p[1], (bool(p[2]) if len(p) > 2 else False)


def fit_scale(iw, ih, maxw, maxh, upscale=True):
    """Scale factor that fits iw x ih inside maxw x maxh, keeping the aspect ratio."""
    sc = min(maxw / iw, maxh / ih)
    return sc if upscale else min(sc, 1.0)


def load_fitted(path, maxw, maxh, upscale=True):
    """Load an image scaled to fit inside maxw x maxh (aspect ratio kept)."""
    try:
        from PIL import Image, ImageTk
    except ImportError:
        Image = None
    if Image:                                   # smooth, any format
        im = Image.open(path)
        im.load()
        iw, ih = im.size
        sc = fit_scale(iw, ih, maxw, maxh, upscale)
        im = im.convert("RGBA").resize((max(1, round(iw * sc)), max(1, round(ih * sc))),
                                       Image.LANCZOS)
        return ImageTk.PhotoImage(im)
    img = tk.PhotoImage(file=path)              # plain tkinter: png / gif only
    sc = fit_scale(img.width(), img.height(), maxw, maxh, upscale)
    fr = Fraction(sc).limit_denominator(32)
    if fr > sc:                                 # never overshoot the screen budget
        fr = Fraction(max(1, int(sc * 32)), 32)
    if fr == 1:
        return img
    out = tk.PhotoImage()
    out.tk.call(out, "copy", img, "-zoom", fr.numerator, fr.numerator,
                "-subsample", fr.denominator, fr.denominator)
    return out


def moon_points(cx, cy, R=8.0, r=6.5, dx=4.0, dy=2.0, steps=14):
    """Polygon for a crescent moon (a circle with a bite taken out of it)."""
    d = math.hypot(dx, dy)
    td = math.atan2(dy, dx)                     # direction of the bite (math coords, y up)
    a = (R * R - r * r + d * d) / (2 * d)
    alpha = math.acos(max(-1, min(1, a / R)))
    beta = math.acos(max(-1, min(1, (d - a) / r)))

    def pt(ox, oy, rad, ang):
        return (cx + ox + rad * math.cos(ang), cy - (oy + rad * math.sin(ang)))

    outer = [pt(0, 0, R, td + alpha + (2 * math.pi - 2 * alpha) * k / steps)
             for k in range(steps + 1)]
    inner = [pt(dx, dy, r, td + math.pi - beta + 2 * beta * k / steps)
             for k in range(steps + 1)]
    if math.dist(outer[-1], inner[0]) > math.dist(outer[-1], inner[-1]):
        inner.reverse()
    return [v for p in outer + inner for v in p]


class MainMenu:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TaskSplit")
        self.root.overrideredirect(True)        # we draw our own title buttons
        self.root.attributes("-topmost", MENU_ALWAYS_ON_TOP)
        self.f = ts.make_fonts(1.0)
        self.set_icon()
        self._redirect_pending = False
        self.root.bind("<Map>", self.on_map)

        self.reload()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{(sw - W) // 2}+{max(20, (sh - H) // 2 - 20)}")
        self.c = tk.Canvas(self.root, width=W, height=H, highlightthickness=0, bd=0)
        self.c.pack()
        self.apply_theme()

        self.view = "home"          # "home" | "settings"
        self.hot = None             # hovered / selected row (home) or control key (settings)
        self.result = None
        self._dialog = None
        self._was_open = False
        self._press = (0, 0, 0, 0)
        self._press_hot = None
        self._press_y = 0
        self._moved = False
        self._logos = {}            # theme name -> PhotoImage (or None); must stay referenced
        self.pos = 0.0              # current (animated) page position, may be fractional
        self.target = 0             # page we're sliding to (can be outside 0..n-1 while wrapping)
        self._anim_job = None
        # AFK page state
        self.afk_scroll = 0.0       # current (animated) scroll offset in px
        self.afk_target = 0.0
        self._afk_job = None
        self._afk_win = None        # the image window, when open
        self._afk_keep = None       # keeps the PhotoImage alive
        self._rehover = False
        self._mouse = None
        self.afk_has = {}           # prompt key -> number of image files found
        self._afk_last = {}         # prompt key -> file shown last time (for no-repeat random)

        self.c.bind("<Motion>", self.on_motion)
        self.c.bind("<Leave>", self.on_leave)
        self.c.bind("<ButtonPress-1>", self.on_press)
        self.c.bind("<B1-Motion>", self.on_drag)
        self.c.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Key>", self.on_key)
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.root.bind(ev, self.on_wheel)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    # ------------------------------------------------------------ data
    def reload(self):
        d = ts.load_data()
        self.theme_name = d["settings"]["theme"]
        self.size = d["settings"]["size"]
        self.th = ts.THEMES[self.theme_name]
        self.lib_count = len(d["library"])
        self.snap = ts.get_snapshot()       # None -> Continue is greyed out

    def apply_theme(self):
        self.root.configure(bg=self.th["bg"])
        self.c.configure(bg=self.th["bg"])

    def get_logo(self):
        """The logo image for the current theme, or None if there isn't one."""
        name = self.theme_name
        if name in self._logos:
            return self._logos[name]
        img = None
        for fn in (f"{LOGO_FILE}_{name}.png", f"{LOGO_FILE}.png"):
            path = resource(os.path.join(LOGO_DIR, fn))
            if os.path.exists(path):
                try:
                    img = tk.PhotoImage(file=path)
                    try:                                    # smooth resize if Pillow is installed
                        from PIL import Image, ImageTk
                        im = Image.open(path).convert("RGBA")
                        w, h = im.size
                        im = im.resize((max(1, int(w * LOGO_SCALE)),
                                        max(1, int(h * LOGO_SCALE))), Image.LANCZOS)
                        img = ImageTk.PhotoImage(im)
                    except Exception:
                        img = scale_image(img, LOGO_SCALE)
                    break
                except tk.TclError:
                    img = None
        self._logos[name] = img
        return img

    # ------------------------------------------------------------ actions
    def dialog_alive(self):
        return self._dialog is not None and self._dialog.alive()

    @property
    def page(self):
        return self.target % len(PAGES)

    @property
    def animating(self):
        return self._anim_job is not None

    def page_items(self):
        return PAGES[self.page]

    def item_enabled(self, i):
        """i = row index on the CURRENT page."""
        return self.page_items()[i] != "continue" or self.snap is not None

    # ---- real-window behaviour (taskbar, minimize, close)
    def set_icon(self):
        for fn, kind in (("icon.ico", "ico"), ("icon.png", "png")):
            path = resource(os.path.join(LOGO_DIR, fn))
            if os.path.exists(path):
                try:
                    if kind == "ico":
                        self.root.iconbitmap(path)
                    else:
                        self._icon = tk.PhotoImage(file=path)
                        self.root.iconphoto(True, self._icon)
                    return
                except tk.TclError:
                    pass

    def _hwnd(self):
        import ctypes
        return ctypes.windll.user32.GetParent(self.root.winfo_id())

    def setup_taskbar(self):
        """Windows: frameless windows are hidden from the taskbar by default.
        Flip the style bits so ours gets a taskbar button (and Alt-Tab entry)."""
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            self.root.update_idletasks()
            u = ctypes.windll.user32
            hwnd = self._hwnd()
            style = u.GetWindowLongW(hwnd, -20)             # GWL_EXSTYLE
            style = (style & ~0x00000080) | 0x00040000      # - TOOLWINDOW, + APPWINDOW
            u.SetWindowLongW(hwnd, -20, style)
            self.root.withdraw()                            # re-show so Windows notices
            self.root.after(20, self.root.deiconify)
        except Exception:
            pass

    def minimize(self):
        if sys.platform.startswith("win"):
            try:
                import ctypes
                ctypes.windll.user32.ShowWindow(self._hwnd(), 6)    # SW_MINIMIZE
                return
            except Exception:
                pass
        # other systems can't minimize a frameless window: briefly give it a frame
        self._redirect_pending = True
        self.root.overrideredirect(False)
        self.root.iconify()

    def on_map(self, e):
        if e.widget is self.root and self._redirect_pending:
            self._redirect_pending = False
            self.root.after(30, lambda: self.root.overrideredirect(True))

    def wrects(self):
        """Custom title buttons, flush in the top-right corner."""
        w, h = WIN_BTN_W, WIN_BTN_H
        return {("win", "min"): (W - 2 * w - 1, 1, W - w - 1, 1 + h),
                ("win", "close"): (W - w - 1, 1, W - 1, 1 + h)}

    def draw_winbtns(self):
        c, th = self.c, self.th
        for key, (x0, y0, x1, y1) in self.wrects().items():
            hov = self.hot == key
            is_close = key[1] == "close"
            if hov:
                c.create_rectangle(x0, y0, x1, y1, outline="",
                                   fill="#c0392b" if is_close else th["btn_hover"])
                col = "#ffffff" if is_close else th["text"]
            else:
                col = th["dim"]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if is_close:
                c.create_line(cx - 5, cy - 5, cx + 5, cy + 5, fill=col, width=1.5)
                c.create_line(cx - 5, cy + 5, cx + 5, cy - 5, fill=col, width=1.5)
            else:
                c.create_line(cx - 5, cy + 3, cx + 5, cy + 3, fill=col, width=1.5)

    # ---- AFK
    def afk_max(self):
        return max(0, len(AFK_PROMPTS) * ROW - (H - ROW - HEADER))

    def afk_scroll_by(self, d, from_mouse=False):
        self.afk_target = min(max(self.afk_target + d, 0), self.afk_max())
        self._rehover = from_mouse
        if self._afk_job is None:
            self._afk_step()

    def _afk_step(self):
        d = self.afk_target - self.afk_scroll
        if abs(d) < 0.5:
            self.afk_scroll = self.afk_target
            self._afk_job = None
        else:
            self.afk_scroll += d * 0.3
            self._afk_job = self.root.after(16, self._afk_step)
        if self._rehover and self._mouse:           # row under a still mouse changes
            self.hot = self.hit(*self._mouse)
        self.draw()

    def afk_keep_visible(self, i):
        vh = H - ROW - HEADER
        top = i * ROW
        if top < self.afk_target:
            self.afk_scroll_by(top - self.afk_target)
        elif top + ROW > self.afk_target + vh:
            self.afk_scroll_by(top + ROW - vh - self.afk_target)

    def close_afk(self, *_):
        if self._afk_win is not None:
            try:
                self._afk_win.destroy()
            except tk.TclError:
                pass
        self._afk_win = None
        self._afk_keep = None

    def open_afk(self, i):
        """Show prompt i's image in the middle of the screen at AFK_SCREEN_FRACTION."""
        label, base, rnd = prompt_info(i)
        self.close_afk()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        maxw, maxh = int(sw * AFK_SCREEN_FRACTION), int(sh * AFK_SCREEN_FRACTION)
        path = pick_image(base, rnd, self._afk_last.get(base))
        if path:
            self._afk_last[base] = path
        img, note = None, ""
        if path:
            try:
                img = load_fitted(path, maxw, maxh, AFK_UPSCALE)
            except Exception as ex:
                note = f"Couldn't load {os.path.basename(path)} ({type(ex).__name__})"
        else:
            note = f"Add  {AFK_DIR.replace(os.sep, '/')}/{base}.png"

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=self.th["edge"])
        if img is not None:
            w, h = img.width(), img.height()
            body = tk.Label(win, image=img, bd=0, highlightthickness=0, cursor="hand2")
            self._afk_keep = img
        else:                                       # no image yet: draw a stand-in card
            w = int(min(maxw, maxh * 16 / 9))
            h = int(w * 9 / 16)
            fs = ts.make_fonts(max(1.0, w / 520))
            body = tk.Canvas(win, width=w, height=h, highlightthickness=0, bd=0,
                             cursor="hand2")
            ts.vgrad(body, 0, 0, w, h, self.th["head_top"], self.th["head_bot"])
            body.create_text(w / 2, h / 2 - h * 0.05, text=label, font=fs.clock,
                             fill=self.th["text"])
            body.create_text(w / 2, h / 2 + h * 0.12, text=note, font=fs.menu,
                             fill=self.th["dim"])
            self._afk_keep = fs
        body.pack(padx=2, pady=2)
        win.geometry(f"{w + 4}x{h + 4}+{(sw - w - 4) // 2}+{(sh - h - 4) // 2}")
        for wd in (win, body):
            wd.bind("<Button-1>", self.close_afk)
        win.bind("<Escape>", self.close_afk)
        win.bind("<Key>", self.close_afk)
        self._afk_win = win
        detach_owner(win)           # stays up even if the menu is minimized
        win.after(50, win.focus_force)

    # ---- page sliding
    def slide(self, d):
        """Go d pages right (negative = left). Wraps around."""
        self.target += d
        self.hot = None
        self._start_anim()

    def go(self, p):
        """Jump to page p by the shortest way round."""
        n = len(PAGES)
        diff = (p - self.page) % n
        if diff > n / 2:
            diff -= n
        if diff:
            self.slide(diff)

    def _start_anim(self):
        if self._anim_job is None:
            self._step()

    def _step(self):
        d = self.target - self.pos
        if abs(d) < 0.004:
            n = len(PAGES)
            self.target %= n
            self.pos = float(self.target)
            self._anim_job = None
        else:
            self.pos += d * 0.26
            self._anim_job = self.root.after(16, self._step)
        self.draw()

    def on_wheel(self, e):
        if self.dialog_alive():
            return
        up = getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0
        if self.view == "afk":
            notches = abs(getattr(e, "delta", 0)) / 120 or 1
            step = min(3.0, notches) * ROW * 0.75
            self.afk_scroll_by(-step if up else step, from_mouse=True)
            return
        if self.view != "home" or self.animating:
            return
        self.slide(-1 if up else 1)

    def snap_summary(self):
        s = self.snap
        n = len(s["tasks"])
        done = min(len(s.get("splits", [])), n)
        return f"{done}/{n}  \u2022  {ts.fmt(float(s.get('elapsed', 0)))}"

    def act(self, name):
        if self.dialog_alive():
            self._dialog.focus()
            return
        if name == "continue":
            snap = ts.get_snapshot()
            if snap:
                self.result = {"snapshot": snap}
                self.root.quit()
        elif name == "start":
            self.open_editor(ts.load_data()["last"])
        elif name == "library":
            self._dialog = ts.LibraryDialog(self.root, self.th, self.f,
                                            on_pick=self.open_editor, action_text="Open")
        elif name == "settings":
            self.view, self.hot = "settings", None
        elif name == "afk":
            self.view, self.hot = "afk", None
            self.afk_scroll = self.afk_target = 0.0
            self.afk_has = {p[1]: len(find_images(p[1])) for p in AFK_PROMPTS}
        elif name == "quit":
            self.quit()
        # ph3 / ph4 are placeholders: they do nothing yet

    def open_editor(self, s):
        self._dialog = ts.TaskEditor(
            self.root, self.th, self.f,
            s.get("title", "Daily Tasks"), s.get("subtitle", ""), s.get("tasks", []),
            "Start", self.begin, heading="New Run",
            subheading="Set up your tasks, then hit Start")

    def begin(self, title, subtitle, tasks):
        d = ts.load_data()
        d["last"] = {"title": title, "subtitle": subtitle, "tasks": tasks}
        ts.save_data(d)
        self.result = {"title": title, "subtitle": subtitle, "tasks": tasks}
        self.root.quit()

    def quit(self):
        self.result = None
        self.root.quit()

    def set_setting(self, kind, name):
        d = ts.load_data()
        d["settings"][kind] = name
        ts.save_data(d)
        self.reload()
        self.apply_theme()

    def activate(self, key):
        if isinstance(key, tuple) and key[0] == "win":
            if key[1] == "min":
                self.minimize()
            else:
                self.quit()
            return
        if self.view == "home":
            if isinstance(key, tuple):
                if key[0] == "page":
                    self.slide(key[1])
                else:
                    self.go(key[1])
            else:
                self.act(self.page_items()[key])
        elif self.view == "afk":
            if key == "back":
                self.view, self.hot = "home", None
            else:
                self.open_afk(key[1])
        elif key == "back":
            self.view, self.hot = "home", None
        else:
            self.set_setting(*key)

    # ------------------------------------------------------------ input
    def srects(self):
        pad, gap = 18, 6
        cw = W - 2 * pad
        r = {}
        names = list(ts.SIZES)
        w = (cw - gap * (len(names) - 1)) / len(names)
        for i, n in enumerate(names):
            x0 = pad + i * (w + gap)
            r[("size", n)] = (x0, 114, x0 + w, 148)
        w2 = (cw - gap) / 2
        for i, n in enumerate(("dark", "light")):
            x0 = pad + i * (w2 + gap)
            r[("theme", n)] = (x0, 198, x0 + w2, 232)
        r["back"] = (0, H - ROW, W, H)
        return r

    def prects(self):
        """Page bar hit areas: arrows on the sides, one cell per dot in the middle."""
        y0 = H - PAGER_H
        y1 = H
        r = {("page", -1): (12, y0 + 5, 52, y1 - 5),
             ("page", 1): (W - 52, y0 + 5, W - 12, y1 - 5)}
        n = len(PAGES)
        gap = 22
        x = W / 2 - (n - 1) * gap / 2
        for i in range(n):
            r[("dot", i)] = (x + i * gap - gap / 2, y0, x + i * gap + gap / 2, y1)
        return r

    def hit(self, x, y):
        if y < 1 + WIN_BTN_H:
            for key, (x0, y0, x1, y1) in self.wrects().items():
                if x0 <= x <= x1 and y0 <= y <= y1:
                    return key
        if self.view == "home":
            if self.animating:
                return None
            if HEADER <= y < HEADER + BODY_H:
                i = int((y - HEADER) // ROW)
                if i >= len(self.page_items()):
                    return None
                return i if self.item_enabled(i) else None   # greyed row: no hover/click
            for key, (x0, y0, x1, y1) in self.prects().items():
                if x0 <= x <= x1 and y0 <= y <= y1:
                    return key
            return None
        if self.view == "afk":
            if y >= H - ROW:
                return "back"
            if HEADER <= y < H - ROW:
                i = int((y - HEADER + self.afk_scroll) // ROW)
                if 0 <= i < len(AFK_PROMPTS):
                    return ("afk", i)
            return None
        for key, (x0, y0, x1, y1) in self.srects().items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return key
        return None

    def on_motion(self, e):
        self._mouse = (e.x, e.y)
        h = self.hit(e.x, e.y)
        if h != self.hot:
            self.hot = h
            self.c.config(cursor="hand2" if h is not None else "")
            self.draw()

    def on_leave(self, e):
        self._mouse = None
        if self.hot is not None:
            self.hot = None
            self.c.config(cursor="")
            self.draw()

    def on_press(self, e):
        self._press = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())
        self._press_hot = self.hit(e.x, e.y)
        self._press_y = e.y
        self._moved = False

    def on_drag(self, e):
        if self._press_hot is not None:
            return
        px, py, wx, wy = self._press
        dx, dy = e.x_root - px, e.y_root - py
        if abs(dx) + abs(dy) > 4:
            self._moved = True
        if self._moved:
            self.root.geometry(f"+{wx + dx}+{wy + dy}")

    def on_release(self, e):
        h = self._press_hot
        self._press_hot = None
        if h is not None and not self._moved and self.hit(e.x, e.y) == h:
            self.activate(h)
            self.draw()

    def on_key(self, e):
        if self.dialog_alive():
            return
        k = e.keysym
        if self.view == "home":
            n = len(self.page_items())

            def step(d):
                i = self.hot if self.hot is not None else (-1 if d > 0 else n)
                for _ in range(n):
                    i = (i + d) % n
                    if self.item_enabled(i):
                        return i
                return None

            if k == "Left":
                self.slide(-1)
            elif k == "Right":
                self.slide(1)
            elif k in ("1", "2", "3", "4") and int(k) <= len(PAGES):
                self.go(int(k) - 1)
            elif k == "Down":
                self.hot = step(1)
            elif k == "Up":
                self.hot = step(-1)
            elif k in ("Return", "KP_Enter") and self.hot is not None:
                self.activate(self.hot)
        elif self.view == "afk":
            n = len(AFK_PROMPTS)
            cur = self.hot[1] if isinstance(self.hot, tuple) else None
            if k in ("Down", "Up"):
                cur = (0 if k == "Down" else n - 1) if cur is None else \
                    (cur + (1 if k == "Down" else -1)) % n
                self.hot = ("afk", cur)
                self.afk_keep_visible(cur)
            elif k in ("Return", "KP_Enter") and cur is not None:
                self.open_afk(cur)
            elif k == "Escape":
                self.view, self.hot = "home", None
        elif k == "Escape":
            self.view, self.hot = "home", None
        self.draw()

    # ------------------------------------------------------------ drawing
    def header(self, title, sub, logo=False):
        c, th, f = self.c, self.th, self.f
        ts.vgrad(c, 0, 0, W, HEADER, th["head_top"], th["head_bot"])
        c.create_line(0, HEADER - 1, W, HEADER - 1, fill=th["head_line"])
        img = self.get_logo() if logo else None
        if img:
            y = HEADER // 2 + LOGO_Y
            if LOGO_CENTER:
                c.create_image(W // 2, y, anchor="center", image=img)
            else:
                c.create_image(LOGO_X, y, anchor="w", image=img)
        else:
            c.create_text(20, 34, anchor="w", text=title, font=f.h1, fill=th["text"])
            c.create_text(20, 60, anchor="w", text=sub, font=f.sub, fill=th["dim"])

    def icon(self, name, cx, cy, col):
        """Small line icons drawn on the canvas, same style as the overlay's buttons."""
        c = self.c
        if name == "continue":      # play
            c.create_polygon(cx - 5, cy - 8, cx - 5, cy + 8, cx + 8, cy,
                             fill=col, outline=col, joinstyle="round")
        elif name == "start":       # plus (new run)
            c.create_line(cx - 8, cy, cx + 8, cy, fill=col, width=3, capstyle="round")
            c.create_line(cx, cy - 8, cx, cy + 8, fill=col, width=3, capstyle="round")
        elif name == "library":     # folder
            c.create_rectangle(cx - 9, cy - 8, cx - 1, cy - 4, fill=col, outline=col)
            c.create_rectangle(cx - 9, cy - 5, cx + 9, cy + 8, fill="", outline=col, width=2)
        elif name == "settings":    # sliders
            for y, kx in ((cy - 6, cx - 3), (cy, cx + 4), (cy + 6, cx - 1)):
                c.create_line(cx - 9, y, cx + 9, y, fill=col, width=2)
                c.create_oval(kx - 3, y - 3, kx + 3, y + 3, fill=col, outline=col)
        elif name == "quit":        # power symbol
            c.create_arc(cx - 8, cy - 7, cx + 8, cy + 9, start=120, extent=300,
                         style="arc", outline=col, width=2)
            c.create_line(cx, cy - 10, cx, cy, fill=col, width=2, capstyle="round")
        elif name == "afk":         # crescent moon
            c.create_polygon(moon_points(cx, cy), fill=col, outline=col, joinstyle="round")
        elif name == "image":       # picture frame
            c.create_rectangle(cx - 9, cy - 7, cx + 9, cy + 7, fill="", outline=col, width=2)
            c.create_polygon(cx - 7, cy + 5, cx - 2, cy - 1, cx + 2, cy + 3, cx + 4, cy + 1,
                             cx + 7, cy + 5, fill=col, outline=col)
            c.create_oval(cx + 3, cy - 5, cx + 6, cy - 2, fill=col, outline=col)
        elif name in ("ph3", "ph4"):            # diamond
            c.create_polygon(cx, cy - 9, cx + 9, cy, cx, cy + 9, cx - 9, cy,
                             fill="", outline=col, width=2)
        elif name == "back":        # left arrow
            c.create_line(cx + 8, cy, cx - 8, cy, fill=col, width=2, capstyle="round")
            c.create_line(cx - 2, cy - 6, cx - 8, cy, cx - 2, cy + 6, fill=col, width=2,
                          capstyle="round", joinstyle="round")

    def row(self, y0, label, sub, hot, danger=False, icon=None, disabled=False, ox=0):
        c, th, f = self.c, self.th, self.f
        y1 = y0 + ROW
        if disabled:
            c.create_line(ox, y1 - 1, ox + W, y1 - 1, fill=th["sep"])
            tcol = scol = icol = ts.lerp(th["bg"], th["dim"], 0.5)
        elif hot:
            top, bot = ("#c0392b", "#8e1f14") if danger else (th["cur_top"], th["cur_bot"])
            ts.vgrad(c, ox, y0, ox + W, y1, top, bot)
            tcol, scol = th["cur_text"], "#ffd9d4" if danger else "#d6e4ff"
            icol = th["cur_text"]
        else:
            c.create_line(ox, y1 - 1, ox + W, y1 - 1, fill=th["sep"])
            tcol, scol = th["text"], th["dim"]
            icol = th["red"] if danger else th["finish"]
        mid = (y0 + y1) / 2
        lx = 20
        if icon:
            self.icon(icon, ox + 36, mid, icol)
            lx = 62
        c.create_text(ox + lx, mid, anchor="w", text=label, font=f.menu, fill=tcol)
        if sub:
            c.create_text(ox + W - 20, mid, anchor="e", text=sub, font=f.row, fill=scol)

    def draw_pager(self, y0):
        c, th = self.c, self.th
        # same gradient as the header, flipped line on top
        ts.vgrad(c, 0, y0, W, H, th["head_top"], th["head_bot"])
        c.create_line(0, y0, W, y0, fill=th["head_line"])
        for key, (x0, ya, x1, yb) in self.prects().items():
            kind, v = key
            mid = (ya + yb) / 2
            cx = (x0 + x1) / 2
            hov = self.hot == key
            if kind == "page":
                fill = th["btn_hover"] if hov else th["btn_fill"]
                edge = th["btn_edge_hover"] if hov else th["btn_edge"]
                c.create_rectangle(x0, ya, x1, yb, fill=fill, outline=edge)
                col = th["icon_hover"] if hov else th["icon"]
                d = -1 if v < 0 else 1
                c.create_line(cx - 3 * d, mid - 6, cx + 3 * d, mid, cx - 3 * d, mid + 6,
                              fill=col, width=2, capstyle="round", joinstyle="round")
            else:
                active = v == self.page
                r = 4.5 if active else (4 if hov else 3)
                col = th["accent"] if active else (th["icon_hover"] if hov else th["btn_edge_hover"])
                c.create_oval(cx - r, mid - r, cx + r, mid + r, fill=col, outline=col)

    def draw_home(self):
        c, th, f = self.c, self.th, self.f
        title, sub = PAGE_TITLES[self.page]
        self.header(title, sub, logo=(self.page == 0))
        subs = {
            "continue": self.snap_summary() if self.snap else "no saved run",
            "start": "new run",
            "library": (f"{self.lib_count} set{'s' if self.lib_count != 1 else ''}"
                        if self.lib_count else "none yet"),
            "settings": f"{self.theme_name.title()}  \u2022  {self.size}",
            "quit": "",
            "afk": f"{len(AFK_PROMPTS)} screens",
        }
        # sliding pages: draw every page copy that is (partly) on screen
        n = len(PAGES)
        for p in range(n):
            for k in (-1, 0, 1):
                ox = (p + k * n - self.pos) * W
                if not -W < ox < W:
                    continue
                for i, name in enumerate(PAGES[p]):
                    here = (p == self.page and not self.animating)
                    self.row(HEADER + i * ROW, LABELS[name], subs.get(name, "coming soon"),
                             here and self.hot == i, danger=(name == "quit"), icon=name,
                             disabled=(name == "continue" and self.snap is None), ox=ox)

        # footer clock lives on page 1 only, so it slides in/out with that page
        for k in (-1, 0, 1):
            ox = (k * n - self.pos) * W
            if -W < ox < W:
                self.draw_clock(HEADER + BODY_H, ox)

        self.draw_pager(H - PAGER_H)

    def draw_clock(self, y0, ox):
        """A live clock, styled like the overlay's timer."""
        c, th, f = self.c, self.th, self.f
        c.create_line(ox, y0, ox + W, y0, fill=th["footer_line"])
        now = datetime.datetime.now()
        main, dec = now.strftime("%H:%M"), now.strftime(":%S")
        right = ox + W - 20
        base_y = y0 + 58
        c.create_text(right, base_y, anchor="se", text=dec, font=f.clockdec, fill=th["green"])
        c.create_text(right - f.clockdec.measure(dec), base_y + 2, anchor="se",
                      text=main, font=f.clock, fill=th["green"])
        c.create_text(ox + 20, y0 + 82, anchor="w", text="LOCAL TIME", font=f.lbl, fill=th["dim"])
        c.create_text(right, y0 + 82, anchor="e", text=now.strftime("%a %d %b").upper(),
                      font=f.lbl, fill=th["dim"])

    def seg(self, r, label, active, hot, swatch=None):
        c, th, f = self.c, self.th, self.f
        x0, y0, x1, y1 = r
        if active:
            fill, edge, fg = th["accent"], th["accent_edge"], th["accent_text"]
        elif hot:
            fill, edge, fg = th["btn_hover"], th["btn_edge_hover"], th["text"]
        else:
            fill, edge, fg = th["btn_fill"], th["btn_edge"], th["dim"]
        c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=edge)
        mid = (y0 + y1) / 2
        tx = (x0 + x1) / 2
        if swatch:
            t = ts.THEMES[swatch]
            c.create_rectangle(x0 + 18, mid - 7, x0 + 32, mid + 7,
                               fill=t["bg"], outline="#8a8a8a")
            tx += 10
        c.create_text(tx, mid, text=label, font=f.rowb, fill=fg)

    def preview(self, top):
        c, th, f = self.c, self.th, self.f
        p = 0.45 * ts.SIZES[self.size]
        cw = 300 * p
        x0 = (W - cw) / 2
        hh, rh, fh = 40 * p, 24 * p, 40 * p
        ch = hh + 2 * rh + fh
        c.create_rectangle(x0 - 1, top - 1, x0 + cw + 1, top + ch + 1,
                           outline=th["edge"], fill=th["bg"])
        ts.vgrad(c, x0, top, x0 + cw, top + hh, th["head_top"], th["head_bot"])
        c.create_rectangle(x0 + 10 * p, top + 11 * p, x0 + 100 * p, top + 19 * p,
                           fill=th["text"], outline="")
        c.create_rectangle(x0 + 10 * p, top + 25 * p, x0 + 70 * p, top + 30 * p,
                           fill=th["dim"], outline="")
        y = top + hh
        ts.vgrad(c, x0, y, x0 + cw, y + rh, th["cur_top"], th["cur_bot"])
        c.create_rectangle(x0 + 10 * p, y + 9 * p, x0 + 80 * p, y + 15 * p,
                           fill=th["cur_text"], outline="")
        c.create_rectangle(x0 + cw - 48 * p, y + 9 * p, x0 + cw - 10 * p, y + 15 * p,
                           fill=th["cur_text"], outline="")
        y += rh
        c.create_rectangle(x0 + 10 * p, y + 9 * p, x0 + 70 * p, y + 15 * p,
                           fill=th["upcoming"], outline="")
        c.create_rectangle(x0 + cw - 48 * p, y + 9 * p, x0 + cw - 10 * p, y + 15 * p,
                           fill=th["dim"], outline="")
        y += rh
        c.create_line(x0, y, x0 + cw, y, fill=th["footer_line"])
        c.create_text(x0 + cw - 10 * p, y + fh / 2, anchor="e", text="0:12:34",
                      font=f.rowb, fill=th["green"])

    def draw_settings(self):
        c, th, f = self.c, self.th, self.f
        self.header("Settings", "CHANGES APPLY INSTANTLY")
        c.create_text(18, 100, anchor="w", text="OVERLAY SIZE", font=f.lbl, fill=th["dim"])
        c.create_text(18, 184, anchor="w", text="THEME", font=f.lbl, fill=th["dim"])
        rects = self.srects()
        for key, r in rects.items():
            if key == "back":
                continue
            kind, name = key
            if kind == "size":
                self.seg(r, name, name == self.size, self.hot == key)
            else:
                self.seg(r, name.title(), name == self.theme_name, self.hot == key, swatch=name)
        width = int(300 * ts.SIZES[self.size])
        c.create_text(W - 18, 100, anchor="e", text=f"{width} px wide", font=f.lbl, fill=th["dim"])
        c.create_text(18, 250, anchor="w", text="PREVIEW", font=f.lbl, fill=th["dim"])
        self.preview(262)
        self.row(H - ROW, "Back", "Esc", self.hot == "back", icon="back")

    def draw_afk(self):
        c, th = self.c, self.th
        for i in range(len(AFK_PROMPTS)):
            label, base, rnd = prompt_info(i)
            y0 = HEADER + i * ROW - self.afk_scroll
            if y0 + ROW <= HEADER or y0 >= H - ROW:
                continue
            cnt = self.afk_has.get(base, 0)
            sub = ("no image" if not cnt else
                   f"random \u2022 {cnt}" if rnd and cnt > 1 else "")
            self.row(y0, label, sub, self.hot == ("afk", i), icon="image")
        self.header("AFK", "PICK A REASON TO SHOW")      # opaque: covers rows scrolled under it
        mx = self.afk_max()
        if mx > 0:                                       # slim scrollbar
            top, bot = HEADER + 6, H - ROW - 6
            th_h = max(24, (bot - top) * (H - ROW - HEADER) / (len(AFK_PROMPTS) * ROW))
            ty = top + (bot - top - th_h) * (self.afk_scroll / mx)
            c.create_rectangle(W - 6, top, W - 3, bot, fill=th["sep"], outline="")
            c.create_rectangle(W - 6, ty, W - 3, ty + th_h, fill=th["btn_edge_hover"], outline="")
        c.create_rectangle(0, H - ROW, W, H, fill=th["bg"], outline="")
        self.row(H - ROW, "Back", "Esc", self.hot == "back", icon="back")

    def draw(self):
        c = self.c
        c.delete("all")
        if self.view == "home":
            self.draw_home()
        elif self.view == "afk":
            self.draw_afk()
        else:
            self.draw_settings()
        self.draw_winbtns()
        c.create_rectangle(0, 0, W - 1, H - 1, outline=self.th["edge"])

    # ------------------------------------------------------------ loop
    def tick(self):
        open_now = self.dialog_alive()
        if self._was_open and not open_now:
            self.reload()
        self._was_open = open_now
        self.draw()
        self.root.after(250, self.tick)

    def run(self):
        self.tick()
        self.root.after(30, self.setup_taskbar)
        self.root.after(150, self.root.focus_force)
        self.root.mainloop()
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        return self.result


def main():
    while True:
        res = MainMenu().run()
        if res is None:
            break                                   # Quit
        if "snapshot" in res:                       # Continue
            ts.TaskSplit(snapshot=res["snapshot"]).run()
        else:                                       # Start New
            ts.TaskSplit(res["title"], res["subtitle"], res["tasks"]).run()
        # overlay closed -> loop around and show the main menu again


if __name__ == "__main__":
    main()