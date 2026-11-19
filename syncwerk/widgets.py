"""Gemeinsame Bausteine der Oberfläche – tastaturbedienbar und mit Sprachausgabe."""
import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

from . import APP_NAME
from . import theme as T
from .theme import C, F

IS_WIN = sys.platform.startswith("win")

# ---------------------------------------------------------------- Sprachausgabe (global)
_SPK = [None]


def set_speaker(spk):
    _SPK[0] = spk


def say(text, interrupt=True):
    if _SPK[0] is not None:
        _SPK[0].say(text, interrupt)


def speech_on():
    return bool(_SPK[0] and _SPK[0].enabled)


def acc(widget, label, value=None):
    """Beim Fokussieren Bezeichnung (+ aktuellen Wert) vorlesen."""
    def on_focus(_e=None):
        v = ""
        if value:
            try:
                v = value()
            except Exception:  # noqa: BLE001
                v = ""
        say(f"{label}. {v}" if v else label)
    widget.bind("<FocusIn>", on_focus, add="+")


# Meldungsfenster im SyncWerk-Stil (dunkel, Symbol-Quadrat, Fußleiste) – werden vorgelesen
def _parent(p):
    return p or tk._default_root


def info(title, text, parent=None):
    return MessageDialog(_parent(parent), "info", title, text).result


def warn(title, text, parent=None):
    return MessageDialog(_parent(parent), "warn", title, text).result


def error(title, text, parent=None):
    return MessageDialog(_parent(parent), "error", title, text).result


def ask(title, text, parent=None, risky=False):
    d = MessageDialog(_parent(parent), "warn" if risky else "ask", title, text,
                      buttons=(("Ja", True), ("Nein", False)), default=1 if risky else 0)
    return bool(d.result)


def ask_string(title, prompt, parent=None, initial=""):
    d = MessageDialog(_parent(parent), "ask", title, prompt,
                      buttons=(("OK", True), ("Abbrechen", False)), entry=initial)
    return d.value.strip() if d.result and d.value.strip() else None


def dark_titlebar(win):
    """Windows 10/11: dunkle Titelleiste im Dunkel- und Kontrastmodus."""
    if not IS_WIN:
        return
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        val = ctypes.c_int(0 if T.name() == "hell" else 1)
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), 4) == 0:
                break
    except (AttributeError, OSError):
        pass


# ---------------------------------------------------------------- Menüs (grau, weiße Schrift)
def _menu_speak(m):
    try:
        i = m.index("active")
        if i is None or m.type(i) in ("separator", "tearoff"):
            return
        lab = m.entrycget(i, "label")
        accel = m.entrycget(i, "accelerator")
        state = ""
        if m.type(i) in ("checkbutton", "radiobutton"):
            var = m.entrycget(i, "variable")
            if var:
                cur = m.getvar(var)
                on = (str(cur) in ("1", "True")) if m.type(i) == "checkbutton" \
                    else str(cur) == str(m.entrycget(i, "value"))
                state = ", aktiviert" if on else ", nicht aktiviert"
        say(f"{lab}{state}" + (f", {accel}" if accel else ""))
    except tk.TclError:
        pass


def style_menu(m):
    m.configure(bg=C["menu_bg"], fg=C["menu_text"], activebackground=C["accent"],
                activeforeground=C["accent_text"], disabledforeground=C["dis_text"],
                selectcolor=C["accent"], relief="flat", bd=1, activeborderwidth=0, font=F(10))
    m.bind("<<MenuSelect>>", lambda e: _menu_speak(m))
    return m


def dark_menu(parent):
    return style_menu(tk.Menu(parent, tearoff=0))


