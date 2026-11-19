"""Dialoge: Hilfe, Archiv-Wiederherstellung, Sammelaufträge, Automatik (Zeitplan, USB, Wächter)."""
import os
import subprocess
import sys
import time
import tkinter as tk
from tkinter import ttk, filedialog

from . import APP_NAME
from . import archive
from . import drives
from . import engine as E
from . import storage
from . import theme as T
from . import watcher
from .theme import C, F
from .widgets import (KEYS, Dialog, FlatButton, acc, ask, ask_string, error, info, open_path, resource,
                      reveal, say)

IS_WIN = sys.platform.startswith("win")
NO_WINDOW = 0x08000000


def _listbox(parent, height=10, width=30):
    lb = tk.Listbox(parent, height=height, width=width, bg=C["field"], fg=C["text"], font=F(10),
                    selectbackground=C["sel_bg"], selectforeground=C["sel_text"], activestyle="none",
                    highlightthickness=2, highlightcolor=C["focus"], highlightbackground=C["border"],
                    relief="flat", exportselection=False)
    return lb


def _lb_speech(lb, name):
    def cur():
        sel = lb.curselection()
        if sel:
            return f"{lb.get(sel[0])}, {sel[0] + 1} von {lb.size()}"
        return f"{lb.size()} Einträge" if lb.size() else "leer"
    acc(lb, name, cur)
    lb.bind("<<ListboxSelect>>", lambda e: lb.focus_get() is lb and say(cur()), add="+")

    def first(_e=None):
        if lb.size() and not lb.curselection():
            lb.selection_set(0)
            lb.activate(0)
    lb.bind("<FocusIn>", first, add="+")


# ====================================================================== Hilfe
HELP = [
    ("So geht's", [
        "1. Links und rechts einen Ordner wählen: Laufwerksliste, „Ordner …“ oder Pfad eintippen und Enter – "
        "auch \\\\server\\freigabe oder ein pCloud-/Nextcloud-Laufwerk.",
        "2. Modus wählen: Backup, Spiegeln oder Zwei-Wege (Alt+1/2/3).",
        "3. Analysieren (F5) – es wird nichts verändert, nur verglichen.",
        "4. Geplante Aktionen prüfen (Strg+3). Entf überspringt eine einzelne Aktion.",
        "5. Synchronisieren (F9). Abbrechen jederzeit mit Esc.",
    ]),
    ("Modi", [
        "Backup – kopiert Neues und Geändertes von der Quelle ins Ziel, löscht nie.",
        "Spiegeln – Ziel wird exakte Kopie der Quelle.",
        "Zwei-Wege – beide Seiten werden gleichgestellt, auch Löschungen werden übernommen.",
        "Umbenannte oder verschobene Dateien und Ordner werden erkannt und im Ziel nur umbenannt.",
    ]),
    ("Farben", [
        "Grün: identisch / erledigt.   Blau: neu – wird kopiert.",
        "Gelb: geändert oder umbenannt.   Rot: wird gelöscht, Konflikt oder Fehler.",
    ]),
    ("Archiv", [
        f"Gelöschte und überschriebene Dateien landen im Ordner „{E.ARCHIVE_DIR}“. Das Archiv räumt sich "
        "selbst auf (Standard: 90 Tage, höchstens 5 Versionen je Datei). Strg+R öffnet das Wiederherstellen.",
    ]),
    ("Automatik", [
        "Automatik …: Zeitplan über die Windows-Aufgabenplanung und USB-Auslöser – das Profil startet, "
        "sobald eine bestimmte Platte angesteckt wird (erkannt an der Seriennummer, nicht am Laufwerksbuchstaben).",
        "Sammelaufträge (Strg+J): mehrere Profile nacheinander, z. B. ein Feierabend-Backup.",
        "Nach automatischen Läufen erscheint eine Windows-Benachrichtigung – bei Fehlern mit rotem Symbol.",
    ]),
    ("Barrierefreiheit", [
        "F2 schaltet die Sprachausgabe ein oder aus. Alle Bedienelemente sind mit Tab erreichbar und werden "
        "vorgelesen. Strg+I liest den Status vor, Strg+W wiederholt die letzte Ansage.",
        "F3 schaltet den Hohen Kontrast (Gelb/Weiß auf Schwarz) um, F4 wechselt Dunkel/Hell, "
        "Strg+Plus/Minus ändert die Schriftgröße.",
        "Menüleiste: F10 oder Alt+unterstrichener Buchstabe (z. B. Alt+D für Datei), Pfeile zum Wählen. "
        "Menüpunkte und alle Meldungsfenster werden von der Sprachausgabe vorgelesen.",
    ]),
]


