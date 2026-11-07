#!/usr/bin/env python3
"""
TaskSplit - main menu.   Run this file:   python mainmenu.py

Keep it in the same folder as tsv2.py.
  Continue     -> pick up the run you left off (greyed out if there is none)
  Start New    -> task editor -> Start -> the speedrun overlay opens
               (right-click the overlay -> "Quit to main menu" saves your run)
  Saved Tasks  -> your library of saved task sets (save from any task editor)
  Settings     -> overlay size + dark / light theme
  Quit         -> close the app
"""
import datetime
import tkinter as tk

import tsv2 as ts

W, H = 340, 480
HEADER = 80
ROW = 58
ITEMS = ("continue", "start", "library", "settings", "quit")
LABELS = {"continue": "Continue", "start": "Start New", "library": "Saved Tasks",
          "settings": "Settings", "quit": "Quit"}


class MainMenu:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TaskSplit")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.f = ts.make_fonts(1.0)

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

        self.c.bind("<Motion>", self.on_motion)
        self.c.bind("<Leave>", self.on_leave)
        self.c.bind("<ButtonPress-1>", self.on_press)
        self.c.bind("<B1-Motion>", self.on_drag)
        self.c.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Key>", self.on_key)
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

    # ------------------------------------------------------------ actions
    def dialog_alive(self):
        return self._dialog is not None and self._dialog.alive()

    def item_enabled(self, i):
        return ITEMS[i] != "continue" or self.snap is not None

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
        elif name == "quit":
            self.quit()

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
        if self.view == "home":
            self.act(ITEMS[key])
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

    def hit(self, x, y):
        if self.view == "home":
            if HEADER <= y < HEADER + len(ITEMS) * ROW:
                i = int((y - HEADER) // ROW)
                return i if self.item_enabled(i) else None   # greyed row: no hover/click
            return None
        for key, (x0, y0, x1, y1) in self.srects().items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return key
        return None

    def on_motion(self, e):
        h = self.hit(e.x, e.y)
        if h != self.hot:
            self.hot = h
            self.c.config(cursor="hand2" if h is not None else "")
            self.draw()

    def on_leave(self, e):
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
            n = len(ITEMS)

            def step(d):
                i = self.hot if self.hot is not None else (-1 if d > 0 else n)
                for _ in range(n):
                    i = (i + d) % n
                    if self.item_enabled(i):
                        return i
                return None

            if k == "Down":
                self.hot = step(1)
            elif k == "Up":
                self.hot = step(-1)
            elif k in ("Return", "KP_Enter") and self.hot is not None:
                self.activate(self.hot)
        elif k == "Escape":
            self.view, self.hot = "home", None
        self.draw()

    # ------------------------------------------------------------ drawing
    def header(self, title, sub):
        c, th, f = self.c, self.th, self.f
        ts.vgrad(c, 0, 0, W, HEADER, th["head_top"], th["head_bot"])
        c.create_line(0, HEADER - 1, W, HEADER - 1, fill=th["head_line"])
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
        elif name == "back":        # left arrow
            c.create_line(cx + 8, cy, cx - 8, cy, fill=col, width=2, capstyle="round")
            c.create_line(cx - 2, cy - 6, cx - 8, cy, cx - 2, cy + 6, fill=col, width=2,
                          capstyle="round", joinstyle="round")

    def row(self, y0, label, sub, hot, danger=False, icon=None, disabled=False):
        c, th, f = self.c, self.th, self.f
        y1 = y0 + ROW
        if disabled:
            c.create_line(0, y1 - 1, W, y1 - 1, fill=th["sep"])
            tcol = scol = icol = ts.lerp(th["bg"], th["dim"], 0.5)
        elif hot:
            top, bot = ("#c0392b", "#8e1f14") if danger else (th["cur_top"], th["cur_bot"])
            ts.vgrad(c, 0, y0, W, y1, top, bot)
            tcol, scol = th["cur_text"], "#ffd9d4" if danger else "#d6e4ff"
            icol = th["cur_text"]
        else:
            c.create_line(0, y1 - 1, W, y1 - 1, fill=th["sep"])
            tcol, scol = th["text"], th["dim"]
            icol = th["red"] if danger else th["finish"]
        mid = (y0 + y1) / 2
        lx = 20
        if icon:
            self.icon(icon, 36, mid, icol)
            lx = 62
        c.create_text(lx, mid, anchor="w", text=label, font=f.menu, fill=tcol)
        if sub:
            c.create_text(W - 20, mid, anchor="e", text=sub, font=f.row, fill=scol)

    def draw_home(self):
        c, th, f = self.c, self.th, self.f
        self.header("TaskSplit", "DAILY TASK SPLITS")
        subs = {
            "continue": self.snap_summary() if self.snap else "no saved run",
            "start": "",
            "library": (f"{self.lib_count} set{'s' if self.lib_count != 1 else ''}"
                        if self.lib_count else "none yet"),
            "settings": f"{self.theme_name.title()}  \u2022  {self.size}",
            "quit": "",
        }
        for i, k in enumerate(ITEMS):
            self.row(HEADER + i * ROW, LABELS[k], subs[k], self.hot == i,
                     danger=(k == "quit"), icon=k, disabled=not self.item_enabled(i))

        # footer: a live clock, styled like the overlay's timer
        y0 = HEADER + len(ITEMS) * ROW
        c.create_line(0, y0, W, y0, fill=th["footer_line"])
        now = datetime.datetime.now()
        main, dec = now.strftime("%H:%M"), now.strftime(":%S")
        right = W - 20
        base_y = y0 + 58
        c.create_text(right, base_y, anchor="se", text=dec, font=f.clockdec, fill=th["green"])
        c.create_text(right - f.clockdec.measure(dec), base_y + 2, anchor="se",
                      text=main, font=f.clock, fill=th["green"])
        c.create_text(20, y0 + 82, anchor="w", text="LOCAL TIME", font=f.lbl, fill=th["dim"])
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

    def draw(self):
        c = self.c
        c.delete("all")
        if self.view == "home":
            self.draw_home()
        else:
            self.draw_settings()
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
        self.root.after(100, self.root.focus_force)
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