class MenuBar(tk.Frame):
    """Eigene Menüleiste (die Windows-Standardleiste lässt sich nicht einfärben).
    Alt+Buchstabe oder F10 öffnet, Pfeile links/rechts wechseln, Pfeil runter/Enter öffnet."""

    def __init__(self, parent):
        super().__init__(parent, bg=C["menubar"])
        self.items = []

    def add(self, label, underline=0):
        m = dark_menu(self)
        i = len(self.items)
        b = tk.Label(self, text=label, bg=C["menubar"], fg=C["menu_text"], font=F(10), padx=10, pady=4,
                     underline=underline, takefocus=1, highlightthickness=1,
                     highlightcolor=C["focus"], highlightbackground=C["menubar"])
        b.pack(side="left")
        b.bind("<Enter>", lambda e: b.config(bg=C["menu_hover"]))
        b.bind("<Leave>", lambda e: b.config(bg=C["menubar"]))
        b.bind("<ButtonRelease-1>", lambda e: self.open(i))
        for k in ("<Return>", "<space>", "<Down>"):
            b.bind(k, lambda e: (self.open(i), "break")[1])
        b.bind("<Left>", lambda e: (self.items[(i - 1) % len(self.items)][0].focus_set(), "break")[1])
        b.bind("<Right>", lambda e: (self.items[(i + 1) % len(self.items)][0].focus_set(), "break")[1])
        b.bind("<FocusIn>", lambda e: say(f"Menü {label}. Pfeil nach unten öffnet, Pfeile links und rechts "
                                          "wechseln das Menü"), add="+")
        self.items.append((b, m, label))
        return m

    def key(self, i):
        return self.items[i][2][self.items[i][0].cget("underline")].lower()

    def open(self, i):
        b, m, label = self.items[i]
        b.config(bg=C["accent"], fg=C["accent_text"])
        say(f"Menü {label} geöffnet")
        try:
            m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
        finally:
            m.grab_release()
            b.config(bg=C["menubar"], fg=C["menu_text"])