class HelpWindow(Dialog):
    def __init__(self, app):
        super().__init__(app, "Hilfe", "Mit Tab zu Vorlesen.")
        self.geometry(f"{int(760 * T.scale())}x{int(680 * T.scale())}")
        txt = tk.Text(self, wrap="word", bg=C["field"], fg=C["text"], relief="flat", padx=16, pady=12,
                      font=F(10), highlightthickness=2, highlightcolor=C["focus"],
                      highlightbackground=C["border"])
        txt.pack(fill="both", expand=True)
        txt.tag_configure("h", font=F(12, "bold"), foreground=C["accent"], spacing1=10, spacing3=4)
        txt.tag_configure("k", font=F(10, "bold"), foreground=C["accent"])
        plain = []
        for head, lines in HELP:
            txt.insert("end", head + "\n", "h")
            for line in lines:
                txt.insert("end", line + "\n")
            plain.append(head + ". " + " ".join(lines))
        txt.insert("end", "Tastenkürzel\n", "h")
        for k, d in KEYS:
            txt.insert("end", f"{k:<28}", "k")
            txt.insert("end", d + "\n")
        plain.append("Tastenkürzel. " + ". ".join(f"{k}: {d}" for k, d in KEYS))
        txt.config(state="disabled")
        self.plain = plain
        bf = tk.Frame(self, bg=C["panel"], pady=10)
        bf.pack(fill="x")
        b = FlatButton(bf, "Alles vorlesen", self.read_all, "primary", name="Hilfe vollständig vorlesen")
        b.pack(side="left")
        FlatButton(bf, "Nur Tastenkürzel vorlesen", lambda: app.speaker.say(plain[-1], force=True)) \
            .pack(side="left", padx=6)
        FlatButton(bf, "Kurzanleitung (PDF)", lambda: open_path(resource("SyncWerk-Kurzanleitung.pdf"))) \
            .pack(side="left", padx=6)
        FlatButton(bf, "Schließen", self.close).pack(side="right")
        b.focus_set()

    def read_all(self):
        self.app.speaker.say(" ".join(self.plain), force=True)


