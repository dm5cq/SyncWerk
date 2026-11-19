"""Hauptfenster von SyncWerk 2.0.

Darstellung: Dunkel (Standard), Hell, Hoher Kontrast · Sprachausgabe · volle Tastaturbedienung.
"""
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog

from . import APP_AUTHOR, APP_DATE_LONG, APP_IMPL, APP_NAME, APP_VERSION, COPYRIGHT
from . import auto
from . import drives
from . import engine as E
from . import jobs
from . import notify
from . import speech
from . import storage
from . import theme as T
from .theme import C, F
from .widgets import (FlatButton, MenuBar, MessageDialog, Segmented, Tooltip, acc, ask, ask_string,
                      dark_menu, dark_titlebar, error, info, make_icon, open_path, resource, reveal, say,
                      set_speaker, warn)

IS_WIN = sys.platform.startswith("win")

MODE_TEXT = {
    "backup": "Backup: Neue und geänderte Dateien werden von der Quelle ins Ziel kopiert. "
              "Im Ziel wird nie etwas gelöscht.",
    "mirror": "Spiegeln: Das Ziel wird ein exaktes Abbild der Quelle. Dateien, die in der Quelle "
              "fehlen, werden im Ziel gelöscht (bzw. ins Archiv verschoben). Umbenennungen werden erkannt.",
    "twoway": "Zwei-Wege: Neue, geänderte, gelöschte und umbenannte Dateien beider Seiten werden "
              "abgeglichen. Beim ersten Lauf wird nur zusammengeführt, nichts gelöscht.",
}
MODE_NAME = {"backup": "Backup", "mirror": "Spiegeln", "twoway": "Zwei-Wege"}
CONFLICT_TXT = {"newer": "Neuere Version gewinnt", "skip": "Konflikt überspringen"}
USB_KEYS = ("usb_serial", "usb_label", "usb_side", "usb_rel", "usb_auto")


# ====================================================================== Explorer-Seite
class Pane(tk.Frame):
    def __init__(self, app, parent, side):
        super().__init__(parent, bg=C["panel"], highlightthickness=1,
                         highlightbackground=C["border"])
        self.app, self.side = app, side
        self.title = "Linke Seite" if side == "L" else "Rechte Seite"
        self.root_path = tk.StringVar()
        self.cur = ""
        self.drive_map = {}

        self.head = tk.Label(self, text="", bg=C["pane_head"], fg=C["pane_head_text"], font=F(11, "bold"),
                             anchor="w", padx=10, pady=6)
        self.head.pack(fill="x")

        row = tk.Frame(self, bg=C["panel"], padx=8, pady=6)
        row.pack(fill="x")
        self.drive = ttk.Combobox(row, state="readonly", width=26, font=F(10))
        self.drive.pack(side="left")
        self.drive.bind("<<ComboboxSelected>>", self._drive_selected)
        acc(self.drive, f"{self.title}: Laufwerk wählen", lambda: self.drive.get())
        self.entry = ttk.Entry(row, textvariable=self.root_path, font=F(10))
        self.entry.pack(side="left", fill="x", expand=True, padx=6)
        self.entry.bind("<Return>", lambda e: self.app.root_changed(self))
        self.entry.bind("<FocusOut>", lambda e: self.app.root_changed(self, quiet=True))
        acc(self.entry, f"{self.title}: Ordnerpfad, eingeben und Eingabetaste",
            lambda: self.root_path.get() or "leer")
        self.browse_btn = FlatButton(row, "Ordner …", self.browse, padx=10, pady=3,
                                     name=f"{self.title}: Ordner wählen",
                                     tip="Netzwerkpfade wie \\\\server\\freigabe können auch direkt "
                                         "eingetippt werden.")
        self.browse_btn.pack(side="left")

        nav = tk.Frame(self, bg=C["panel"], padx=8)
        nav.pack(fill="x")
        FlatButton(nav, "↑ Ebene höher", lambda: self.app.go_up(self), padx=8, pady=2,
                   font=F(9), name=f"{self.title}: eine Ebene höher").pack(side="left")
        self.crumb = tk.Label(nav, text="", bg=C["panel"], fg=C["muted"], font=F(9), anchor="w")
        self.crumb.pack(side="left", fill="x", expand=True, padx=8)

        box = tk.Frame(self, bg=C["panel"])
        box.pack(fill="both", expand=True, padx=8, pady=(6, 0))
        self.tree = ttk.Treeview(box, columns=("size", "mtime", "status"), selectmode="browse")
        self.tree.heading("#0", text="Name", anchor="w")
        self.tree.heading("size", text="Größe", anchor="e")
        self.tree.heading("mtime", text="Geändert", anchor="w")
        self.tree.heading("status", text="Status / Aktion", anchor="w")
        sc = T.scale()
        self.tree.column("#0", width=int(250 * sc), minwidth=140, stretch=True)
        self.tree.column("size", width=int(80 * sc), minwidth=60, anchor="e", stretch=False)
        self.tree.column("mtime", width=int(122 * sc), minwidth=90, stretch=False)
        self.tree.column("status", width=int(160 * sc), minwidth=90, stretch=False)
        self.vsb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=lambda f, l: self.app.on_scroll(self, f, l))
        self.tree.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        for col, tint in T.TINT.items():
            self.tree.tag_configure(col, background=C[tint], foreground=C["text"])
        self.tree.tag_configure("ghost", foreground=C["ghost"], background=C["field"])
        self.tree.tag_configure("up", foreground=C["muted"])
        self.tree.bind("<Double-1>", self._open)
        self.tree.bind("<Return>", self._open)
        self.tree.bind("<BackSpace>", lambda e: self.app.go_up(self))
        self.tree.bind("<<TreeviewSelect>>", self._selected)
        self.tree.bind("<Button-3>", self._context)
        self.tree.bind("<Shift-F10>", self._context_key)
        if IS_WIN:
            self.tree.bind("<App>", self._context_key)
        self.tree.bind("<FocusIn>", self._tree_focus, add="+")

        self.foot = tk.Label(self, text="", bg=C["panel"], fg=C["muted"], font=F(9),
                             anchor="w", padx=8, pady=4)
        self.foot.pack(fill="x")
        for w in (self, row, nav, box, self.crumb, self.foot):
            w.bind("<Button-1>", lambda e: self.app.set_active(self), add="+")

    # --- Laufwerke
    def fill_drives(self, items):
        self.drive_map = {drives.display(k, t): p for k, t, p in items}
        self.drive["values"] = list(self.drive_map)
        self.drive.set("Laufwerk wählen …")

    def _drive_selected(self, _e=None):
        p = self.drive_map.get(self.drive.get())
        if p:
            self.root_path.set(p)
            say(f"{self.drive.get()} gewählt")
            self.app.root_changed(self)

    def browse(self):
        self.app.set_active(self)
        start = self.root_path.get() if os.path.isdir(self.root_path.get()) else os.path.expanduser("~")
        say(f"Ordner für die {self.title} wählen")
        p = filedialog.askdirectory(initialdir=start, title=f"Ordner wählen – {self.title}", mustexist=True)
        if p:
            self.root_path.set(os.path.normpath(p))
            say(f"{self.title}: {p}")
            self.app.root_changed(self)

    def path(self):
        return self.root_path.get().strip().strip('"')

    # --- Anzeige
    def refresh(self):
        t = self.tree
        t.delete(*t.get_children())
        root = self.path()
        an = self.app.view_analysis()
        icons = self.app.icons
        if an and self.cur and self.cur not in an.L and self.cur not in an.R:
            self.cur = ""
        if self.cur:
            t.insert("", "end", iid="..", text="  ..", image=icons["up"], tags=("up",))
        sep = "\\" if IS_WIN else "/"
        self.crumb.config(text=sep + self.cur.replace("/", sep))
        if an:
            mine = an.L if self.side == "L" else an.R
            other = an.R if self.side == "L" else an.L
            for _, _, name, rel in self.app.index.get(self.cur, []):
                e = mine.get(rel)
                is_dir = (e or other[rel]).is_dir
                ic = icons["dir" if is_dir else "file"]
                if e:
                    col, lab = an.status.get(rel, (E.GREEN, "="))
                    lab = {"=": "✔ identisch", "≠": "≠ verschieden"}.get(lab, lab)
                    t.insert("", "end", iid=rel, text="  " + name, image=ic, tags=(col,),
                             values=("" if is_dir else E.fmt_size(e.size),
                                     "" if is_dir else E.fmt_time(e.mtime), lab))
                else:
                    t.insert("", "end", iid=rel, text="  " + name, image=ic, tags=("ghost",),
                             values=("", "", "— fehlt —"))
            n, size = self.app.totals.get(self.side, (0, 0))
            self.foot.config(text=f"{n:,} Dateien · {E.fmt_size(size)} (gesamt, ohne Ausschlüsse)"
                             .replace(",", "."))
        elif root and os.path.isdir(E.lp(root)):
            path = E.join(root, self.cur)
            try:
                with os.scandir(E.lp(path)) as it:
                    items = []
                    for e in it:
                        try:
                            d = e.is_dir()
                            st = None if d else e.stat()
                        except OSError:
                            continue
                        items.append((not d, e.name.lower(), e.name, d, st))
                items.sort()
                for _, _, name, d, st in items[:20000]:
                    rel = f"{self.cur}/{name}" if self.cur else name
                    t.insert("", "end", iid=rel, text="  " + name, image=icons["dir" if d else "file"],
                             values=("" if d else E.fmt_size(st.st_size), "" if d else E.fmt_time(st.st_mtime), ""))
                self.foot.config(text=f"{len(items):,} Einträge in diesem Ordner – noch nicht analysiert"
                                 .replace(",", "."))
            except OSError as ex:
                self.foot.config(text=f"Nicht lesbar: {ex.strerror or ex}")
        else:
            self.foot.config(text="Kein Ordner gewählt" if not root else "Ordner nicht erreichbar")

    def row_text(self, iid):
        if iid == "..":
            return "Punkt Punkt, eine Ebene höher"
        if not self.tree.exists(iid):
            return ""
        v = self.tree.item(iid)
        name = v["text"].strip()
        size, mtime, status = (list(v["values"]) + ["", "", ""])[:3]
        if "ghost" in v["tags"]:
            return f"{name}, fehlt auf dieser Seite"
        kind = "Ordner" if self.app.is_dir_rel(iid) or not size else "Datei"
        parts = [name, kind]
        if size:
            parts.append(str(size))
        if mtime:
            parts.append(f"geändert {mtime}")
        if status:
            parts.append(f"Status {status}")
        return ", ".join(parts)

    def _tree_focus(self, _e=None):
        self.app.set_active(self)
        if not self.tree.focus():
            kids = self.tree.get_children()
            if kids:
                self.tree.focus(kids[0])
                self.tree.selection_set(kids[0])
        n = len(self.tree.get_children())
        where = self.crumb.cget("text")
        say(f"{self.title}, Liste, {n} Einträge, Ordner {where or 'oberste Ebene'}. "
            f"{self.row_text(self.tree.focus())}")

    def _selected(self, _e=None):
        self.app.on_select(self)
        if self.app.root.focus_get() is self.tree:
            say(self.row_text(self.tree.focus()))

    def _open(self, _e=None):
        sel = self.tree.focus()
        if not sel:
            return
        if sel == "..":
            self.app.go_up(self)
            return
        full = E.join(self.path(), sel)
        if self.app.is_dir_rel(sel) or os.path.isdir(E.lp(full)):
            self.app.navigate(self, sel)
        elif os.path.isfile(E.lp(full)):
            say("Datei wird geöffnet")
            open_path(full)

    def _context_key(self, _e=None):
        iid = self.tree.focus()
        if iid:
            bbox = self.tree.bbox(iid)
            x = self.tree.winfo_rootx() + 40
            y = self.tree.winfo_rooty() + (bbox[1] + bbox[3] if bbox else 20)
            self._menu(iid, x, y)

    def _context(self, e):
        iid = self.tree.identify_row(e.y)
        if iid:
            self._menu(iid, e.x_root, e.y_root)

    def _menu(self, iid, x, y):
        if iid == "..":
            return
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        full = E.join(self.path(), iid)
        m = dark_menu(self)
        m.add_command(label="Öffnen", command=self._open)
        m.add_command(label="Im Explorer anzeigen", command=lambda: reveal(full))
        m.add_command(label="Pfad kopieren", command=lambda: (self.clipboard_clear(), self.clipboard_append(full),
                                                               say("Pfad kopiert")))
        say("Kontextmenü")
        m.tk_popup(x, y)