class MessageDialog(tk.Toplevel):
    """Meldung/Frage im Stil von FotoRahmen: Symbol-Quadrat, Text, Fußleiste mit Knöpfen."""
    ICON = {"info": ("i", "accent", "#1c1c1f"), "ask": ("?", "accent", "#1c1c1f"),
            "warn": ("!", "yellow", "#1c1c1f"), "error": ("✕", "red", "#ffffff")}
    SPEAK = {"info": "", "ask": "Frage. ", "warn": "Warnung. ", "error": "Fehler. "}

    def __init__(self, parent, kind, title, text, buttons=(("OK", True),), default=0, entry=None,
                 bold_first=False):
        super().__init__(parent)
        self.result = buttons[-1][1] if len(buttons) > 1 else buttons[0][1]
        self.value = ""
        self.withdraw()
        self.title(title)
        self.configure(bg=C["panel"])
        self.resizable(False, False)
        try:
            self.transient(parent.winfo_toplevel())
        except tk.TclError:
            pass
        try:
            self.iconbitmap(resource("SyncWerk.ico"))
        except tk.TclError:
            pass
        body = tk.Frame(self, bg=C["panel"], padx=24, pady=22)
        body.pack(fill="both", expand=True)
        sym, col, fg = self.ICON.get(kind, self.ICON["info"])
        if T.is_hc():
            fg = "#000000"
        sz = int(46 * T.scale())
        box = tk.Frame(body, bg=C[col], width=sz, height=sz)
        box.grid(row=0, column=0, rowspan=2, sticky="n")
        box.pack_propagate(False)
        tk.Label(box, text=sym, bg=C[col], fg=fg, font=F(20, "bold")).pack(expand=True)
        wrap = int(440 * T.scale())
        lines = str(text).split("\n")
        if bold_first and lines:
            tk.Label(body, text=lines[0], bg=C["panel"], fg=C["text"], font=F(12, "bold"), justify="left",
                     anchor="w", wraplength=wrap).grid(row=0, column=1, sticky="nw", padx=(18, 0))
            rest = "\n".join(lines[1:])
        else:
            rest = str(text)
        tk.Label(body, text=rest, bg=C["panel"], fg=C["text"], font=F(11), justify="left", anchor="w",
                 wraplength=wrap).grid(row=1 if bold_first else 0, column=1, sticky="nw", padx=(18, 0))
        self.entry = None
        if entry is not None:
            self.var = tk.StringVar(value=entry)
            self.entry = ttk.Entry(body, textvariable=self.var, font=F(11), width=34)
            self.entry.grid(row=2, column=1, sticky="we", padx=(18, 0), pady=(10, 0))
            self.entry.bind("<FocusIn>", lambda e: say(f"Eingabefeld. {self.var.get()}"), add="+")
        foot = tk.Frame(self, bg=C["footer"], padx=16, pady=12,
                        highlightthickness=1 if T.is_hc() else 0, highlightbackground=C["border"])
        foot.pack(fill="x")
        self.btns = []
        for i, (txt, val) in reversed(list(enumerate(buttons))):
            b = FlatButton(foot, txt, lambda v=val: self._done(v), "primary" if i == default else "secondary",
                           font=F(11, "bold"), padx=34 if len(buttons) == 1 else 22, pady=6)
            b.pack(side="right", padx=(8, 0))
            self.btns.insert(0, b)
        cancel = buttons[-1][1] if len(buttons) > 1 else buttons[0][1]
        self.bind("<Escape>", lambda e: (self._done(cancel), "break")[1])
        self.bind("<Return>", lambda e: (self._done(buttons[default][1]), "break")[1])
        self.protocol("WM_DELETE_WINDOW", lambda: self._done(cancel))
        # zentrieren über dem Hauptfenster
        self.update_idletasks()
        try:
            top = parent.winfo_toplevel()
            x = top.winfo_rootx() + (top.winfo_width() - self.winfo_reqwidth()) // 2
            y = top.winfo_rooty() + (top.winfo_height() - self.winfo_reqheight()) // 3
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except tk.TclError:
            pass
        self.deiconify()
        dark_titlebar(self)
        btn_hint = " oder ".join(t for t, _ in buttons)
        say(f"{self.SPEAK.get(kind, '')}{title}. {text}. " + (f"Eingabe, dann {btn_hint}." if entry is not None
                                                              else f"{btn_hint}."))
        try:
            self.grab_set()
        except tk.TclError:
            pass
        if self.entry is not None:
            self.entry.focus_set()
            self.entry.select_range(0, "end")
        else:
            self.btns[default].focus_set()
        self.wait_window(self)

    def _done(self, val):
        self.result = val
        if self.entry is not None:
            self.value = self.var.get()
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