# ====================================================================== Wiederherstellen
class RestoreDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Archiv – Versionen wiederherstellen",
                         "Liste der archivierten Versionen. Eingabetaste stellt die gewählte Version wieder her.")
        self.geometry(f"{int(980 * T.scale())}x{int(600 * T.scale())}")
        self.roots = [(n, p) for n, p in (("Links", app.left.path()), ("Rechts", app.right.path()))
                      if p and os.path.isdir(E.lp(p))]
        top = tk.Frame(self, bg=C["panel"])
        top.pack(fill="x")
        self.label(top, "Suchen").pack(side="left")
        self.q = tk.StringVar()
        e = ttk.Entry(top, textvariable=self.q, font=F(10), width=36)
        e.pack(side="left", padx=6)
        acc(e, "Dateiname suchen")
        self.q.trace_add("write", lambda *a: self.fill())
        self.label(top, "Seite").pack(side="left", padx=(12, 4))
        self.side = ttk.Combobox(top, state="readonly", width=10, values=["Beide", "Links", "Rechts"], font=F(10))
        self.side.set("Beide")
        self.side.pack(side="left")
        self.side.bind("<<ComboboxSelected>>", lambda e: (say(self.side.get()), self.fill()))
        acc(self.side, "Seite filtern", lambda: self.side.get())
        self.count = self.label(top, "", muted=True)
        self.count.pack(side="right")

        box = tk.Frame(self, bg=C["panel"])
        box.pack(fill="both", expand=True, pady=8)
        self.tree = ttk.Treeview(box, columns=("rel", "when", "size", "side"), show="headings")
        for c, t, w, a in (("rel", "Datei", 480, "w"), ("when", "Archiviert am", 150, "w"),
                           ("size", "Größe", 90, "e"), ("side", "Seite", 70, "w")):
            self.tree.heading(c, text=t, anchor=a)
            self.tree.column(c, width=int(w * T.scale()), anchor=a, stretch=c == "rel")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Return>", lambda e: self.restore())
        self.tree.bind("<Double-1>", lambda e: self.restore())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.focus_get() is self.tree and say(self.row_text()))
        self.tree.bind("<FocusIn>", self._focus, add="+")

        bf = tk.Frame(self, bg=C["panel"])
        bf.pack(fill="x")
        FlatButton(bf, "Wiederherstellen", self.restore, "primary",
                   tip="An den ursprünglichen Ort; die aktuelle Datei wird vorher selbst archiviert") \
            .pack(side="left")
        FlatButton(bf, "Wiederherstellen nach …", self.restore_to).pack(side="left", padx=6)
        FlatButton(bf, "Öffnen", lambda: self.sel() and open_path(E.lp(self.sel().path))).pack(side="left", padx=6)
        FlatButton(bf, "Im Explorer zeigen", lambda: self.sel() and reveal(self.sel().path)).pack(side="left")
        FlatButton(bf, "Jetzt aufräumen", self.cleanup,
                   tip="Versionen nach den Aufbewahrungsregeln des Profils löschen").pack(side="left", padx=6)
        FlatButton(bf, "Schließen", self.close).pack(side="right")
        self.load()
        self.tree.focus_set()

    def load(self):
        self.versions = []
        self.config(cursor="watch")
        self.update_idletasks()
        for name, root in self.roots:
            for v in archive.list_versions(root):
                v.side = name
                self.versions.append(v)
        self.config(cursor="")
        self.fill()

    def fill(self):
        t = self.tree
        t.delete(*t.get_children())
        q = self.q.get().lower().strip()
        side = self.side.get()
        self.shown = []
        for v in self.versions:
            if q and q not in v.rel.lower():
                continue
            if side != "Beide" and v.side != side:
                continue
            self.shown.append(v)
        for i, v in enumerate(self.shown[:5000]):
            t.insert("", "end", iid=str(i), values=(v.rel, time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(v.when)),
                                                    E.fmt_size(v.size), v.side))
        self.count.config(text=f"{len(self.shown)} Versionen")
        if not self.versions:
            self.count.config(text="Kein Archiv vorhanden")

    def sel(self):
        f = self.tree.focus()
        return self.shown[int(f)] if f.isdigit() and int(f) < len(self.shown) else None

    def row_text(self):
        v = self.sel()
        if not v:
            return ""
        return (f"{v.rel}, archiviert am {time.strftime('%d.%m.%Y %H:%M', time.localtime(v.when))}, "
                f"{E.fmt_size(v.size)}, {v.side}")

    def _focus(self, _e=None):
        kids = self.tree.get_children()
        if kids and not self.tree.focus():
            self.tree.focus(kids[0])
            self.tree.selection_set(kids[0])
        say(f"Archivierte Versionen, {len(self.shown)} Einträge. {self.row_text()}")

    def restore(self):
        v = self.sel()
        if not v:
            return
        if not ask("Wiederherstellen", f"„{v.rel}“ vom "
                   f"{time.strftime('%d.%m.%Y %H:%M', time.localtime(v.when))} wiederherstellen?\n\n"
                   "Eine vorhandene aktuelle Datei wird vorher archiviert.", self):
            return
        try:
            dst = archive.restore(v)
            self.app.log(f"Wiederhergestellt: {v.rel} (Version {v.stamp})", E.GREEN)
            self.app.set_status("Datei wiederhergestellt – bitte neu analysieren (F5).", E.YELLOW)
            info("Wiederherstellen", f"Wiederhergestellt:\n{dst}", self)
            self.load()
        except OSError as e:
            error("Wiederherstellen", str(e), self)

    def restore_to(self):
        v = self.sel()
        if not v:
            return
        d = filedialog.askdirectory(parent=self, title="Zielordner für die Wiederherstellung")
        if d:
            try:
                dst = archive.restore(v, os.path.join(d, v.rel.rsplit("/", 1)[-1]))
                info("Wiederherstellen", f"Gespeichert unter:\n{dst}", self)
            except OSError as e:
                error("Wiederherstellen", str(e), self)

    def cleanup(self):
        p = self.app.current_profile()
        days, keep = p["archive_days"], p["archive_keep"]
        if not (days or keep):
            info(APP_NAME, "Aufbewahrung ist unbegrenzt – nichts aufzuräumen.", self)
            return
        if not ask("Archiv aufräumen", f"Versionen älter als {days or '∞'} Tage und mehr als "
                   f"{keep or '∞'} Versionen je Datei endgültig löschen?", self, risky=True):
            return
        total = freed = 0
        for _, root in self.roots:
            n, f = archive.cleanup(root, days, keep)
            total += n
            freed += f
        info("Archiv aufräumen", f"{total} Versionen gelöscht, {E.fmt_size(freed)} frei.", self)
        self.load()