# ====================================================================== Hauptfenster
class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.q = queue.Queue()
        self.an = None
        self.an_key = None
        self.index = {}
        self.totals = {}
        self.busy = False
        self.cancel = threading.Event()
        self._scrolling = self._selecting = False
        self._last_q = 0.0
        self._prog_n = (0, 0)
        self._after_idle_action = None
        self._executing = False
        self._spoken_pct = -1
        self.log_lines = []
        self.usb = {}
        self.active = None
        self.profiles = storage.load_profiles()
        self.settings = storage.load_settings()
        self.icon_path = resource("SyncWerk.ico")

        T.apply(self.settings.get("theme", "dunkel"), self.settings.get("scale", 1.0))
        self.speaker = speech.Speaker(self.settings.get("speech", False), self.settings.get("rate", 1))
        set_speaker(self.speaker)

        root.title(f"{APP_NAME} {APP_VERSION} – Synchronisation & Backup")
        root.minsize(1100, 720)
        root.geometry(self.settings.get("geometry", "1440x900"))
        try:
            root.iconbitmap(self.icon_path)
        except tk.TclError:
            pass
        self._build_all()
        self._load_initial()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._bind_keys()
        root.after(80, self._poll)
        if self.speaker.enabled:
            self.speaker.warmup()
            root.after(600, lambda: say(f"{APP_NAME} {APP_VERSION} gestartet. Sprachausgabe ist an. "
                                        "F1 für Hilfe, F2 schaltet die Sprachausgabe aus."))

    # ------------------------------------------------------------ Stil & Aufbau
    def _styles(self):
        st = ttk.Style()
        st.theme_use("clam")
        st.configure(".", font=F(10), background=C["panel"], foreground=C["text"],
                     fieldbackground=C["field"], bordercolor=C["field_border"],
                     lightcolor=C["panel"], darkcolor=C["panel"], troughcolor=C["trough"],
                     focuscolor=C["focus"], selectbackground=C["sel_bg"], selectforeground=C["sel_text"],
                     insertcolor=C["text"])
        st.configure("Treeview", background=C["field"], fieldbackground=C["field"], foreground=C["text"],
                     rowheight=int(25 * T.scale()) + (4 if T.is_hc() else 0), borderwidth=2,
                     bordercolor=C["border"], font=F(10))
        st.configure("Treeview.Heading", background=C["ctrl"], foreground=C["ctrl_text"],
                     font=F(9, "bold"), relief="flat", padding=(6, 4), bordercolor=C["border"])
        st.map("Treeview", background=[("selected", C["sel_bg"])], foreground=[("selected", C["sel_text"])],
               bordercolor=[("focus", C["focus"])])
        st.map("Treeview.Heading", background=[("active", C["ctrl_hover"])])
        st.configure("O.Horizontal.TProgressbar", troughcolor=C["trough"], background=C["accent"],
                     bordercolor=C["border"], lightcolor=C["accent"], darkcolor=C["accent_d"],
                     thickness=int(14 * T.scale()))
        st.configure("TNotebook", background=C["bg"], borderwidth=0, tabmargins=(0, 4, 0, 0))
        st.configure("TNotebook.Tab", padding=(16, 6), background=C["ctrl"], foreground=C["ctrl_text"],
                     font=F(10), bordercolor=C["border"])
        st.map("TNotebook.Tab", background=[("selected", C["accent"])],
               foreground=[("selected", C["accent_text"])])
        for w in ("TCheckbutton", "TRadiobutton"):
            st.configure(w, background=C["panel"], foreground=C["text"], font=F(10),
                         indicatorbackground=C["field"], indicatorforeground=C["accent"])
            st.map(w, background=[("active", C["panel"])], foreground=[("active", C["text"])],
                   indicatorcolor=[("selected", C["accent"]), ("!selected", C["field"])])
        st.configure("TEntry", padding=4, fieldbackground=C["field"], foreground=C["text"],
                     bordercolor=C["field_border"], insertcolor=C["text"])
        st.map("TEntry", bordercolor=[("focus", C["focus"])])
        for w in ("TCombobox", "TSpinbox"):
            st.configure(w, padding=3, fieldbackground=C["field"], foreground=C["text"],
                         background=C["ctrl"], bordercolor=C["field_border"], arrowcolor=C["accent"],
                         insertcolor=C["text"])
            st.map(w, fieldbackground=[("readonly", C["field"]), ("disabled", C["dis_bg"])],
                   foreground=[("disabled", C["dis_text"])], bordercolor=[("focus", C["focus"])],
                   selectbackground=[("readonly", C["field"])], selectforeground=[("readonly", C["text"])])
        st.configure("Vertical.TScrollbar", background=C["ctrl"], troughcolor=C["field"],
                     bordercolor=C["border"], arrowcolor=C["muted"])
        self.root.option_add("*TCombobox*Listbox.background", C["field"])
        self.root.option_add("*TCombobox*Listbox.foreground", C["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", C["sel_bg"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", C["sel_text"])
        self.root.option_add("*TCombobox*Listbox.font", F(10))
        self.root.configure(bg=C["bg"])

    def dark_titlebar(self, win):
        dark_titlebar(win)

    def _build_all(self):
        self.icons = {k: make_icon(k) for k in ("dir", "file", "up")}
        self._styles()
        self._build_menu()
        self._build()
        self.dark_titlebar(self.root)

    def _build_menu(self):
        self.root.config(menu="")
        mb = self.menubar = MenuBar(self.root)
        mb.pack(fill="x")

        def menu(label, underline=0):
            return mb.add(label, underline)
        m = menu("Datei")
        m.add_command(label="Profil speichern …", accelerator="Strg+S", command=self.save_profile)
        m.add_command(label="Profil löschen", command=self.delete_profile)
        m.add_separator()
        m.add_command(label="Protokollordner öffnen", command=lambda: open_path(os.path.dirname(storage.log_path())))
        m.add_separator()
        m.add_command(label="Beenden", accelerator="Alt+F4", command=self.on_close)
        m = menu("Synchronisation")
        m.add_command(label="Analysieren", accelerator="F5", command=self.analyze)
        m.add_command(label="Synchronisieren", accelerator="F9", command=self.sync)
        m.add_command(label="Abbrechen", accelerator="Esc", command=self.do_cancel)
        m.add_separator()
        for i, k in enumerate(("backup", "mirror", "twoway"), 1):
            m.add_command(label=f"Modus {MODE_NAME[k]}", accelerator=f"Alt+{i}",
                          command=lambda k=k: self.set_mode(k))
        m.add_command(label="Richtung umschalten", accelerator="Alt+R", command=self.toggle_direction)
        m.add_command(label="Seiten tauschen", command=self.swap_sides)
        m = menu("Archiv")
        m.add_command(label="Versionen wiederherstellen …", accelerator="Strg+R", command=self.open_restore)
        m.add_command(label="Archiv jetzt aufräumen", command=self.cleanup_now)
        m = menu("Automatik", 1)
        m.add_command(label="Zeitplan und USB-Auslöser …", command=self.open_automation)
        m.add_command(label="Sammelaufträge …", accelerator="Strg+J", command=self.open_batch)
        m = menu("Ansicht", 1)
        self.theme_var = tk.StringVar(value=T.name())
        for k, n in T.NAMES.items():
            m.add_radiobutton(label=n, variable=self.theme_var, value=k, command=lambda k=k: self.set_theme(k))
        m.add_separator()
        m.add_command(label="Schrift größer", accelerator="Strg++", command=lambda: self.set_scale(+0.1))
        m.add_command(label="Schrift kleiner", accelerator="Strg+-", command=lambda: self.set_scale(-0.1))
        m.add_command(label="Schrift normal", accelerator="Strg+0", command=lambda: self.set_scale(0))
        m = menu("Barrierefreiheit")
        self.speech_var = tk.BooleanVar(value=self.speaker.enabled)
        m.add_checkbutton(label="Sprachausgabe", accelerator="F2", variable=self.speech_var,
                          command=lambda: self.toggle_speech(self.speech_var.get()))
        m.add_command(label="Status vorlesen", accelerator="Strg+I", command=self.read_status)
        m.add_command(label="Letzte Ansage wiederholen", accelerator="Strg+W", command=self.speaker.repeat)
        m.add_command(label="Sprechtempo schneller", command=lambda: self.set_rate(+1))
        m.add_command(label="Sprechtempo langsamer", command=lambda: self.set_rate(-1))
        m.add_separator()
        m.add_command(label="Hoher Kontrast ein/aus", accelerator="F3", command=self.toggle_hc)
        m = menu("Hilfe")
        m.add_command(label="Hilfe und Tastenkürzel", accelerator="F1", command=self.show_help)
        m.add_command(label="Kurzanleitung (PDF)", command=lambda: open_path(resource("SyncWerk-Kurzanleitung.pdf")))
        m.add_command(label="Über SyncWerk …", command=self.show_info)

    def _build(self):
        r = self.root
        # --- Kopfzeile
        head = tk.Frame(r, bg=C["head"])
        head.pack(fill="x")
        logo = tk.Canvas(head, width=44, height=44, bg=C["head"], highlightthickness=0)
        logo.pack(side="left", padx=(16, 10), pady=10)
        logo.create_oval(2, 2, 42, 42, fill=C["accent"], outline="")
        logo.create_text(22, 22, text="⇄", fill=C["accent_text"], font=(T.FAMILY, 20, "bold"))
        tt = tk.Frame(head, bg=C["head"])
        tt.pack(side="left")
        tk.Label(tt, text=APP_NAME, bg=C["head"], fg="#ffffff" if not T.is_hc() else C["head_text"],
                 font=F(18, "bold")).pack(anchor="w")
        tk.Label(tt, text="Synchronisation & Backup – lokal · USB · Netzwerk · Cloud",
                 bg=C["head"], fg=C["head_text"], font=F(9)).pack(anchor="w")
        hb = dict(style="head", padx=10, pady=4, font=F(9))
        FlatButton(head, "Info", self.show_info, **hb).pack(side="right", padx=(2, 14))
        FlatButton(head, "Hilfe (F1)", self.show_help, name="Hilfe", **hb).pack(side="right", padx=2)
        FlatButton(head, "A+", lambda: self.set_scale(+0.1), name="Schrift größer", **hb).pack(side="right", padx=2)
        FlatButton(head, "A−", lambda: self.set_scale(-0.1), name="Schrift kleiner", **hb).pack(side="right", padx=2)
        self.theme_btn = FlatButton(head, f"Ansicht: {T.NAMES[T.name()]}", self.cycle_theme,
                                    name="Ansicht wechseln", tip="Dunkel → Hell → Hoher Kontrast (F3/F4)", **hb)
        self.theme_btn.pack(side="right", padx=2)
        self.speech_btn = FlatButton(head, "", lambda: self.toggle_speech(not self.speaker.enabled),
                                     tip="Sprachausgabe für blinde und sehbehinderte Menschen (F2)", **hb)
        self.speech_btn.pack(side="right", padx=2)
        self._speech_btn_text()
        tk.Label(head, text=f"Version {APP_VERSION}", bg=C["head"], fg=C["accent"],
                 font=F(10, "bold")).pack(side="right", padx=12)
        tk.Frame(r, bg=C["accent"], height=3).pack(fill="x")

        # --- Steuerkarte
        card = tk.Frame(r, bg=C["panel"], padx=14, pady=8, highlightthickness=1,
                        highlightbackground=C["border"])
        card.pack(fill="x", padx=12, pady=(10, 6))
        row1 = tk.Frame(card, bg=C["panel"])
        row1.pack(fill="x")
        self._lbl(row1, "Profil").pack(side="left")
        self.profile_cb = ttk.Combobox(row1, state="readonly", width=24, font=F(10))
        self.profile_cb.pack(side="left", padx=(6, 4))
        self.profile_cb.bind("<<ComboboxSelected>>", lambda e: self.load_profile(self.profile_cb.get()))
        acc(self.profile_cb, "Profil wählen", lambda: self.profile_cb.get() or "keins")
        sb = dict(padx=10, pady=3)
        FlatButton(row1, "Speichern", self.save_profile, name="Profil speichern", **sb).pack(side="left", padx=2)
        FlatButton(row1, "Löschen", self.delete_profile, name="Profil löschen", **sb).pack(side="left", padx=2)
        FlatButton(row1, "Automatik …", self.open_automation, name="Automatik: Zeitplan und USB-Auslöser",
                   tip="Zeitplan (Aufgabenplanung) und Start beim Anstecken einer USB-Platte", **sb) \
            .pack(side="left", padx=2)
        FlatButton(row1, "Sammelaufträge …", self.open_batch, name="Sammelaufträge",
                   tip="Mehrere Profile nacheinander, z. B. Feierabend-Backup (Strg+J)", **sb) \
            .pack(side="left", padx=2)
        FlatButton(row1, "Wiederherstellen …", self.open_restore, name="Archiv: Versionen wiederherstellen",
                   tip="Gelöschte oder überschriebene Dateien aus dem Archiv zurückholen (Strg+R)", **sb) \
            .pack(side="left", padx=2)

        row1b = tk.Frame(card, bg=C["panel"], pady=6)
        row1b.pack(fill="x")
        self._lbl(row1b, "Modus").pack(side="left")
        self.mode_seg = Segmented(row1b, [("backup", "Backup"), ("mirror", "Spiegeln"),
                                          ("twoway", "⇄ Zwei-Wege")], "backup", self.on_mode, name="Modus")
        self.mode_seg.pack(side="left", padx=6)
        self.direction = "LR"
        self.dir_btn = FlatButton(row1b, "", self.toggle_direction, "dark", padx=12, pady=4,
                                  font=F(10, "bold"), tip="Richtung umschalten (Alt+R)")
        self.dir_btn.pack(side="left", padx=6)
        tk.Frame(row1b, bg=C["border"], width=2, height=26).pack(side="left", padx=14)
        self._lbl(row1b, "Vergleich").pack(side="left")
        self.cmp_seg = Segmented(row1b, [("fast", "Schnell"), ("exact", "Genau")], "fast", self.on_scan_opt,
                                 name="Vergleich")
        self.cmp_seg.pack(side="left", padx=6)
        Tooltip(self.cmp_seg, "Schnell: Größe + Änderungsdatum (empfohlen).\nGenau: zusätzlich Inhalt "
                              "per Prüfsumme – langsamer.")
        tk.Frame(row1b, bg=C["border"], width=2, height=26).pack(side="left", padx=14)
        self.moves = tk.BooleanVar(value=True)
        self._check(row1b, "Umbenennen/Verschieben erkennen", self.moves, self.on_plan_opt,
                    "Umbenannte oder verschobene Dateien und Ordner werden im Ziel nur umbenannt "
                    "statt neu kopiert – spart bei großen Fotoarchiven viel Zeit.").pack(side="left")
        self.ignore_dst = tk.BooleanVar(value=True)
        self._check(row1b, "±1 h ignorieren", self.ignore_dst, self.on_scan_opt,
                    "FAT/exFAT-Laufwerke zeigen nach der Zeitumstellung oft genau 1 Stunde Abweichung.") \
            .pack(side="left", padx=(14, 0))

        row2 = tk.Frame(card, bg=C["panel"])
        row2.pack(fill="x")
        self.archive = tk.BooleanVar(value=True)
        self._check(row2, "Archivieren statt löschen", self.archive, None,
                    f"Gelöschte/überschriebene Dateien landen im Ordner „{E.ARCHIVE_DIR}“.").pack(side="left")
        self._lbl(row2, "aufbewahren", bold=False).pack(side="left", padx=(10, 4))
        self.arch_days = tk.StringVar(value="90")
        self._spin(row2, self.arch_days, 0, 3650, "Archiv: Tage aufbewahren, 0 bedeutet unbegrenzt").pack(side="left")
        self._lbl(row2, "Tage, max.", bold=False).pack(side="left", padx=4)
        self.arch_keep = tk.StringVar(value="5")
        self._spin(row2, self.arch_keep, 0, 99, "Archiv: höchstens Versionen je Datei, 0 bedeutet unbegrenzt") \
            .pack(side="left")
        self._lbl(row2, "Versionen je Datei", bold=False).pack(side="left", padx=4)
        tk.Frame(row2, bg=C["border"], width=2, height=26).pack(side="left", padx=12)
        self._lbl(row2, "Konflikte").pack(side="left", padx=(0, 4))
        self.conflict_cb = ttk.Combobox(row2, state="readonly", width=22, values=list(CONFLICT_TXT.values()),
                                        font=F(10))
        self.conflict_cb.set(CONFLICT_TXT["newer"])
        self.conflict_cb.pack(side="left")
        self.conflict_cb.bind("<<ComboboxSelected>>", lambda e: (say(self.conflict_cb.get()), self.on_plan_opt()))
        acc(self.conflict_cb, "Konflikte bei Zwei-Wege", lambda: self.conflict_cb.get())
        self._lbl(row2, "Ausschließen").pack(side="left", padx=(12, 4))
        self.excludes = tk.StringVar(value=storage.DEFAULT_PROFILE["excludes"])
        ex = ttk.Entry(row2, textvariable=self.excludes, font=F(10))
        ex.pack(side="left", fill="x", expand=True)
        acc(ex, "Ausschließen, Muster mit Semikolon getrennt", lambda: self.excludes.get())
        Tooltip(ex, "Muster mit ; trennen, z. B.  *.tmp; Thumbs.db; node_modules; ~$*")
        self.mode_info = tk.Label(card, text="", bg=C["panel"], fg=C["muted"], font=F(9, italic=True),
                                  anchor="w", justify="left")
        self.mode_info.pack(fill="x", pady=(4, 0))

        # --- Explorer + Aktionen
        split = tk.PanedWindow(r, orient="vertical", bg=C["bg"], sashwidth=7, bd=0, sashrelief="flat")
        split.pack(fill="both", expand=True, padx=12)
        top = tk.Frame(split, bg=C["bg"])
        self.left = Pane(self, top, "L")
        mid = tk.Frame(top, bg=C["bg"])
        self.right = Pane(self, top, "R")
        self.left.grid(row=0, column=0, sticky="nsew")
        mid.grid(row=0, column=1, sticky="ns", padx=6)
        self.right.grid(row=0, column=2, sticky="nsew")
        top.columnconfigure(0, weight=1, uniform="p")
        top.columnconfigure(2, weight=1, uniform="p")
        top.rowconfigure(0, weight=1)
        tk.Frame(mid, bg=C["bg"], height=90).pack()
        FlatButton(mid, "⇄", self.swap_sides, "dark", font=F(14, "bold"), padx=10, pady=4,
                   name="Seiten tauschen", tip="Linke und rechte Seite tauschen").pack(pady=4)
        self.sync_nav = tk.BooleanVar(value=True)
        self.nav_btn = FlatButton(mid, "⛓", self.toggle_nav, "primary", font=F(13), padx=10, pady=4,
                                  name="Gekoppelt navigieren",
                                  tip="Beide Seiten zeigen denselben Unterordner und scrollen gemeinsam")
        self.nav_btn.pack(pady=4)
        FlatButton(mid, "⟳", self.reload_drives, "secondary", font=F(13), padx=10, pady=4,
                   name="Laufwerke neu einlesen",
                   tip="Laufwerksliste neu einlesen (z. B. nach Anstecken einer USB-Platte)").pack(pady=4)
        split.add(top, minsize=240, stretch="always")

        bottom = tk.Frame(split, bg=C["bg"])
        legend = tk.Frame(bottom, bg=C["bg"])
        legend.pack(fill="x", pady=(6, 2))
        for col, txt in ((E.GREEN, "✔ identisch / erledigt"), (E.BLUE, "neu – wird kopiert"),
                         (E.YELLOW, "geändert / umbenannt"), (E.RED, "✕ löschen / Konflikt / Fehler")):
            tk.Label(legend, text="●", fg=C[col], bg=C["bg"], font=F(12)).pack(side="left")
            tk.Label(legend, text=txt, fg=C["text"], bg=C["bg"], font=F(9)).pack(side="left", padx=(0, 14))
        self.nb = ttk.Notebook(bottom)
        self.nb.pack(fill="both", expand=True)
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self.root.focus_get() is self.nb and
                     say(self.nb.tab(self.nb.select(), "text").strip()))
        af = tk.Frame(self.nb, bg=C["field"])
        self.acts = ttk.Treeview(af, columns=("aktion", "pfad", "size", "grund"), show="headings")
        sc = T.scale()
        for c, t, w, a in (("aktion", "Aktion", 190, "w"), ("pfad", "Pfad", 520, "w"),
                           ("size", "Größe", 90, "e"), ("grund", "Grund", 320, "w")):
            self.acts.heading(c, text=t, anchor=a)
            self.acts.column(c, width=int(w * sc), anchor=a, stretch=c in ("pfad", "grund"))
        for col, tint in T.TINT.items():
            self.acts.tag_configure(col, background=C[tint], foreground=C["text"])
        asb = ttk.Scrollbar(af, orient="vertical", command=self.acts.yview)
        self.acts.configure(yscrollcommand=asb.set)
        self.acts.pack(side="left", fill="both", expand=True)
        asb.pack(side="right", fill="y")
        self.acts.bind("<Double-1>", self._goto_action)
        self.acts.bind("<Return>", self._goto_action)
        self.acts.bind("<Delete>", lambda e: self.acts.focus().isdigit() and self._skip_action(int(self.acts.focus())))
        self.acts.bind("<Button-3>", self._action_menu)
        self.acts.bind("<Shift-F10>", self._action_menu_key)
        if IS_WIN:
            self.acts.bind("<App>", self._action_menu_key)
        self.acts.bind("<<TreeviewSelect>>", lambda e: self.root.focus_get() is self.acts and say(self._act_text()))
        self.acts.bind("<FocusIn>", self._acts_focus, add="+")
        self.nb.add(af, text="  Geplante Aktionen  ")
        lf = tk.Frame(self.nb, bg=C["field"])
        self.logw = tk.Text(lf, bg=C["field"], fg=C["text"], font=F(9, mono=True), insertbackground=C["text"],
                            relief="flat", padx=8, pady=6, wrap="none", state="disabled",
                            highlightthickness=2, highlightcolor=C["focus"], highlightbackground=C["field"])
        lsb = ttk.Scrollbar(lf, orient="vertical", command=self.logw.yview)
        self.logw.configure(yscrollcommand=lsb.set)
        self.logw.pack(side="left", fill="both", expand=True)
        lsb.pack(side="right", fill="y")
        for col in (E.GREEN, E.BLUE, E.YELLOW, E.RED):
            self.logw.tag_configure(col, foreground=C[col])
        self.logw.tag_configure("time", foreground=C["ghost"])
        acc(self.logw, "Protokoll", lambda: f"{len(self.log_lines)} Meldungen. Letzte: "
                                            f"{self.log_lines[-1][1] if self.log_lines else 'keine'}")
        self.nb.add(lf, text="  Protokoll  ")
        split.add(bottom, minsize=140, height=int(230 * T.scale()))

        # --- Fußleiste
        bar = tk.Frame(r, bg=C["panel"], padx=14, pady=10, highlightthickness=1,
                       highlightbackground=C["border"])
        bar.pack(fill="x", padx=12, pady=(6, 4))
        left = tk.Frame(bar, bg=C["panel"])
        left.pack(side="left", fill="x", expand=True)
        self.chips = tk.Frame(left, bg=C["panel"])
        self.chips.pack(fill="x")
        self.prog = ttk.Progressbar(left, style="O.Horizontal.TProgressbar", maximum=1000)
        self.prog.pack(fill="x", pady=(6, 2))
        self.status = tk.Label(left, text="Bereit. Wähle links und rechts einen Ordner und drücke F5 "
                                          "zum Analysieren.", bg=C["panel"], fg=C["muted"], font=F(9),
                               anchor="w")
        self.status.pack(fill="x")
        btns = tk.Frame(bar, bg=C["panel"])
        btns.pack(side="right", padx=(16, 0))
        self.btn_analyze = FlatButton(btns, "Analysieren  (F5)", self.analyze, "dark", font=F(11, "bold"),
                                      padx=18, pady=10, name="Analysieren, Taste F5",
                                      tip="Vergleicht beide Seiten, verändert nichts")
        self.btn_sync = FlatButton(btns, "▶  Synchronisieren  (F9)", self.sync, "primary",
                                   font=F(12, "bold"), padx=22, pady=10, name="Synchronisieren, Taste F9")
        self.btn_cancel = FlatButton(btns, "■  Abbrechen", self.do_cancel, "danger", font=F(11, "bold"),
                                     padx=16, pady=10, name="Abbrechen, Taste Escape")
        self.btn_analyze.pack(side="left", padx=4)
        self.btn_sync.pack(side="left", padx=4)
        self.btn_cancel.pack(side="left", padx=4)
        self.btn_cancel.set_enabled(False)
        tk.Label(r, text=COPYRIGHT, bg=C["bg"], fg=C["ghost"], font=F(8)).pack(pady=(0, 4))
        self._set_chips(None)

    def _lbl(self, parent, text, bold=True):
        return tk.Label(parent, text=text, bg=C["panel"], fg=C["text"], font=F(10, "bold" if bold else "normal"))

    def _check(self, parent, text, var, command, tip=None):
        def changed():
            say(f"{text}: {'an' if var.get() else 'aus'}")
            if command:
                command()
        cb = ttk.Checkbutton(parent, text=text, variable=var, command=changed)
        acc(cb, f"{text}, Kontrollkästchen", lambda: "an" if var.get() else "aus")
        if tip:
            Tooltip(cb, tip)
        return cb

    def _spin(self, parent, var, lo, hi, name):
        sp = ttk.Spinbox(parent, from_=lo, to=hi, textvariable=var, width=5, font=F(10),
                         command=lambda: say(var.get()))
        acc(sp, name, lambda: var.get())
        return sp

    # ------------------------------------------------------------ Tastatur
    def _bind_keys(self):
        r = self.root
        keys = {
            "<F1>": lambda e: self.show_help(), "<F2>": lambda e: self.toggle_speech(not self.speaker.enabled),
            "<F3>": lambda e: self.toggle_hc(), "<F4>": lambda e: self.toggle_dark_light(),
            "<F5>": lambda e: self.analyze(), "<F9>": lambda e: self.sync(),
            "<Escape>": lambda e: self.do_cancel(),
            "<Control-Key-1>": lambda e: self.focus_pane(self.left),
            "<Control-Key-2>": lambda e: self.focus_pane(self.right),
            "<Control-Key-3>": lambda e: (self.nb.select(0), self.acts.focus_set()),
            "<Control-Key-4>": lambda e: (self.nb.select(1), self.logw.focus_set()),
            "<Control-l>": lambda e: self.active_pane().entry.focus_set(),
            "<Control-d>": lambda e: self.active_pane().drive.focus_set(),
            "<Control-o>": lambda e: self.active_pane().browse(),
            "<Alt-Key-1>": lambda e: self.set_mode("backup"), "<Alt-Key-2>": lambda e: self.set_mode("mirror"),
            "<Alt-Key-3>": lambda e: self.set_mode("twoway"), "<Alt-r>": lambda e: self.toggle_direction(),
            "<Control-s>": lambda e: self.save_profile(), "<Control-p>": lambda e: self.profile_cb.focus_set(),
            "<Control-r>": lambda e: self.open_restore(), "<Control-j>": lambda e: self.open_batch(),
            "<Control-i>": lambda e: self.read_status(), "<Control-w>": lambda e: self.speaker.repeat(),
            "<Control-plus>": lambda e: self.set_scale(+0.1), "<Control-KP_Add>": lambda e: self.set_scale(+0.1),
            "<Control-minus>": lambda e: self.set_scale(-0.1),
            "<Control-KP_Subtract>": lambda e: self.set_scale(-0.1),
            "<Control-Key-0>": lambda e: self.set_scale(0),
        }
        for k, fn in keys.items():
            r.bind_all(k, lambda e, fn=fn: (fn(e), "break")[1])
        self._bind_menu_keys()

    def _bind_menu_keys(self):
        """Alt+Buchstabe öffnet das Menü, F10 springt in die Menüleiste."""
        r = self.root
        for i in range(len(self.menubar.items)):
            ch = self.menubar.key(i)
            for k in (f"<Alt-{ch}>", f"<Alt-{ch.upper()}>"):
                r.bind_all(k, lambda e, i=i: (self.menubar.open(i), "break")[1])
        r.bind_all("<F10>", lambda e: (self.menubar.items[0][0].focus_set(), "break")[1])

    def active_pane(self):
        return self.active or self.left

    def set_active(self, pane):
        self.active = pane

    def focus_pane(self, pane):
        self.set_active(pane)
        pane.tree.focus_set()

    # ------------------------------------------------------------ Darstellung / Barrierefreiheit
    def _speech_btn_text(self):
        on = self.speaker.enabled
        self.speech_btn.set_text(f"Sprachausgabe: {'AN' if on else 'AUS'} (F2)",
                                 name=f"Sprachausgabe ist {'an' if on else 'aus'}")
        self.speech_btn.set_style("primary" if on else "head")

    def toggle_speech(self, on):
        self.speaker.enabled = bool(on)
        self.settings["speech"] = self.speaker.enabled
        if hasattr(self, "speech_var"):
            self.speech_var.set(self.speaker.enabled)
        self._speech_btn_text()
        if on:
            self.speaker.warmup()
            say("Sprachausgabe eingeschaltet. F1 Hilfe, Strg I Status vorlesen, Strg W wiederholen, "
                "Tab wechselt zwischen den Bedienelementen.")
        else:
            self.speaker.say("Sprachausgabe ausgeschaltet", force=True)

    def set_rate(self, d):
        self.speaker.set_rate(self.speaker.rate + d)
        self.settings["rate"] = self.speaker.rate
        say(f"Sprechtempo {self.speaker.rate}")

    def set_theme(self, name):
        if name == "kontrast" and T.name() != "kontrast":
            self.settings["theme_before_hc"] = T.name()
        self.settings["theme"] = name
        self.rebuild()
        say(f"Ansicht {T.NAMES[name]}")

    def cycle_theme(self):
        order = ["dunkel", "hell", "kontrast"]
        self.set_theme(order[(order.index(T.name()) + 1) % 3])

    def toggle_hc(self):
        self.set_theme(self.settings.get("theme_before_hc", "dunkel") if T.is_hc() else "kontrast")

    def toggle_dark_light(self):
        self.set_theme("hell" if T.name() == "dunkel" else "dunkel")

    def set_scale(self, d):
        s = 1.0 if d == 0 else round(T.scale() + d, 2)
        s = max(0.8, min(2.0, s))
        self.settings["scale"] = s
        self.rebuild()
        say(f"Schriftgröße {int(s * 100)} Prozent")

    def rebuild(self):
        if self.busy:
            say("Während eines Vorgangs nicht möglich")
            self.set_status("Darstellung kann während eines Vorgangs nicht geändert werden.", E.YELLOW)
            return
        state = dict(profile=self.current_profile(), name=self.profile_cb.get(), lcur=self.left.cur,
                     rcur=self.right.cur, nav=self.sync_nav.get())
        for w in self.root.winfo_children():
            w.destroy()
        T.apply(self.settings.get("theme", "dunkel"), self.settings.get("scale", 1.0))
        self._build_all()
        self._bind_menu_keys()
        self.theme_var.set(T.name())
        self.reload_drives()
        self.profile_cb["values"] = sorted(self.profiles)
        self.apply_profile(state["profile"], keep_analysis=True)
        if state["name"]:
            self.profile_cb.set(state["name"])
        self.sync_nav.set(state["nav"])
        self._nav_style()
        self.left.cur, self.right.cur = state["lcur"], state["rcur"]
        for t, msg, col in self.log_lines[-2000:]:
            self._log_insert(t, msg, col)
        if self.view_analysis():
            self._after_analysis(replan=True, quiet=True)
        else:
            self.refresh_panes()

    def read_status(self):
        p = self.current_profile()
        parts = [f"Modus {MODE_NAME[p['mode']]}"]
        if p["mode"] != "twoway":
            parts.append("Richtung von links nach rechts" if p["direction"] == "LR" else "Richtung von rechts nach links")
        parts.append(f"Links: {p['left'] or 'kein Ordner'}")
        parts.append(f"Rechts: {p['right'] or 'kein Ordner'}")
        an = self.view_analysis()
        if an:
            s = E.summarize(an.acts)
            parts.append(f"{s['copy_new']} neu, {s['copy_upd']} geändert, {s['move']} umbenannt, "
                         f"{s['delete']} löschen, {s['conflict']} Konflikte, {E.fmt_size(s['bytes'])} zu übertragen")
        else:
            parts.append("noch nicht analysiert")
        parts.append(self.status.cget("text"))
        self.speaker.say(". ".join(parts), force=True)

    # ------------------------------------------------------------ Profile & Einstellungen
    def current_profile(self) -> dict:
        inv = {v: k for k, v in CONFLICT_TXT.items()}

        def num(var, default):
            try:
                return max(0, int(var.get()))
            except (ValueError, tk.TclError):
                return default
        p = {
            "left": self.left.path(), "right": self.right.path(),
            "mode": self.mode_seg.value, "direction": self.direction,
            "compare": self.cmp_seg.value, "archive": self.archive.get(),
            "conflict": inv.get(self.conflict_cb.get(), "newer"),
            "ignore_dst": self.ignore_dst.get(), "excludes": self.excludes.get(),
            "detect_moves": self.moves.get(),
            "archive_days": num(self.arch_days, 90), "archive_keep": num(self.arch_keep, 5),
        }
        for k in USB_KEYS:
            if k in self.usb:
                p[k] = self.usb[k]
        return p

    def apply_profile(self, p: dict, keep_analysis=False):
        p, miss = auto.resolve(p) if p.get("usb_serial") else ({**storage.DEFAULT_PROFILE, **p}, "")
        self.usb = {k: p[k] for k in USB_KEYS if p.get(k)}
        self.left.root_path.set(p["left"])
        self.right.root_path.set(p["right"])
        self.left.cur = self.right.cur = ""
        self.mode_seg.set(p["mode"])
        self.direction = p["direction"]
        self.cmp_seg.set(p["compare"])
        self.archive.set(p["archive"])
        self.conflict_cb.set(CONFLICT_TXT.get(p["conflict"], CONFLICT_TXT["newer"]))
        self.ignore_dst.set(p["ignore_dst"])
        self.excludes.set(p["excludes"])
        self.moves.set(p.get("detect_moves", True))
        self.arch_days.set(str(p.get("archive_days", 90)))
        self.arch_keep.set(str(p.get("archive_keep", 5)))
        if not keep_analysis:
            self.an = None
        self._update_mode_ui()
        self._fill_actions()
        self.refresh_panes()
        self._set_chips(self.view_analysis())
        if miss:
            self.set_status(miss, E.YELLOW, speak=True)

    def _load_initial(self):
        self.reload_drives()
        self.profile_cb["values"] = sorted(self.profiles)
        name = self.settings.get("profile")
        last = self.settings.get("last", {})
        self.apply_profile(self.profiles.get(name, last) if name in self.profiles else last)
        if name in self.profiles:
            self.profile_cb.set(name)
        self.sync_nav.set(self.settings.get("sync_nav", True))
        self._nav_style()

    def load_profile(self, name):
        if name in self.profiles:
            self.apply_profile(self.profiles[name])
            self.set_status(f"Profil „{name}“ geladen.", speak=True)

    def save_profile(self):
        name = ask_string("Profil speichern", "Name für das Profil:", self.root,
                          self.profile_cb.get() or "Mein Backup")
        if not name:
            return
        name = name.strip()
        self.profiles[name] = self.current_profile()
        storage.save_profiles(self.profiles)
        self.profile_cb["values"] = sorted(self.profiles)
        self.profile_cb.set(name)
        self.set_status(f"Profil „{name}“ gespeichert.", E.GREEN, speak=True)

    def delete_profile(self):
        name = self.profile_cb.get()
        if name in self.profiles and ask(APP_NAME, f"Profil „{name}“ löschen?", self.root, risky=True):
            del self.profiles[name]
            storage.save_profiles(self.profiles)
            self.profile_cb["values"] = sorted(self.profiles)
            self.profile_cb.set("")
            self.usb = {}
            self.set_status(f"Profil „{name}“ gelöscht.", speak=True)

    def on_close(self):
        if self.busy and not ask(APP_NAME, "Es läuft noch ein Vorgang. Trotzdem beenden?", self.root, risky=True):
            return
        self.cancel.set()
        self.settings.update(last=self.current_profile(), profile=self.profile_cb.get(),
                             geometry=self.root.geometry(), sync_nav=self.sync_nav.get(),
                             theme=T.name(), scale=T.scale(), speech=self.speaker.enabled,
                             rate=self.speaker.rate)
        try:
            storage.save_settings(self.settings)
        except OSError:
            pass
        self.speaker.close()
        self.root.destroy()

    # ------------------------------------------------------------ Modus / Optionen
    def _update_mode_ui(self):
        mode = self.mode_seg.value
        usb_side = self.usb.get("usb_side")
        tag = {s: (f"   [USB: {self.usb.get('usb_label') or self.usb.get('usb_serial')}]" if usb_side == s else "")
               for s in ("L", "R")}
        if mode == "twoway":
            self.dir_btn.set_text("Links ⇄ Rechts")
            self.dir_btn.set_enabled(False)
            self.left.head.config(text="LINKS" + tag["L"], bg=C["pane_head"], fg=C["pane_head_text"])
            self.right.head.config(text="RECHTS" + tag["R"], bg=C["pane_head"], fg=C["pane_head_text"])
        else:
            lr = self.direction == "LR"
            self.dir_btn.set_enabled(True)
            self.dir_btn.set_text("Links  →  Rechts" if lr else "Links  ←  Rechts",
                                  name="Richtung " + ("von links nach rechts" if lr else "von rechts nach links"))
            src, dst = (self.left, self.right) if lr else (self.right, self.left)
            s_side, d_side = ("LINKS", "RECHTS") if lr else ("RECHTS", "LINKS")
            src.head.config(text=f"{s_side}  ·  Quelle" + tag[src.side], bg=C["pane_head"], fg=C["pane_head_text"])
            dst.head.config(text=f"{d_side}  ·  Ziel" + tag[dst.side], bg=C["accent"], fg=C["accent_text"])
        if mode == "twoway":
            self.conflict_cb.state(["!disabled", "readonly"])
        else:
            self.conflict_cb.state(["disabled"])
        self.mode_info.config(text=MODE_TEXT[mode])

    def set_mode(self, mode):
        self.mode_seg.set(mode, True)

    def on_mode(self, _v=None):
        self._update_mode_ui()
        say(MODE_TEXT[self.mode_seg.value])
        self.on_plan_opt()

    def toggle_direction(self):
        if self.mode_seg.value == "twoway":
            say("Im Zwei-Wege-Modus gibt es keine Richtung")
            return
        self.direction = "RL" if self.direction == "LR" else "LR"
        self._update_mode_ui()
        say("Richtung " + ("von links nach rechts" if self.direction == "LR" else "von rechts nach links"))
        self.on_plan_opt()

    def on_plan_opt(self):
        """Optionen, für die kein neues Einlesen nötig ist -> sofort neu planen."""
        an = self.view_analysis()
        if not an or self.busy:
            return
        o = jobs.options_from_profile(self.current_profile())
        an.opts = o
        an.state = storage.load_state(an.lroot, an.rroot) if o.mode == "twoway" else {}
        an.acts = E.plan(an.L, an.R, an.cmp, o, an.state, (an.lroot, an.rroot))
        an.status = E.status_map(an.L, an.R, an.cmp, an.acts)
        an.warnings = E.space_warnings(an.acts, an.lroot, an.rroot)
        self._after_analysis(replan=True)

    def on_scan_opt(self, _v=None):
        if self.an:
            self.set_status("Vergleichseinstellung geändert – bitte neu analysieren (F5).", E.YELLOW)

    def scan_key(self):
        p = self.current_profile()
        return (os.path.normcase(os.path.abspath(p["left"])) if p["left"] else "",
                os.path.normcase(os.path.abspath(p["right"])) if p["right"] else "",
                p["compare"], p["ignore_dst"], p["excludes"])

    # ------------------------------------------------------------ Explorer-Steuerung
    def reload_drives(self):
        items = drives.list_drives()
        self.left.fill_drives(items)
        self.right.fill_drives(items)
        say(f"{len(items)} Laufwerke und Ordner gefunden")

    def view_analysis(self):
        if self.an and self.an_key and self.an_key[:2] == self.scan_key()[:2]:
            return self.an
        return None

    def is_dir_rel(self, rel):
        an = self.view_analysis()
        if not an:
            return False
        e = an.L.get(rel) or an.R.get(rel)
        return bool(e and e.is_dir)

    def root_changed(self, pane, quiet=False):
        p = pane.path()
        if quiet and p == getattr(pane, "_last_root", None):
            return
        pane._last_root = p
        pane.cur = ""
        # Profil an USB gebunden, Seite manuell geändert -> Bindung lösen
        if self.usb.get("usb_side") == pane.side and not quiet:
            self.usb = {}
            self._update_mode_ui()
        if self.sync_nav.get():
            other = self.right if pane is self.left else self.left
            other.cur = ""
            other.refresh()
        pane.refresh()
        if self.an and not self.view_analysis():
            self._fill_actions()
            self._set_chips(None)
            self.set_status("Ordner geändert – bitte neu analysieren (F5).", E.YELLOW)

    def refresh_panes(self):
        self.left.refresh()
        self.right.refresh()

    def navigate(self, pane, rel):
        targets = [self.left, self.right] if self.sync_nav.get() else [pane]
        for p in targets:
            if self.view_analysis() or os.path.isdir(E.lp(E.join(p.path(), rel))) or p is pane:
                p.cur = rel
            p.refresh()
        kids = pane.tree.get_children()
        if kids:
            pane.tree.focus(kids[0])
            pane.tree.selection_set(kids[0])
        say(f"Ordner {rel.rsplit('/', 1)[-1] if rel else 'oberste Ebene'}, {len(kids)} Einträge")

    def go_up(self, pane):
        if pane.cur:
            old = pane.cur
            self.navigate(pane, E.parent_of(pane.cur))
            if pane.tree.exists(old):
                pane.tree.focus(old)
                pane.tree.selection_set(old)
                pane.tree.see(old)
        else:
            say("Bereits auf oberster Ebene")

    def swap_sides(self):
        if self.busy:
            return
        lp_, rp_ = self.left.path(), self.right.path()
        self.left.root_path.set(rp_)
        self.right.root_path.set(lp_)
        if self.usb.get("usb_side"):
            self.usb["usb_side"] = "R" if self.usb["usb_side"] == "L" else "L"
        self.an = None
        self.left.cur = self.right.cur = ""
        self._update_mode_ui()
        self.refresh_panes()
        self._fill_actions()
        self._set_chips(None)
        self.set_status("Seiten getauscht – bitte neu analysieren (F5).", speak=True)

    def toggle_nav(self):
        self.sync_nav.set(not self.sync_nav.get())
        self._nav_style()
        say("Gekoppelte Navigation " + ("an" if self.sync_nav.get() else "aus"))
        if self.sync_nav.get():
            self.right.cur = self.left.cur
            self.right.refresh()

    def _nav_style(self):
        self.nav_btn.set_style("primary" if self.sync_nav.get() else "secondary")

    def on_scroll(self, pane, first, last):
        pane.vsb.set(first, last)
        if self._scrolling or not self.sync_nav.get() or not self.view_analysis():
            return
        other = self.right if pane is self.left else self.left
        if other.cur != pane.cur:
            return
        if abs(other.tree.yview()[0] - float(first)) > 1e-6:
            self._scrolling = True
            try:
                other.tree.yview_moveto(first)
            finally:
                self._scrolling = False

    def on_select(self, pane):
        if self._selecting or not self.sync_nav.get():
            return
        other = self.right if pane is self.left else self.left
        sel = pane.tree.selection()
        if sel and other.cur == pane.cur and other.tree.exists(sel[0]) and other.tree.selection() != sel:
            self._selecting = True
            try:
                other.tree.selection_set(sel[0])
                other.tree.see(sel[0])
            finally:
                self.root.after_idle(lambda: setattr(self, "_selecting", False))

    # ------------------------------------------------------------ Analyse / Sync
    def set_busy(self, on, text=""):
        self.busy = on
        self.btn_cancel.set_enabled(on)
        self.btn_analyze.set_enabled(not on)
        self.btn_sync.set_enabled(not on)
        if on:
            self.cancel = threading.Event()
            self._spoken_pct = -1
            self.prog["value"] = 0
            self.set_status(text, speak=True)
            self.root.config(cursor="watch")
        else:
            self.root.config(cursor="")

    def do_cancel(self):
        if self.busy:
            self.cancel.set()
            self.set_status("Wird abgebrochen …", E.RED, speak=True)

    def _worker(self, fn):
        def run():
            try:
                fn()
            except E.Cancelled:
                self.q.put(("cancelled",))
            except Exception as e:  # noqa: BLE001
                self.q.put(("error", f"{type(e).__name__}: {e}"))
            finally:
                self.q.put(("idle",))
        threading.Thread(target=run, daemon=True).start()

    def _q_info(self, text, frac=None):
        now = time.time()
        if frac == 1.0 or now - self._last_q > 0.08:
            self._last_q = now
            self.q.put(("info", text, frac))

    def _q_progress(self, done, total, i, n, rel):
        if i is not None:
            self._prog_n = (i, n)
        now = time.time()
        if now - self._last_q > 0.08 or (i is not None and i == n):
            self._last_q = now
            self.q.put(("progress", done, total, self._prog_n[0], self._prog_n[1], rel))

    def analyze(self, then_sync=False):
        if self.busy:
            return
        lroot, rroot = self.left.path(), self.right.path()
        if not lroot or not rroot:
            error(APP_NAME, "Bitte links und rechts einen Ordner wählen.", self.root)
            return
        opts = jobs.options_from_profile(self.current_profile())
        key = self.scan_key()
        self.set_busy(True, "Analyse läuft …")
        self.log("Analyse: " + lroot + "  ⇆  " + rroot)

        def job():
            errs = E.sanity_check(lroot, rroot)   # im Hintergrund: Netzpfade können hängen
            if errs:
                self.q.put(("sanity", errs))
                return
            an = jobs.analyze(lroot, rroot, opts, info=self._q_info, cancel=self.cancel)
            self.q.put(("analysis", an, key, then_sync))
        self._worker(job)

    def sync(self):
        if self.busy:
            return
        if not self.an or self.an_key != self.scan_key():
            self.analyze(then_sync=True)
            return
        self._confirm_and_sync()

    def _confirm_and_sync(self):
        an = self.an
        s = E.summarize(an.acts)
        todo = [a for a in an.acts if a.kind != "conflict"]
        if not todo:
            extra = f"\n\n{s['conflict']} Konflikt(e) werden übersprungen – siehe Liste." if s["conflict"] else ""
            info(APP_NAME, "Alles ist bereits synchron. ✔" + extra, self.root)
            return
        o = jobs.options_from_profile(self.current_profile())
        an.opts.archive, an.opts.archive_days, an.opts.archive_keep = o.archive, o.archive_days, o.archive_keep
        lines = [f"Modus:  {MODE_NAME[an.opts.mode]}", ""]
        for key, txt in (("copy_new", "neue Datei(en) kopieren"), ("copy_upd", "Datei(en) aktualisieren"),
                         ("move", "Datei(en)/Ordner nur umbenennen"), ("mkdir", "Ordner anlegen")):
            if s[key]:
                lines.append(f"●  {s[key]} {txt}")
        if s["delete"]:
            lines.append(f"●  {s['delete']} Element(e) löschen" + (" (→ Archiv)" if an.opts.archive else " (endgültig!)"))
        if s["conflict"]:
            lines.append(f"●  {s['conflict']} Konflikt(e) – werden übersprungen")
        lines.append(f"\nDatenmenge:  {E.fmt_size(s['bytes'])}")
        if an.warnings:
            lines += ["", "⚠ " + "\n⚠ ".join(an.warnings)]
        lines.append("\nJetzt synchronisieren?")
        risky = bool(an.warnings) or (s["delete"] and not an.opts.archive)
        if not ask("Synchronisation starten?", "\n".join(lines), self.root, risky=risky):
            say("Abgebrochen, nichts verändert")
            return
        self.set_busy(True, "Synchronisation läuft …")
        self._executing = True
        self.nb.select(1)
        self.log(f"Start: {len(todo)} Aktionen, {E.fmt_size(s['bytes'])}")

        def job():
            ok, failed = jobs.execute(an, progress=self._q_progress,
                                      log=lambda m, c=None: self.q.put(("log", m, c)), cancel=self.cancel)
            self.q.put(("executed", ok, failed))
        self._worker(job)

    def run_batch(self, job):
        """Sammelauftrag in der Oberfläche ausführen."""
        if self.busy:
            return
        names = storage.load_jobs().get(job, [])
        if not names:
            error(APP_NAME, "Der Sammelauftrag ist leer.", self.root)
            return
        if not ask(f"Sammelauftrag „{job}“", "Diese Profile werden nacheinander ohne weitere Rückfrage "
                   "synchronisiert:\n\n" + "\n".join(f"{i}. {n}" for i, n in enumerate(names, 1)) +
                   "\n\nJetzt starten?", self.root):
            return
        self.set_busy(True, f"Sammelauftrag „{job}“ läuft …")
        self._executing = True
        self.nb.select(1)
        self.log(f"Sammelauftrag „{job}“: {len(names)} Profile")

        def job_fn():
            res = auto.run_batch(job, notify_result=not self._window_active(), progress=self._q_progress,
                                 log=lambda m, c=None: self.q.put(("log", m, c)), cancel=self.cancel,
                                 info=self._q_info,
                                 on_profile=lambda i, n, name: self.q.put(("batchstep", i, n, name)))
            self.q.put(("batchdone", job, res))
        self._worker(job_fn)

    def _window_active(self):
        try:
            return self.root.focus_displayof() is not None
        except (tk.TclError, KeyError):
            return False

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "info":
                    self.set_status(msg[1])
                    if msg[2] is not None:
                        self.prog["value"] = msg[2] * 1000
                elif kind == "progress":
                    done, total, i, n, rel = msg[1:]
                    frac = done / max(total, 1)
                    self.prog["value"] = min(1000, frac * 1000)
                    self.set_status(f"{frac * 100:5.1f} %   ·   {i} / {n}   ·   {E.fmt_size(done)} von "
                                    f"{E.fmt_size(total)}   ·   {rel[-90:]}")
                    step = int(frac * 4)
                    if step > self._spoken_pct and 0 < step < 4:
                        self._spoken_pct = step
                        say(f"{step * 25} Prozent", interrupt=False)
                elif kind == "log":
                    self.log(msg[1], msg[2])
                elif kind == "sanity":
                    error(APP_NAME, "\n\n".join(msg[1]), self.root)
                elif kind == "analysis":
                    self.an, self.an_key = msg[1], msg[2]
                    self._after_analysis()
                    if msg[3]:
                        self._after_idle_action = self._confirm_and_sync
                elif kind == "executed":
                    ok, failed = msg[1], msg[2]
                    col = E.RED if failed else E.GREEN
                    self.log(f"Fertig: {ok} erfolgreich, {failed} Fehler.", col)
                    self.set_status(f"✔ Synchronisation abgeschlossen: {ok} erfolgreich"
                                    + (f", {failed} Fehler – siehe Protokoll" if failed else ""), col, speak=True)
                    self.prog["value"] = 1000
                    if not self._window_active():
                        name = self.profile_cb.get() or "Synchronisation"
                        threading.Thread(target=notify.result_toast, daemon=True, args=([{
                            "name": name, "ok": not failed,
                            "msg": f"{ok} erfolgreich" + (f", {failed} Fehler" if failed else "")}], "SyncWerk: ")
                        ).start()
                    if failed:
                        top = (self.an.error_reasons[:2] if self.an else [])
                        why = "\n\n".join(f"{n} ×  {r}" for r, n in top)
                        warn(APP_NAME, f"{failed} Aktion(en) sind fehlgeschlagen.\n\n"
                                       + (f"Häufigste Ursache:\n{why}\n\n" if why else "")
                                       + "Details stehen im Protokoll.", self.root)
                    self._after_idle_action = self.analyze
                elif kind == "batchstep":
                    i, n, name = msg[1:]
                    self.log(f"── Profil {i}/{n}: {name}", E.BLUE)
                    self.set_status(f"Sammelauftrag: Profil {i} von {n} – {name}", speak=True)
                elif kind == "batchdone":
                    job, res = msg[1], msg[2]
                    bad = [r for r in res if not r["ok"]]
                    for r in res:
                        self.log(("✔ " if r["ok"] else "✕ ") + f"{r['name']}: {r['msg']}",
                                 E.GREEN if r["ok"] else E.RED)
                    text = "\n".join(("✔ " if r["ok"] else "✕ ") + f"{r['name']}: {r['msg']}" for r in res)
                    self.set_status(f"Sammelauftrag „{job}“: {len(res) - len(bad)} von {len(res)} erfolgreich",
                                    E.RED if bad else E.GREEN, speak=True)
                    self.prog["value"] = 1000
                    (warn if bad else info)(f"Sammelauftrag „{job}“", text, self.root)
                elif kind == "cancelled":
                    self.log("Vorgang abgebrochen.", E.RED)
                    self.set_status("Abgebrochen.", E.RED, speak=True)
                    self.prog["value"] = 0
                    if self._executing:
                        self._after_idle_action = self.analyze
                elif kind == "error":
                    self.log("Fehler: " + msg[1], E.RED)
                    error(APP_NAME, msg[1], self.root)
                elif kind == "idle":
                    self.set_busy(False)
                    self._executing = False
                    act, self._after_idle_action = self._after_idle_action, None
                    if act:
                        self.root.after(50, act)
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    def _after_analysis(self, replan=False, quiet=False):
        an = self.an
        if not replan:
            idx = {}
            for rel in set(an.L) | set(an.R):
                e = an.L.get(rel) or an.R.get(rel)
                name = rel.rsplit("/", 1)[-1]
                idx.setdefault(E.parent_of(rel), []).append((not e.is_dir, name.lower(), name, rel))
            for v in idx.values():
                v.sort()
            self.index = idx
            self.totals = {}
            for side, ent in (("L", an.L), ("R", an.R)):
                files = [x for x in ent.values() if not x.is_dir]
                self.totals[side] = (len(files), sum(x.size for x in files))
            for x in an.errors[:50]:
                self.log("Lesefehler: " + x, E.RED)
            if len(an.errors) > 50:
                self.log(f"… {len(an.errors) - 50} weitere Lesefehler", E.RED)
        if not quiet:
            for w in an.warnings:
                self.log("⚠ " + w, E.YELLOW)
        self.refresh_panes()
        self._fill_actions()
        self._set_chips(an)
        s = E.summarize(an.acts)
        n = len([a for a in an.acts if a.kind != "conflict"])
        if n == 0 and not s["conflict"]:
            self.set_status("✔ Alles synchron – nichts zu tun.", E.GREEN, speak=not quiet)
        else:
            self.set_status(
                f"Analyse fertig: {n} Aktion(en) – {s['copy_new']} neu, {s['copy_upd']} geändert, "
                f"{s['move']} umbenannt, {s['delete']} löschen, {s['conflict']} Konflikte; "
                f"{E.fmt_size(s['bytes'])} zu übertragen. Mit F9 synchronisieren.", E.BLUE, speak=not quiet)
        if an.warnings and not quiet:
            say("Achtung: " + " ".join(an.warnings), interrupt=False)
        self.prog["value"] = 0
        if not replan:
            self.nb.select(0)

    def _fill_actions(self):
        t = self.acts
        t.delete(*t.get_children())
        an = self.view_analysis()
        if not an:
            return
        limit = 5000
        for i, a in enumerate(an.acts[:limit]):
            t.insert("", "end", iid=str(i), tags=(a.color,),
                     values=(a.label(), a.rel, E.fmt_size(a.size) if a.kind == "copy" else "", a.reason))
        if len(an.acts) > limit:
            t.insert("", "end", iid="more", values=("", f"… und {len(an.acts) - limit} weitere", "", ""))

    def _act_text(self):
        sel = self.acts.focus()
        if not sel or not self.acts.exists(sel):
            return ""
        a, rel, size, reason = (list(self.acts.item(sel)["values"]) + ["", "", "", ""])[:4]
        return f"{a}: {rel}. {size}. {reason}"

    def _acts_focus(self, _e=None):
        kids = self.acts.get_children()
        if kids and not self.acts.focus():
            self.acts.focus(kids[0])
            self.acts.selection_set(kids[0])
        say(f"Geplante Aktionen, {len(kids)} Einträge. Entf überspringt eine Aktion. {self._act_text()}")

    def _goto_action(self, _e=None):
        sel = self.acts.focus()
        an = self.view_analysis()
        if not an or not sel.isdigit():
            return
        rel = an.acts[int(sel)].rel
        parent = E.parent_of(rel)
        for p in (self.left, self.right):
            p.cur = parent
            p.refresh()
            if p.tree.exists(rel):
                p.tree.selection_set(rel)
                p.tree.focus(rel)
                p.tree.see(rel)
        say(f"Angezeigt in Ordner {parent or 'oberste Ebene'}")

    def _action_menu_key(self, _e=None):
        iid = self.acts.focus()
        if iid.isdigit():
            self._show_action_menu(iid, self.acts.winfo_rootx() + 60, self.acts.winfo_rooty() + 40)

    def _action_menu(self, e):
        iid = self.acts.identify_row(e.y)
        if iid.isdigit():
            self._show_action_menu(iid, e.x_root, e.y_root)

    def _show_action_menu(self, iid, x, y):
        self.acts.selection_set(iid)
        self.acts.focus(iid)
        m = dark_menu(self.root)
        m.add_command(label="Im Explorer oben anzeigen", command=self._goto_action)
        m.add_command(label="Diese Aktion überspringen (Entf)", command=lambda: self._skip_action(int(iid)))
        say("Kontextmenü")
        m.tk_popup(x, y)

    def _skip_action(self, i):
        an = self.view_analysis()
        if an and 0 <= i < len(an.acts):
            a = an.acts.pop(i)
            self.log(f"Übersprungen (manuell): {a.label()} {a.rel}", E.YELLOW)
            say(f"Übersprungen: {a.rel}")
            an.status = E.status_map(an.L, an.R, an.cmp, an.acts)
            self.refresh_panes()
            self._fill_actions()
            self._set_chips(an)
            kids = self.acts.get_children()
            if kids:
                nxt = kids[min(i, len(kids) - 1)]
                self.acts.focus(nxt)
                self.acts.selection_set(nxt)

    def _set_chips(self, an):
        for w in self.chips.winfo_children():
            w.destroy()
        if not an:
            tk.Label(self.chips, text="Noch keine Analyse", bg=C["panel"], fg=C["muted"],
                     font=F(10, "bold")).pack(side="left")
            return
        s = E.summarize(an.acts)
        same = sum(1 for rel, st in an.cmp.items()
                   if st == "gleich" and not an.L.get(rel, E.Entry(0, 0, True)).is_dir)
        items = [(E.GREEN, f"{same:,} identisch".replace(",", ".")),
                 (E.BLUE, f"{s['copy_new']} neu"),
                 (E.YELLOW, f"{s['copy_upd']} geändert"),
                 (E.YELLOW, f"{s['move']} umbenannt"),
                 (E.RED, f"{s['delete']} löschen"),
                 (E.RED, f"{s['conflict']} Konflikte")]
        for col, txt in items:
            f = tk.Frame(self.chips, bg=C[T.TINT[col]], padx=8, pady=2,
                         highlightthickness=1 if T.is_hc() else 0, highlightbackground=C[col])
            f.pack(side="left", padx=(0, 6))
            tk.Label(f, text="●", fg=C[col], bg=C[T.TINT[col]], font=F(10)).pack(side="left")
            tk.Label(f, text=txt, fg=C["text"], bg=C[T.TINT[col]], font=F(10, "bold")).pack(side="left")
        tk.Label(self.chips, text=f"Übertragung: {E.fmt_size(s['bytes'])}", bg=C["panel"], fg=C["text"],
                 font=F(10)).pack(side="left", padx=10)

    # ------------------------------------------------------------ Ausgabe
    def set_status(self, text, col=None, speak=False):
        self.status.config(text=text, fg=C[col] if col else C["muted"])
        if speak:
            say(text)

    def log(self, msg, col=None):
        t = time.strftime("%H:%M:%S  ")
        self.log_lines.append((t, msg, col))
        if len(self.log_lines) > 20000:
            del self.log_lines[:2000]
        self._log_insert(t, msg, col)

    def _log_insert(self, t, msg, col):
        w = self.logw
        w.config(state="normal")
        w.insert("end", t, "time")
        w.insert("end", msg + "\n", col or "")
        if int(w.index("end-1c").split(".")[0]) > 20000:
            w.delete("1.0", "2000.0")
        w.see("end")
        w.config(state="disabled")

    # ------------------------------------------------------------ Dialoge
    def show_info(self):
        from . import watcher
        w = "läuft" if watcher.is_running() else "nicht aktiv"
        MessageDialog(self.root, "info", f"Über {APP_NAME}",
                      f"{APP_NAME} {APP_VERSION}\n"
                      "Synchronisation & Backup – lokal, USB, Netzwerk und Cloud\n\n"
                      f"© 2026 {APP_AUTHOR}\n"
                      f"Idee und Prompt: {APP_AUTHOR}\n"
                      f"Umsetzung: {APP_IMPL}, {APP_DATE_LONG}\n\n"
                      f"Sprachausgabe: {'an' if self.speaker.enabled else 'aus'}\n"
                      f"Ansicht: {T.NAMES[T.name()]}\n"
                      f"USB-Wächter: {w}\n"
                      f"Einstellungen: {storage.app_dir()}")

    def show_help(self):
        from .dialogs import HelpWindow
        HelpWindow(self)

    def open_restore(self):
        from .dialogs import RestoreDialog
        RestoreDialog(self)

    def open_batch(self):
        from .dialogs import BatchDialog
        BatchDialog(self)

    def open_automation(self):
        name = self.profile_cb.get()
        if not name or name not in self.profiles:
            info(APP_NAME, "Bitte die Einstellungen zuerst als Profil speichern (Strg+S).", self.root)
            return
        from .dialogs import AutomationDialog
        AutomationDialog(self, name)

    def cleanup_now(self):
        from . import archive
        o = jobs.options_from_profile(self.current_profile())
        if not (o.archive_days or o.archive_keep):
            info(APP_NAME, "Aufbewahrung ist unbegrenzt (0 Tage und 0 Versionen) – nichts aufzuräumen.", self.root)
            return
        total = freed = 0
        for root in {self.left.path(), self.right.path()} - {""}:
            if os.path.isdir(E.lp(root)):
                n, f = archive.cleanup(root, o.archive_days, o.archive_keep)
                total += n
                freed += f
        self.log(f"Archiv aufgeräumt: {total} alte Versionen, {E.fmt_size(freed)} frei", E.GREEN)
        info(APP_NAME, f"Archiv aufgeräumt: {total} alte Versionen entfernt, {E.fmt_size(freed)} frei.", self.root)


def main():
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(notify.AUMID)
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()