# ---------------------------------------------------------------- Schaltfläche
class FlatButton(tk.Label):
    """Flache Schaltfläche: per Maus, Eingabe- oder Leertaste auslösbar, mit Fokusrahmen."""

    def _colors(self):
        return {
            "primary": (C["accent"], C["accent_text"], C["accent_d"]),
            "secondary": (C["ctrl"], C["ctrl_text"], C["ctrl_hover"]),
            "dark": (C["pane_head"], C["pane_head_text"], C["ctrl_hover"]),
            "danger": (C["red"], C["on_red"], C["red"]),
            "head": (C["head_btn"], C["head_text"], C["head_btn_hover"]),
        }[self.style]

    def __init__(self, parent, text, command, style="secondary", font=None, padx=14, pady=6,
                 tip=None, name=None):
        self.style = style
        bg, fg, hover = self._colors()
        try:
            pbg = parent.cget("bg")
        except tk.TclError:
            pbg = C["bg"]
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font or F(10),
                         padx=padx, pady=pady, cursor="hand2", takefocus=1,
                         highlightthickness=2, highlightcolor=C["focus"],
                         highlightbackground=C["border"] if T.is_hc() else pbg)
        self._bg, self._fg, self._hover = bg, fg, hover
        self.command, self.enabled = command, True
        self.name = name or text
        self.tip = tip
        self.bind("<Enter>", lambda e: self.enabled and self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg if self.enabled else C["dis_bg"]))
        self.bind("<ButtonRelease-1>", lambda e: self.invoke())
        self.bind("<Return>", lambda e: (self.invoke(), "break")[1])
        self.bind("<KP_Enter>", lambda e: (self.invoke(), "break")[1])
        self.bind("<space>", lambda e: (self.invoke(), "break")[1])
        self.bind("<FocusIn>", self._focus, add="+")
        if tip:
            Tooltip(self, tip)

    def _focus(self, _e=None):
        txt = self.name + ("" if self.enabled else ", nicht verfügbar")
        if self.tip:
            txt += ". " + self.tip
        say(txt + ". Schaltfläche")

    def invoke(self):
        if self.enabled and self.command:
            self.command()

    def set_text(self, text, name=None):
        self.config(text=text)
        self.name = name or text

    def set_style(self, style):
        self.style = style
        self._bg, self._fg, self._hover = self._colors()
        self.config(bg=self._bg if self.enabled else C["dis_bg"], fg=self._fg if self.enabled else C["dis_text"])

    def set_enabled(self, on: bool):
        self.enabled = on
        self.config(bg=self._bg if on else C["dis_bg"], fg=self._fg if on else C["dis_text"],
                    cursor="hand2" if on else "arrow")


class Segmented(tk.Frame):
    """Umschalter (z. B. Modus). Tab springt hinein, Pfeiltasten wählen."""

    def __init__(self, parent, options, value, command, name=""):
        super().__init__(parent, bg=C["ctrl"], padx=2, pady=2,
                         highlightthickness=1 if T.is_hc() else 0, highlightbackground=C["border"])
        self.btns, self.value, self.command, self.name = {}, value, command, name
        self.options = options
        for i, (val, text) in enumerate(options):
            b = tk.Label(self, text=text, font=F(10), padx=12, pady=4, cursor="hand2", takefocus=1,
                         highlightthickness=2, highlightcolor=C["focus"], highlightbackground=C["ctrl"])
            b.pack(side="left", padx=1)
            b.bind("<ButtonRelease-1>", lambda e, v=val: self.set(v, True))
            b.bind("<Return>", lambda e, v=val: self.set(v, True))
            b.bind("<space>", lambda e, v=val: self.set(v, True))
            b.bind("<Left>", lambda e: self._step(-1))
            b.bind("<Right>", lambda e: self._step(1))
            b.bind("<FocusIn>", lambda e, v=val, t=text, n=i: say(
                f"{self.name}: {t}{', ausgewählt' if v == self.value else ''}. {n + 1} von {len(options)}. "
                "Pfeiltasten zum Wechseln"), add="+")
            self.btns[val] = b
        self.set(value)

    def _step(self, d):
        vals = [v for v, _ in self.options]
        i = (vals.index(self.value) + d) % len(vals)
        self.set(vals[i], True)
        self.btns[vals[i]].focus_set()

    def set(self, val, fire=False):
        self.value = val
        for v, b in self.btns.items():
            on = v == val
            b.config(bg=C["accent"] if on else C["ctrl"], fg=C["accent_text"] if on else C["ctrl_text"],
                     font=F(10, "bold" if on else "normal"))
        if fire:
            text = dict(self.options)[val]
            say(f"{self.name}: {text} ausgewählt")
            if self.command:
                self.command(val)