# ====================================================================== Zeitplan (gemeinsam)
def task_command(extra_args: str) -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" {extra_args}'
    pyw = sys.executable.replace("python.exe", "pythonw.exe")
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SyncWerk.py")
    return f'"{pyw}" "{script}" {extra_args}'


class ScheduleBox(tk.Frame):
    """Eingabe Häufigkeit/Uhrzeit + Aufgabe anlegen/entfernen."""
    FREQ = ["Täglich", "Wöchentlich (Montag)", "Wöchentlich (Freitag)", "Stündlich", "Bei Anmeldung"]

    def __init__(self, parent, dialog, task_name, args):
        super().__init__(parent, bg=C["panel"])
        self.dialog, self.task_name = dialog, task_name
        self.cmd = task_command(args)
        dialog.label(self, "Häufigkeit").grid(row=0, column=0, sticky="w")
        self.freq = ttk.Combobox(self, state="readonly", width=24, values=self.FREQ, font=F(10))
        self.freq.set("Täglich")
        self.freq.grid(row=0, column=1, sticky="w", pady=3)
        self.freq.bind("<<ComboboxSelected>>", lambda e: say(self.freq.get()))
        acc(self.freq, "Häufigkeit", lambda: self.freq.get())
        dialog.label(self, "Uhrzeit (HH:MM)").grid(row=1, column=0, sticky="w")
        self.tvar = tk.StringVar(value="20:00")
        te = ttk.Entry(self, textvariable=self.tvar, width=8, font=F(10))
        te.grid(row=1, column=1, sticky="w", pady=3)
        acc(te, "Uhrzeit, Stunden Doppelpunkt Minuten", lambda: self.tvar.get())
        dialog.label(self, "Befehl", muted=True).grid(row=2, column=0, sticky="nw", pady=(6, 0))
        tk.Label(self, text=self.cmd, bg=C["ctrl"], fg=C["ctrl_text"], font=F(8), wraplength=int(520 * T.scale()),
                 justify="left", padx=6, pady=4).grid(row=2, column=1, sticky="w", pady=(6, 0))
        bf = tk.Frame(self, bg=C["panel"])
        bf.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        FlatButton(bf, "Aufgabe anlegen", self.create, "primary", name=f"Zeitplan-Aufgabe {task_name} anlegen") \
            .pack(side="left")
        FlatButton(bf, "Aufgabe entfernen", self.remove).pack(side="left", padx=6)

    def create(self):
        if not IS_WIN:
            self.clipboard_clear()
            self.clipboard_append(self.cmd)
            info(APP_NAME, "Die Aufgabenplanung gibt es nur unter Windows.\nBefehl wurde kopiert.", self.dialog)
            return
        tm = self.tvar.get().strip()
        try:
            time.strptime(tm, "%H:%M")
        except ValueError:
            error(APP_NAME, "Uhrzeit bitte als HH:MM angeben, z. B. 20:00.", self.dialog)
            return
        if len(self.cmd) > 261:
            error(APP_NAME, "Der Befehl ist für die Aufgabenplanung zu lang (max. 261 Zeichen).\n"
                            "Tipp: SyncWerk.exe in einen kürzeren Ordner legen, z. B. C:\\SyncWerk.", self.dialog)
            return
        sc = {"Täglich": ["/SC", "DAILY", "/ST", tm],
              "Wöchentlich (Montag)": ["/SC", "WEEKLY", "/D", "MON", "/ST", tm],
              "Wöchentlich (Freitag)": ["/SC", "WEEKLY", "/D", "FRI", "/ST", tm],
              "Stündlich": ["/SC", "HOURLY"],
              "Bei Anmeldung": ["/SC", "ONLOGON"]}[self.freq.get()]
        args = ["schtasks", "/Create", "/F", "/TN", f"SyncWerk\\{self.task_name}", "/TR", self.cmd] + sc
        try:
            r = subprocess.run(args, capture_output=True, text=True, creationflags=NO_WINDOW)
            if r.returncode == 0:
                info(APP_NAME, f"Aufgabe „SyncWerk\\{self.task_name}“ wurde angelegt "
                               f"({self.freq.get()}{'' if 'Stünd' in self.freq.get() or 'Anmeld' in self.freq.get() else ', ' + tm}).",
                     self.dialog)
            else:
                error(APP_NAME, (r.stderr or r.stdout).strip() +
                      "\n\nTipp: „Bei Anmeldung“ braucht ggf. Administratorrechte.", self.dialog)
        except OSError as e:
            error(APP_NAME, str(e), self.dialog)

    def remove(self):
        if not IS_WIN:
            return
        r = subprocess.run(["schtasks", "/Delete", "/F", "/TN", f"SyncWerk\\{self.task_name}"],
                           capture_output=True, text=True, creationflags=NO_WINDOW)
        info(APP_NAME, "Aufgabe entfernt." if r.returncode == 0 else (r.stderr or r.stdout).strip(), self.dialog)