class Tooltip:
    def __init__(self, widget, text):
        self.w, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, _e=None):
        if self.tip:
            return
        x = self.w.winfo_rootx() + 10
        y = self.w.winfo_rooty() + self.w.winfo_height() + 4
        self.tip = tk.Toplevel(self.w)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg=C["head"], fg=C["head_text"], font=F(9),
                 padx=8, pady=4, justify="left", wraplength=380,
                 highlightthickness=1, highlightbackground=C["border"]).pack()

    def hide(self, _e=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


def make_icon(kind):
    img = tk.PhotoImage(width=16, height=16)
    if kind == "dir":
        img.put(C["accent_d"], to=(1, 3, 7, 5))
        img.put(C["accent"], to=(1, 5, 15, 14))
    elif kind == "file":
        img.put(C["muted"], to=(3, 1, 13, 15))
        img.put(C["field"], to=(4, 2, 12, 14))
        for y in (5, 8, 11):
            img.put(C["muted"], to=(5, y, 11, y + 1))
    elif kind == "up":
        img.put(C["muted"], to=(7, 4, 9, 14))
        for i in range(5):
            img.put(C["muted"], to=(7 - i, 4 + i, 9 + i, 5 + i))
    return img


class Dialog(tk.Toplevel):
    """Grundfenster für Dialoge: Escape schließt, Titel wird vorgelesen."""

    def __init__(self, app, title, intro=""):
        super().__init__(app.root)
        self.app = app
        self.title(f"{title} – {APP_NAME}")
        self.configure(bg=C["panel"], padx=18, pady=14)
        self.transient(app.root)
        self.bind("<Escape>", lambda e: (self.close(), "break")[1])
        self.protocol("WM_DELETE_WINDOW", self.close)
        try:
            self.iconbitmap(app.icon_path)
        except tk.TclError:
            pass
        dark_titlebar(self)
        say(f"Fenster {title}. {intro} Escape schließt.")

    def label(self, parent, text, bold=False, muted=False, wrap=0, size=10):
        return tk.Label(parent, text=text, bg=C["panel"], fg=C["muted"] if muted else C["text"],
                        font=F(size, "bold" if bold else "normal"), justify="left", anchor="w",
                        wraplength=wrap)

    def close(self):
        say("Fenster geschlossen")
        self.destroy()
        try:
            self.app.root.focus_force()
        except tk.TclError:
            pass


def open_path(p):
    try:
        if IS_WIN:
            os.startfile(p)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", p])
        else:
            subprocess.Popen(["xdg-open", p])
    except OSError as e:
        error(APP_NAME, f"Kann nicht geöffnet werden:\n{e}")


def reveal(p):
    if IS_WIN and os.path.exists(p):
        subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
    else:
        open_path(os.path.dirname(p) if os.path.isfile(p) else p)


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", name)


KEYS = [
    ("F1", "Hilfe mit allen Tasten"),
    ("F2", "Sprachausgabe ein/aus"),
    ("F3", "Hoher Kontrast ein/aus"),
    ("F4", "Dunkel / Hell umschalten"),
    ("F5", "Analysieren"),
    ("F9", "Synchronisieren"),
    ("Esc", "Vorgang abbrechen / Fenster schließen"),
    ("Strg+1 / Strg+2", "Linke / rechte Seite"),
    ("Strg+3 / Strg+4", "Aktionsliste / Protokoll"),
    ("Strg+L / Strg+D", "Pfadfeld / Laufwerk der aktiven Seite"),
    ("Strg+O", "Ordner für aktive Seite wählen"),
    ("Alt+1 / 2 / 3", "Modus Backup / Spiegeln / Zwei-Wege"),
    ("Alt+R", "Richtung umschalten"),
    ("Strg+S", "Profil speichern"),
    ("Strg+P", "Profilauswahl"),
    ("Strg+R", "Archiv: Wiederherstellen"),
    ("Strg+J", "Sammelaufträge"),
    ("Strg+I", "Status vorlesen"),
    ("Strg+W", "Letzte Ansage wiederholen"),
    ("Strg++ / Strg+- / Strg+0", "Schrift größer / kleiner / normal"),
    ("Pfeile, Enter, Rücktaste", "In Listen bewegen, Ordner öffnen, Ebene höher"),
    ("Tab / Umschalt+Tab", "Zum nächsten / vorigen Bedienelement"),
]