# ====================================================================== Automatik (Profil)
class AutomationDialog(Dialog):
    def __init__(self, app, name):
        super().__init__(app, f"Automatik für Profil {name}",
                         "Zeitplan, USB-Auslöser und Hintergrund-Wächter.")
        self.name = name
        if app.profiles[name] != app.current_profile() and ask(
                APP_NAME, f"Aktuelle Einstellungen im Profil „{name}“ speichern?", self):
            app.profiles[name] = app.current_profile()
            storage.save_profiles(app.profiles)
        self.p = dict(app.profiles[name])

        self.label(self, f"Profil „{name}“ automatisch ausführen", bold=True, size=13).pack(anchor="w")
        self.label(self, "Automatische Läufe fragen nicht nach. Sie brechen ab, wenn die Quelle leer oder "
                         "nicht erreichbar ist oder der Platz nicht reicht. Ergebnis: Windows-Benachrichtigung "
                         "und Protokoll.", muted=True, wrap=int(620 * T.scale())).pack(anchor="w", pady=(2, 8))

        self._section("1  Zeitplan (Windows-Aufgabenplanung)")
        ScheduleBox(self, self, name, f'--profil "{name}" --auto').pack(anchor="w", padx=12)

        self._section("2  USB-Auslöser – starten, wenn eine bestimmte Platte angesteckt wird")
        uf = tk.Frame(self, bg=C["panel"])
        uf.pack(anchor="w", fill="x", padx=12)
        self.label(uf, "Welche Seite liegt auf der USB-Platte?").pack(anchor="w")
        rf = tk.Frame(uf, bg=C["panel"])
        rf.pack(anchor="w", pady=2)
        self.side = tk.StringVar(value=self.p.get("usb_side") or "")
        for val, txt in (("", "keine"), ("L", f"Links  ({app.left.path() or '–'})"),
                         ("R", f"Rechts  ({app.right.path() or '–'})")):
            rb = ttk.Radiobutton(rf, text=txt, value=val, variable=self.side, command=self._detect)
            rb.pack(anchor="w")
            acc(rb, f"USB-Seite {txt}, Optionsfeld", lambda v=val: "ausgewählt" if self.side.get() == v else "")
        self.detect = self.label(uf, "", wrap=int(620 * T.scale()))
        self.detect.pack(anchor="w", pady=4)
        self.auto = tk.BooleanVar(value=bool(self.p.get("usb_auto")))
        cb = ttk.Checkbutton(uf, text="Profil automatisch starten, wenn diese Platte angesteckt wird",
                             variable=self.auto, command=lambda: say("an" if self.auto.get() else "aus"))
        cb.pack(anchor="w")
        acc(cb, "Automatisch starten beim Anstecken, Kontrollkästchen", lambda: "an" if self.auto.get() else "aus")
        FlatButton(uf, "USB-Einstellung übernehmen", self.save_usb, "primary").pack(anchor="w", pady=6)

        self._section("3  Hintergrund-Wächter (nötig für den USB-Auslöser)")
        wf = tk.Frame(self, bg=C["panel"])
        wf.pack(anchor="w", fill="x", padx=12)
        self.wstat = self.label(wf, "")
        self.wstat.pack(anchor="w")
        bf = tk.Frame(wf, bg=C["panel"])
        bf.pack(anchor="w", pady=6)
        FlatButton(bf, "Wächter aktivieren (Autostart)", self.w_on, "primary",
                   tip="Startet unsichtbar mit Windows und beobachtet angesteckte Laufwerke").pack(side="left")
        FlatButton(bf, "Wächter deaktivieren", self.w_off).pack(side="left", padx=6)
        FlatButton(self, "Schließen", self.close).pack(anchor="e", pady=(10, 0))
        self._detect(initial=True)
        self._wstatus()

    def _section(self, text):
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x", pady=(12, 6))
        self.label(self, text, bold=True, size=11).pack(anchor="w", pady=(0, 4))

    def _detect(self, initial=False):
        side = self.side.get()
        self.vol = None
        if not side:
            txt = "Kein USB-Auslöser."
        elif not IS_WIN:
            txt = "USB-Erkennung per Seriennummer gibt es nur unter Windows."
        else:
            path = self.app.left.path() if side == "L" else self.app.right.path()
            self.vol = drives.volume_info(path) if path else None
            if self.vol:
                sn, root, label, kind = self.vol
                txt = (f"Erkannt: „{label or 'ohne Namen'}“ auf {root} – Seriennummer {sn}"
                       + ("" if kind == "usb" else "  (als festes Laufwerk gemeldet – funktioniert trotzdem)"))
            elif self.p.get("usb_serial") and side == self.p.get("usb_side"):
                txt = (f"Gespeichert: „{self.p.get('usb_label')}“, Seriennummer {self.p['usb_serial']} "
                       "(Platte derzeit nicht angesteckt)")
            else:
                txt = "Dieser Ordner liegt auf keinem lokalen/USB-Laufwerk (Netzlaufwerke gehen nicht)."
        self.detect.config(text=txt, fg=C["text"] if self.vol else C["muted"])
        if not initial:
            say(txt)

    def save_usb(self):
        side = self.side.get()
        p = self.app.profiles[self.name]
        if not side:
            for k in ("usb_serial", "usb_label", "usb_side", "usb_rel", "usb_auto"):
                p.pop(k, None)
            msg = "USB-Auslöser entfernt."
        else:
            if self.vol:
                sn, root, label, _ = self.vol
                path = self.app.left.path() if side == "L" else self.app.right.path()
                rel = os.path.relpath(path, root) if os.path.normcase(path) != os.path.normcase(root) else ""
                p.update(usb_serial=sn, usb_label=label, usb_side=side, usb_rel="" if rel == "." else rel)
            elif not (p.get("usb_serial") and p.get("usb_side") == side):
                error(APP_NAME, "Die Platte muss zum Einrichten angesteckt sein.", self)
                return
            p["usb_auto"] = self.auto.get()
            msg = (f"USB-Auslöser gespeichert: „{p.get('usb_label') or p['usb_serial']}“."
                   + (" Startet automatisch beim Anstecken." if p["usb_auto"] else ""))
            if p["usb_auto"] and not watcher.is_running():
                msg += "\n\nHinweis: Der Hintergrund-Wächter läuft noch nicht – bitte unten aktivieren."
        storage.save_profiles(self.app.profiles)
        self.app.usb = {k: p[k] for k in ("usb_serial", "usb_label", "usb_side", "usb_rel", "usb_auto") if p.get(k)}
        self.app._update_mode_ui()
        info(APP_NAME, msg, self)

    def _wstatus(self):
        run, inst = watcher.is_running(), watcher.is_installed()
        txt = ("● Wächter läuft" if run else "● Wächter läuft nicht") + \
              (" · startet automatisch mit Windows" if inst else " · kein Autostart")
        n = len(watcher.usb_profiles())
        txt += f" · {n} Profil(e) mit USB-Auslöser"
        self.wstat.config(text=txt, fg=C["green"] if run else C["muted"])

    def w_on(self):
        if not IS_WIN:
            info(APP_NAME, "Der Wächter ist nur unter Windows verfügbar.", self)
            return
        try:
            watcher.install()
        except OSError as e:
            error(APP_NAME, str(e), self)
        self.after(1500, self._wstatus)
        say("Wächter aktiviert")

    def w_off(self):
        watcher.uninstall()
        self.after(4000, self._wstatus)
        say("Wächter wird beendet und aus dem Autostart entfernt")


# ====================================================================== Sammelaufträge
class BatchDialog(Dialog):
    def __init__(self, app):
        super().__init__(app, "Sammelaufträge",
                         "Mehrere Profile nacheinander ausführen, zum Beispiel als Feierabend-Backup.")
        self.jobs = storage.load_jobs()
        row = tk.Frame(self, bg=C["panel"])
        row.pack(fill="x")
        self.label(row, "Sammelauftrag", bold=True).pack(side="left")
        self.job = ttk.Combobox(row, state="readonly", width=28, values=sorted(self.jobs), font=F(10))
        self.job.pack(side="left", padx=6)
        self.job.bind("<<ComboboxSelected>>", lambda e: (say(self.job.get()), self.load()))
        acc(self.job, "Sammelauftrag wählen", lambda: self.job.get() or "keiner")
        FlatButton(row, "Neu …", self.new, name="Neuen Sammelauftrag anlegen").pack(side="left", padx=2)
        FlatButton(row, "Löschen", self.delete, name="Sammelauftrag löschen").pack(side="left", padx=2)

        body = tk.Frame(self, bg=C["panel"], pady=10)
        body.pack(fill="both", expand=True)
        l1 = tk.Frame(body, bg=C["panel"])
        l1.pack(side="left", fill="both", expand=True)
        self.label(l1, "Verfügbare Profile").pack(anchor="w")
        self.avail = _listbox(l1)
        self.avail.pack(fill="both", expand=True)
        _lb_speech(self.avail, "Verfügbare Profile. Eingabetaste fügt hinzu")
        self.avail.bind("<Return>", lambda e: self.add())
        self.avail.bind("<Double-1>", lambda e: self.add())
        mid = tk.Frame(body, bg=C["panel"], padx=10)
        mid.pack(side="left")
        for txt, fn, nm in (("Hinzufügen →", self.add, "Hinzufügen"), ("← Entfernen", self.remove, "Entfernen"),
                            ("▲ Nach oben", lambda: self.move(-1), "Nach oben"),
                            ("▼ Nach unten", lambda: self.move(1), "Nach unten")):
            FlatButton(mid, txt, fn, padx=10, pady=4, name=nm).pack(fill="x", pady=3)
        l2 = tk.Frame(body, bg=C["panel"])
        l2.pack(side="left", fill="both", expand=True)
        self.label(l2, "Im Auftrag (Reihenfolge)").pack(anchor="w")
        self.inj = _listbox(l2)
        self.inj.pack(fill="both", expand=True)
        _lb_speech(self.inj, "Profile im Auftrag. Entf entfernt, Strg Pfeil verschiebt")
        self.inj.bind("<Delete>", lambda e: self.remove())
        self.inj.bind("<Control-Up>", lambda e: self.move(-1))
        self.inj.bind("<Control-Down>", lambda e: self.move(1))

        self.sched_holder = tk.Frame(self, bg=C["panel"])
        self.sched_holder.pack(fill="x")
        bf = tk.Frame(self, bg=C["panel"], pady=8)
        bf.pack(fill="x")
        FlatButton(bf, "Speichern", self.save, name="Sammelauftrag speichern").pack(side="left")
        FlatButton(bf, "Zeitplan …", self.schedule, name="Zeitplan für diesen Sammelauftrag").pack(side="left", padx=6)
        FlatButton(bf, "▶  Jetzt ausführen", self.run, "primary", name="Sammelauftrag jetzt ausführen") \
            .pack(side="left", padx=6)
        FlatButton(bf, "Schließen", self.close).pack(side="right")
        if self.jobs:
            self.job.set(sorted(self.jobs)[0])
        self.load()
        self.job.focus_set()

    def load(self):
        names = self.jobs.get(self.job.get(), [])
        self.inj.delete(0, "end")
        for n in names:
            self.inj.insert("end", n)
        self.avail.delete(0, "end")
        for n in sorted(self.app.profiles):
            self.avail.insert("end", n)

    def new(self):
        n = ask_string("Neuer Sammelauftrag", "Name des Sammelauftrags:", self, "Feierabend")
        if n:
            self.jobs.setdefault(n, [])
            self.job["values"] = sorted(self.jobs)
            self.job.set(n)
            self.load()
            say(f"Sammelauftrag {n} angelegt. Profile links auswählen und hinzufügen.")
            self.avail.focus_set()

    def delete(self):
        n = self.job.get()
        if n in self.jobs and ask(APP_NAME, f"Sammelauftrag „{n}“ löschen?", self, risky=True):
            del self.jobs[n]
            storage.save_jobs(self.jobs)
            self.job["values"] = sorted(self.jobs)
            self.job.set("")
            self.load()

    def add(self):
        if not self.job.get():
            self.new()
            if not self.job.get():
                return
        for i in self.avail.curselection():
            name = self.avail.get(i)
            if name not in self.inj.get(0, "end"):
                self.inj.insert("end", name)
                say(f"{name} hinzugefügt, Position {self.inj.size()}")

    def remove(self):
        sel = self.inj.curselection()
        if sel:
            name = self.inj.get(sel[0])
            self.inj.delete(sel[0])
            say(f"{name} entfernt")
            if self.inj.size():
                i = min(sel[0], self.inj.size() - 1)
                self.inj.selection_set(i)
                self.inj.activate(i)

    def move(self, d):
        sel = self.inj.curselection()
        if not sel:
            return "break"
        i = sel[0]
        j = i + d
        if 0 <= j < self.inj.size():
            name = self.inj.get(i)
            self.inj.delete(i)
            self.inj.insert(j, name)
            self.inj.selection_clear(0, "end")
            self.inj.selection_set(j)
            self.inj.activate(j)
            say(f"{name} jetzt Position {j + 1}")
        return "break"

    def save(self):
        n = self.job.get()
        if not n:
            self.new()
            n = self.job.get()
            if not n:
                return
        self.jobs[n] = list(self.inj.get(0, "end"))
        storage.save_jobs(self.jobs)
        info(APP_NAME, f"Sammelauftrag „{n}“ gespeichert ({len(self.jobs[n])} Profile).", self)

    def schedule(self):
        n = self.job.get()
        if not n:
            return
        self.save()
        for w in self.sched_holder.winfo_children():
            w.destroy()
        tk.Frame(self.sched_holder, bg=C["border"], height=1).pack(fill="x", pady=6)
        self.label(self.sched_holder, f"Zeitplan für „{n}“", bold=True).pack(anchor="w")
        box = ScheduleBox(self.sched_holder, self, f"Auftrag {n}", f'--auftrag "{n}" --auto')
        box.pack(anchor="w")
        box.freq.focus_set()

    def run(self):
        n = self.job.get()
        if not n:
            return
        self.jobs[n] = list(self.inj.get(0, "end"))
        storage.save_jobs(self.jobs)
        self.close()
        self.app.run_batch(n)
