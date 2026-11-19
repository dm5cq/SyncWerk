"""Sync-Engine: Einlesen, Vergleichen, Planen und Ausführen.

Pfade werden intern relativ und mit '/' als Trenner geführt.
Neu in 2.0: Erkennen verschobener/umbenannter Dateien und Ordner (move/movedir).
Modi:
  backup  – Einweg: neue + geänderte Dateien kopieren, im Ziel nie löschen
  mirror  – Einweg: Ziel wird exaktes Abbild der Quelle (inkl. Löschen)
  twoway  – Zwei-Wege: Änderungen und Löschungen beider Seiten übernehmen
"""
import fnmatch
import hashlib
import os
import shutil
import stat
import sys
import time
from dataclasses import dataclass, field

TIME_TOL = 2.0                       # FAT/exFAT speichern nur 2-s-Raster
ARCHIVE_DIR = "_SyncWerk_Archiv"
TMP_SUFFIX = ".swtmp"
ALWAYS_EXCLUDE = [ARCHIVE_DIR, "*" + TMP_SUFFIX]
CHUNK = 1024 * 1024
IS_WIN = sys.platform.startswith("win")

# Statusfarben (Schlüssel, die die Oberfläche einfärbt)
GREEN, BLUE, YELLOW, RED, GREY = "green", "blue", "yellow", "red", "grey"
PRIORITY = {RED: 4, YELLOW: 3, BLUE: 2, GREEN: 1, GREY: 0}


class Cancelled(Exception):
    pass


@dataclass
class Entry:
    size: int
    mtime: float
    is_dir: bool


@dataclass
class Action:
    kind: str            # copy | delete | mkdir | rmdir | conflict | move | movedir
    rel: str
    side: str            # copy: Quellseite; sonst: betroffene Seite ('L'/'R')
    size: int = 0
    reason: str = ""
    color: str = BLUE
    result: str = ""     # "", "ok" oder Fehlermeldung
    src_rel: str = ""    # move/movedir: bisheriger Pfad auf derselben Seite

    @property
    def target_side(self):
        if self.kind == "copy":
            return "R" if self.side == "L" else "L"
        return self.side

    def label(self):
        arrow = "→" if self.side == "L" else "←"
        return {
            "copy": f"{arrow} kopieren",
            "mkdir": f"{'→' if self.side == 'R' else '←'} Ordner anlegen",
            "delete": f"✕ löschen ({'links' if self.side == 'L' else 'rechts'})",
            "rmdir": f"✕ Ordner löschen ({'links' if self.side == 'L' else 'rechts'})",
            "conflict": "⚠ Konflikt",
            "move": f"↪ umbenennen ({'links' if self.side == 'L' else 'rechts'})",
            "movedir": f"↪ Ordner umbenennen ({'links' if self.side == 'L' else 'rechts'})",
        }.get(self.kind, self.kind)


@dataclass
class Options:
    mode: str = "backup"
    direction: str = "LR"
    compare: str = "fast"
    archive: bool = True
    conflict: str = "newer"
    ignore_dst: bool = True
    excludes: list = field(default_factory=list)
    detect_moves: bool = True
    archive_days: int = 90     # 0 = nie automatisch löschen
    archive_keep: int = 5      # max. Versionen je Datei, 0 = unbegrenzt


# ====================================================================== Hilfen
LONG_PATH = 240     # erst ab dieser Länge das Präfix \\?\ verwenden


def lp(path: str) -> str:
    """Windows: Präfix \\\\?\\ nur für wirklich lange Pfade.
    Seit 2.2: kurze Pfade bleiben unverändert – manche Laufwerke (pCloud Drive, WebDAV/Nextcloud,
    einige NAS-Treiber) lehnen das Präfix mit „Invalid argument“ ab."""
    if not IS_WIN:
        return path
    p = os.path.abspath(path)
    if p.startswith("\\\\?\\") or len(p) < LONG_PATH:
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p


# Bekannte Windows-Fehlercodes mit verständlichem Hinweis
WIN_HINTS = {
    2: "Datei nicht gefunden – wurde sie während der Synchronisation verschoben oder gelöscht?",
    3: "Ordner nicht gefunden – Laufwerk getrennt?",
    5: "Zugriff verweigert – Rechte fehlen oder Datei ist schreibgeschützt.",
    32: "Datei wird von einem anderen Programm benutzt – Programm (z. B. N1MM) schließen und erneut versuchen.",
    33: "Datei ist von einem anderen Programm gesperrt.",
    53: "Netzwerkpfad nicht erreichbar.",
    87: "Das Laufwerk lehnt den Pfad oder die Aktion ab (virtuelles Laufwerk / Cloud-Laufwerk?).",
    112: "Zu wenig Speicherplatz auf dem Ziel.",
    123: "Dateiname ist auf dem Ziel-Laufwerk nicht erlaubt (Sonderzeichen, Leerzeichen/Punkt am Ende).",
    206: "Pfad oder Dateiname zu lang für das Ziel.",
    223: "Datei zu groß für das Dateisystem (FAT32: max. 4 GB).",
    362: "Cloud-Datei: der Sync-Client (OneDrive/pCloud/Nextcloud) läuft nicht.",
    389: "Cloud-Datei: der Sync-Client ist nicht erreichbar.",
    395: "Cloud-Datei: Zugriff durch den Sync-Client verweigert.",
    396: "Cloud-Datei: der Sync-Client hat die Anfrage abgelehnt.",
    665: "Datei zu groß für das Dateisystem.",
    1117: "E/A-Gerätefehler – Kabel/Laufwerk prüfen.",
    1920: "Datei kann vom System nicht gelesen werden (z. B. nur online verfügbare Cloud-Datei).",
    4390: "Cloud-Datei: Datei ist nur online vorhanden und konnte nicht geladen werden.",
}


def win_error_detail(path: str, write: bool = False) -> str:
    """Ermittelt die echte Windows-Ursache, wenn Python nur „Invalid argument“ meldet."""
    if not IS_WIN or not path:
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        access = 0x40000000 if write else 0x80000000             # GENERIC_WRITE / GENERIC_READ
        disp = 2 if write else 3                                  # CREATE_ALWAYS / OPEN_EXISTING
        h = k32.CreateFileW(path, access, 7, None, disp, 0x80, None)
        if h in (None, wintypes.HANDLE(-1).value):
            code = ctypes.get_last_error()
            msg = ctypes.FormatError(code).strip()
            hint = WIN_HINTS.get(code, "")
            return f"Windows-Fehler {code}: {msg}" + (f" → {hint}" if hint else "")
        k32.CloseHandle(h)
        if write:
            k32.DeleteFileW(path)
        return "Windows meldet bei erneutem Test keinen Fehler (evtl. nur kurzzeitig gestört)."
    except Exception:  # noqa: BLE001
        return ""


class StepError(OSError):
    """Fehler mit Angabe, in welchem Schritt und bei welchem Pfad er auftrat."""
    def __init__(self, err: OSError, step: str, path: str, write: bool = False):
        super().__init__(err.errno, err.strerror or str(err))
        self.step, self.path, self.orig = step, path, err
        code = getattr(err, "winerror", None)
        if code:
            hint = WIN_HINTS.get(code, "")
            self.detail = (f"Windows-Fehler {code}" + (f" → {hint}" if hint else ""))
        elif err.errno == 22 or not err.strerror:
            self.detail = win_error_detail(path, write)
        else:
            self.detail = ""

    @property
    def reason(self):
        base = self.orig.strerror or str(self.orig)
        return f"{base} – beim Schritt „{self.step}“" + (f". {self.detail}" if self.detail else "")


def join(root: str, rel: str) -> str:
    return os.path.join(root, *rel.split("/")) if rel else root


def parent_of(rel: str) -> str:
    return rel.rsplit("/", 1)[0] if "/" in rel else ""


def parse_excludes(text: str) -> list:
    parts = text.replace("\n", ";").split(";")
    return [p.strip() for p in parts if p.strip()]


def is_excluded(name: str, patterns) -> bool:
    n = name.lower()
    return any(fnmatch.fnmatch(n, p.lower()) for p in patterns)


def fmt_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024
    return str(n)


def fmt_time(t: float) -> str:
    try:
        return time.strftime("%d.%m.%Y %H:%M", time.localtime(t))
    except (OSError, ValueError, OverflowError):
        return ""


def times_equal(a: float, b: float, ignore_dst: bool) -> bool:
    d = abs(a - b)
    return d <= TIME_TOL or (ignore_dst and abs(d - 3600) <= TIME_TOL)


def _check(cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled()


def file_hash(path: str, cancel=None) -> str:
    h = hashlib.blake2b(digest_size=20)
    with open(lp(path), "rb") as f:
        while True:
            _check(cancel)
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def quick_sig(path: str, part: int = 64 * 1024) -> str:
    """Schnelle Inhalts-Signatur: Größe + erste und letzte 64 KB (kleine Dateien = ganzer Inhalt)."""
    h = hashlib.blake2b(digest_size=16)
    with open(lp(path), "rb") as f:
        size = os.fstat(f.fileno()).st_size
        h.update(str(size).encode())
        h.update(f.read(part))
        if size > 2 * part:
            f.seek(-part, os.SEEK_END)
        h.update(f.read(part))
    return h.hexdigest()


def sanity_check(left: str, right: str) -> list:
    """Liefert Fehlertexte, die eine Synchronisation verhindern."""
    errs = []
    for name, p in (("Links", left), ("Rechts", right)):
        if not p:
            errs.append(f"{name}: Kein Ordner gewählt.")
        elif not os.path.isdir(lp(p)):
            errs.append(f"{name}: Ordner nicht erreichbar – {p}\n"
                        "(Laufwerk angeschlossen? Netzlaufwerk verbunden?)")
    if errs:
        return errs
    a = os.path.normcase(os.path.abspath(left)).rstrip("\\/") + os.sep
    b = os.path.normcase(os.path.abspath(right)).rstrip("\\/") + os.sep
    if a == b:
        errs.append("Links und rechts ist derselbe Ordner.")
    elif a.startswith(b) or b.startswith(a):
        errs.append("Ein Ordner liegt innerhalb des anderen – das würde sich selbst kopieren.")
    return errs


# ====================================================================== Einlesen
def scan(root: str, patterns, progress=None, cancel=None):
    """Liest einen Ordnerbaum ein. Rückgabe: (entries, fehler)."""
    pats = list(patterns) + ALWAYS_EXCLUDE
    entries, errors = {}, []
    stack = [""]
    count = 0
    while stack:
        _check(cancel)
        rel_dir = stack.pop()
        try:
            it = os.scandir(lp(join(root, rel_dir)))
        except OSError as e:
            errors.append(f"{rel_dir or '/'}: {e.strerror or e}")
            continue
        with it:
            for e in it:
                if is_excluded(e.name, pats):
                    continue
                rel = f"{rel_dir}/{e.name}" if rel_dir else e.name
                try:
                    if e.is_symlink() or (hasattr(e, "is_junction") and e.is_junction()):
                        continue
                    if e.is_dir(follow_symlinks=False):
                        entries[rel] = Entry(0, 0.0, True)
                        stack.append(rel)
                    else:
                        st = e.stat(follow_symlinks=False)
                        entries[rel] = Entry(st.st_size, st.st_mtime, False)
                except OSError as ex:
                    errors.append(f"{rel}: {ex.strerror or ex}")
                count += 1
                if progress and count % 400 == 0:
                    progress(count, rel_dir)
    if progress:
        progress(count, "")
    return entries, errors


# ====================================================================== Vergleich
def compare(L: dict, R: dict, lroot: str, rroot: str, opts: Options,
            progress=None, cancel=None) -> dict:
    """Status je Pfad: gleich | nur_links | nur_rechts | links_neuer |
    rechts_neuer | unterschiedlich | typkonflikt"""
    res = {}
    keys = set(L) | set(R)
    to_hash = []
    for rel in keys:
        l, r = L.get(rel), R.get(rel)
        if l and not r:
            res[rel] = "nur_links"
        elif r and not l:
            res[rel] = "nur_rechts"
        elif l.is_dir != r.is_dir:
            res[rel] = "typkonflikt"
        elif l.is_dir:
            res[rel] = "gleich"
        elif l.size != r.size:
            res[rel] = _newer(l, r)
        elif opts.compare == "exact":
            to_hash.append(rel)
        elif times_equal(l.mtime, r.mtime, opts.ignore_dst):
            res[rel] = "gleich"
        else:
            res[rel] = _newer(l, r)
    total = sum(L[r].size for r in to_hash) or 1
    done = 0
    for rel in to_hash:
        _check(cancel)
        try:
            same = file_hash(join(lroot, rel), cancel) == file_hash(join(rroot, rel), cancel)
        except OSError:
            same = False
        if same:
            res[rel] = "gleich"
        elif times_equal(L[rel].mtime, R[rel].mtime, opts.ignore_dst):
            res[rel] = "unterschiedlich"
        else:
            res[rel] = _newer(L[rel], R[rel])
        done += L[rel].size
        if progress:
            progress(done, total, rel)
    return res


def _newer(l: Entry, r: Entry) -> str:
    return "links_neuer" if l.mtime > r.mtime else "rechts_neuer"


# ====================================================================== Planung
def _changed(cur: Entry, rec, ignore_dst) -> bool:
    if not rec:
        return True
    return cur.size != rec[0] or not times_equal(cur.mtime, rec[1], ignore_dst)


def plan(L: dict, R: dict, cmp: dict, opts: Options, state: dict = None, roots=None) -> list:
    acts = _plan_base(L, R, cmp, opts, state)
    if opts.detect_moves and opts.mode != "backup":
        acts = detect_moves(acts, L, R, opts, roots)
    return acts


def _plan_base(L, R, cmp, opts, state):
    acts = []
    if opts.mode in ("backup", "mirror"):
        src, dst = ("L", "R") if opts.direction == "LR" else ("R", "L")
        S, D = (L, R) if src == "L" else (R, L)
        only_src = "nur_links" if src == "L" else "nur_rechts"
        only_dst = "nur_rechts" if src == "L" else "nur_links"
        src_newer = "links_neuer" if src == "L" else "rechts_neuer"
        for rel in sorted(cmp):
            st = cmp[rel]
            if st == "gleich":
                continue
            if st == "typkonflikt":
                acts.append(Action("conflict", rel, src, reason="Datei und Ordner gleichen Namens", color=RED))
            elif st == only_src:
                e = S[rel]
                if e.is_dir:
                    acts.append(Action("mkdir", rel, dst, reason="Ordner fehlt im Ziel", color=BLUE))
                else:
                    acts.append(Action("copy", rel, src, e.size, "neu", BLUE))
            elif st == only_dst:
                if opts.mode == "mirror":
                    e = D[rel]
                    acts.append(Action("rmdir" if e.is_dir else "delete", rel, dst, e.size,
                                       "nicht mehr in der Quelle", RED))
            else:
                reason = "Quelle ist neuer" if st == src_newer else (
                    "Inhalt verschieden" if st == "unterschiedlich" else "Ziel ist neuer – wird überschrieben")
                acts.append(Action("copy", rel, src, S[rel].size, reason, YELLOW))
    else:
        acts = _plan_twoway(L, R, cmp, opts, state or {})
    return acts


def _plan_twoway(L, R, cmp, opts, state):
    acts = []
    dst_of = {"L": "R", "R": "L"}
    for rel in sorted(cmp):
        st = cmp[rel]
        rec = state.get(rel)
        if st == "gleich":
            continue
        if st == "typkonflikt":
            acts.append(Action("conflict", rel, "L", reason="Datei und Ordner gleichen Namens", color=RED))
            continue
        if st in ("nur_links", "nur_rechts"):
            side = "L" if st == "nur_links" else "R"
            e = (L if side == "L" else R)[rel]
            if rec is None:
                if e.is_dir:
                    acts.append(Action("mkdir", rel, dst_of[side], reason="neuer Ordner", color=BLUE))
                else:
                    acts.append(Action("copy", rel, side, e.size, "neu", BLUE))
            else:
                other = "rechts" if side == "L" else "links"
                if e.is_dir:
                    acts.append(Action("rmdir", rel, side, reason=f"wurde {other} gelöscht", color=RED))
                elif _changed(e, rec.get(side.lower()), opts.ignore_dst):
                    acts.append(Action("copy", rel, side, e.size,
                                       f"{other} gelöscht, hier aber geändert – wird wiederhergestellt", YELLOW))
                else:
                    acts.append(Action("delete", rel, side, e.size, f"wurde {other} gelöscht", RED))
            continue
        # beide Seiten haben die Datei, Inhalt unterschiedlich
        l, r = L[rel], R[rel]
        if rec:
            lch = _changed(l, rec.get("l"), opts.ignore_dst)
            rch = _changed(r, rec.get("r"), opts.ignore_dst)
            if lch and not rch:
                acts.append(Action("copy", rel, "L", l.size, "links geändert", YELLOW))
                continue
            if rch and not lch:
                acts.append(Action("copy", rel, "R", r.size, "rechts geändert", YELLOW))
                continue
            both = True
        else:
            both = False
        if st == "unterschiedlich":
            acts.append(Action("conflict", rel, "L", reason="gleiches Datum, anderer Inhalt", color=RED))
        elif both and opts.conflict == "skip":
            acts.append(Action("conflict", rel, "L", reason="beide Seiten geändert – übersprungen", color=RED))
        else:
            side = "L" if st == "links_neuer" else "R"
            e = l if side == "L" else r
            if both:
                acts.append(Action("copy", rel, side, e.size,
                                   "Konflikt: beide geändert – neuere gewinnt", RED))
            else:
                acts.append(Action("copy", rel, side, e.size, "neuere Version gewinnt", YELLOW))
    # Ordner, die gelöscht werden sollen, aber neue Inhalte bekommen -> anlegen
    copies = [a for a in acts if a.kind in ("copy", "mkdir")]
    for a in acts:
        if a.kind == "rmdir":
            pre = a.rel + "/"
            if any(c.rel.startswith(pre) for c in copies):
                a.kind, a.side = "mkdir", dst_of[a.side]
                a.reason, a.color = "enthält neue Dateien", BLUE
    return acts


# ====================================================================== Verschieben erkennen
def detect_moves(acts, L, R, opts, roots=None):
    """Ersetzt Paare aus 'neu kopieren' + 'löschen' (gleiche Größe und gleiches
    Datum auf der Zielseite) durch ein schnelles Umbenennen auf der Zielseite.
    Ganze umbenannte Ordner werden zu einer einzigen Ordner-Umbenennung."""
    sides = {"L": L, "R": R}
    roots = {"L": roots[0], "R": roots[1]} if roots else None
    dels = {}
    for a in acts:
        if a.kind == "delete":
            e = sides[a.side].get(a.rel)
            if e and e.size > 0:
                dels.setdefault((a.side, e.size), []).append(a)
    if not dels:
        return acts
    used = set()
    for a in acts:
        if a.kind != "copy" or a.color != BLUE:
            continue
        t = a.target_side
        se = sides[a.side][a.rel]
        cands = [d for d in dels.get((t, se.size), [])
                 if id(d) not in used and times_equal(sides[t][d.rel].mtime, se.mtime, opts.ignore_dst)]
        if not cands:
            continue
        base = a.rel.rsplit("/", 1)[-1].lower()
        cands.sort(key=lambda d: d.rel.rsplit("/", 1)[-1].lower() != base)
        d = None
        for c in cands:
            if roots:
                # Inhalt absichern: kleine Dateien komplett, große über Anfang + Ende
                hasher = file_hash if opts.compare == "exact" else quick_sig
                try:
                    if hasher(join(roots[a.side], a.rel)) != hasher(join(roots[t], c.rel)):
                        continue
                except OSError:
                    continue
            elif c.rel.rsplit("/", 1)[-1].lower() != base:
                continue            # ohne Inhaltsprüfung nur bei gleichem Dateinamen
            d = c
            break
        if d is None:
            continue
        used.add(id(d))
        a.kind, a.side, a.src_rel = "move", t, d.rel
        a.reason, a.color = f"verschoben/umbenannt – vorher: {d.rel}", YELLOW
    acts = [a for a in acts if id(a) not in used]
    return _merge_dir_moves(acts, sides)


def _merge_dir_moves(acts, sides):
    moves = [a for a in acts if a.kind == "move"]
    if not moves:
        return acts
    rmdirs = {(a.side, a.rel) for a in acts if a.kind == "rmdir"}
    mkdirs = {(a.side, a.rel) for a in acts if a.kind == "mkdir"}
    pairs = {}
    for m in moves:
        o, n = parent_of(m.src_rel), parent_of(m.rel)
        while o and n:
            if (m.side, o) in rmdirs and (m.side, n) in mkdirs and m.src_rel[len(o):] == m.rel[len(n):]:
                pairs.setdefault((m.side, o, n), []).append(m)
            o, n = parent_of(o), parent_of(n)
    if not pairs:
        return acts
    # Anzahl Dateien unter jedem Ordner je Seite
    counts = {"L": {}, "R": {}}
    for side in ("L", "R"):
        cnt = counts[side]
        for rel, e in sides[side].items():
            if not e.is_dir:
                p = parent_of(rel)
                while p:
                    cnt[p] = cnt.get(p, 0) + 1
                    p = parent_of(p)
    chosen = []
    for (side, o, n), ms in sorted(pairs.items(), key=lambda kv: kv[0][1].count("/")):
        if any(side == cs and (o == co or o.startswith(co + "/")) for cs, co, _ in chosen):
            continue
        if len(ms) == counts[side].get(o, 0):
            chosen.append((side, o, n))
    if not chosen:
        return acts
    out = []
    for a in acts:
        drop = False
        for side, o, n in chosen:
            if a.side != side:
                continue
            if a.kind == "move" and (a.src_rel.startswith(o + "/")):
                drop = True
            elif a.kind == "rmdir" and (a.rel == o or a.rel.startswith(o + "/")):
                drop = True
            elif a.kind == "mkdir" and (a.rel == n or a.rel.startswith(n + "/")):
                drop = True
        if not drop:
            out.append(a)
    for side, o, n in chosen:
        out.append(Action("movedir", n, side, 0, f"Ordner verschoben/umbenannt – vorher: {o}", YELLOW, src_rel=o))
    return out


def build_state(L: dict, R: dict, cmp: dict, old: dict) -> dict:
    """Zustand nach dem Abgleich für die nächste Zwei-Wege-Synchronisation."""
    new = {}
    for rel, st in cmp.items():
        l, r = L.get(rel), R.get(rel)
        if st == "gleich" and l and r:
            new[rel] = {"d": 1} if l.is_dir else {"l": [l.size, l.mtime], "r": [r.size, r.mtime]}
        elif rel in old and l and r:
            new[rel] = old[rel]          # ungelöster Konflikt: alten Stand behalten
    return new


def status_map(L, R, cmp, acts):
    """Farbe und Aktionstext je Pfad (für die Explorer-Ansicht)."""
    m = {}
    for rel, st in cmp.items():
        if st == "gleich":
            m[rel] = (GREEN, "=")
        elif st in ("nur_links", "nur_rechts"):
            m[rel] = (BLUE, "nur " + ("links" if st == "nur_links" else "rechts"))
        elif st == "typkonflikt":
            m[rel] = (RED, "⚠")
        else:
            m[rel] = (YELLOW, "≠")
    for a in acts:
        m[a.rel] = (a.color, a.label())
        if a.kind in ("move", "movedir"):
            m[a.src_rel] = (YELLOW, "↪ wird umbenannt")
    moved_dirs = [(a.src_rel + "/", a.rel + "/") for a in acts if a.kind == "movedir"]
    if moved_dirs:
        for rel in cmp:
            for o, n in moved_dirs:
                if rel.startswith(o) or rel.startswith(n):
                    m[rel] = (YELLOW, "↪ im umbenannten Ordner")
    # Ordner erben die "schlimmste" Farbe ihres Inhalts
    agg = {}
    for rel, (col, _) in m.items():
        p = parent_of(rel)
        while p:
            if PRIORITY[col] > PRIORITY.get(agg.get(p, GREY), 0):
                agg[p] = col
            p = parent_of(p)
    for p, col in agg.items():
        old = m.get(p, (GREEN, ""))
        if PRIORITY[col] > PRIORITY[old[0]]:
            m[p] = (col, old[1] if old[1] not in ("=", "") else "Inhalt abweichend")
    return m


def summarize(acts):
    s = {"copy_new": 0, "copy_upd": 0, "delete": 0, "mkdir": 0, "conflict": 0, "move": 0, "bytes": 0}
    for a in acts:
        if a.kind == "copy":
            s["copy_new" if a.color == BLUE else "copy_upd"] += 1
            s["bytes"] += a.size
        elif a.kind in ("delete", "rmdir"):
            s["delete"] += 1
        elif a.kind == "mkdir":
            s["mkdir"] += 1
        elif a.kind == "conflict":
            s["conflict"] += 1
        elif a.kind in ("move", "movedir"):
            s["move"] += 1
    return s


def space_warnings(acts, lroot, rroot) -> list:
    need = {"L": 0, "R": 0}
    for a in acts:
        if a.kind == "copy":
            need[a.target_side] += a.size
    warns = []
    for side, root in (("L", lroot), ("R", rroot)):
        if need[side]:
            try:
                free = shutil.disk_usage(root).free
                if free < need[side]:
                    warns.append(f"{'Links' if side == 'L' else 'Rechts'}: zu wenig Speicher – "
                                 f"benötigt {fmt_size(need[side])}, frei {fmt_size(free)}")
            except OSError:
                pass
    return warns


# ====================================================================== Ausführung
def _make_writable(p):
    try:
        os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


class Executor:
    def __init__(self, lroot, rroot, opts: Options, progress=None, log=None, cancel=None):
        self.roots = {"L": lroot, "R": rroot}
        self.opts = opts
        self.progress = progress
        self.log = log or (lambda msg, col=None: None)
        self.cancel = cancel
        self.stamp = time.strftime("%Y-%m-%d_%H%M%S")
        self.done_bytes = 0
        self.total_bytes = 0
        self.ok = 0
        self.failed = 0
        self.reasons = {}
        self.ts_failed = 0

    def run(self, acts):
        order = {"movedir": 0, "mkdir": 1, "move": 2, "copy": 3, "delete": 4, "rmdir": 5}
        todo = [a for a in acts if a.kind in order]
        todo.sort(key=lambda a: (order[a.kind],
                                 -a.rel.count("/") if a.kind == "rmdir" else a.rel.count("/"),
                                 a.rel))
        self.total_bytes = sum(a.size for a in todo if a.kind == "copy") or 1
        n = len(todo)
        for i, a in enumerate(todo, 1):
            _check(self.cancel)
            try:
                getattr(self, "_" + a.kind)(a)
                a.result = "ok"
                self.ok += 1
            except Cancelled:
                raise
            except Exception as e:  # noqa: BLE001 – jede Datei einzeln absichern
                a.result = e.reason if isinstance(e, StepError) else (getattr(e, "strerror", None) or str(e))
                self.failed += 1
                self.reasons[a.result] = self.reasons.get(a.result, 0) + 1
                if self.reasons[a.result] <= 3:
                    self.log(f"FEHLER  {a.label()}  {a.rel}: {a.result}", RED)
                    if isinstance(e, StepError) and self.reasons[a.result] == 1:
                        self.log(f"        Pfad: {e.path}", RED)
                elif self.reasons[a.result] == 4:
                    self.log("        … weitere Dateien mit demselben Fehler werden am Ende zusammengefasst", RED)
            if self.progress:
                self.progress(self.done_bytes, self.total_bytes, i, n, a.rel)
        self._summary()
        return self.ok, self.failed

    def _summary(self):
        for reason, n in sorted(self.reasons.items(), key=lambda kv: -kv[1]):
            if n > 1:
                self.log(f"ZUSAMMENFASSUNG: {n} × {reason}", RED)
        if self.ts_failed:
            self.log(f"Hinweis: Bei {self.ts_failed} Datei(en) konnte das Änderungsdatum im Ziel nicht gesetzt "
                     "werden (vom Ziel-Laufwerk nicht unterstützt). Diese können beim nächsten Vergleich erneut "
                     "als geändert erscheinen – dann „±1 h ignorieren“ bzw. Vergleich „Genau“ nutzen.", YELLOW)

    # --- einzelne Aktionen
    def _path(self, side, rel):
        return lp(join(self.roots[side], rel))

    def _to_archive(self, side, rel):
        src = self._path(side, rel)
        dst = lp(join(self.roots[side], f"{ARCHIVE_DIR}/{self.stamp}/{rel}"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            os.replace(src, dst)
        except OSError:
            _make_writable(src)
            shutil.move(src, dst)

    def _move(self, a):
        src = self._path(a.side, a.src_rel)
        dst = self._path(a.side, a.rel)
        if os.path.exists(dst):
            raise OSError(f"Ziel existiert bereits: {a.rel}")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.rename(src, dst)
        self.log(f"↪ umbenannt ({'links' if a.side == 'L' else 'rechts'}): {a.src_rel}  →  {a.rel}", YELLOW)

    def _movedir(self, a):
        self._move(a)

    def _mkdir(self, a):
        os.makedirs(self._path(a.side, a.rel), exist_ok=True)
        self.log(f"Ordner angelegt ({'links' if a.side == 'L' else 'rechts'}): {a.rel}", BLUE)

    def _copy(self, a):
        src = self._path(a.side, a.rel)
        dst = self._path(a.target_side, a.rel)
        tmp = dst + TMP_SUFFIX

        def step(name, path, fn, write=False):
            try:
                return fn()
            except Cancelled:
                raise
            except OSError as e:
                raise StepError(e, name, path, write) from e

        step("Zielordner anlegen", os.path.dirname(dst), lambda: os.makedirs(os.path.dirname(dst), exist_ok=True))
        try:
            fi = step("Quelldatei öffnen", src, lambda: open(src, "rb"))
            try:
                fo = step("Zieldatei anlegen", tmp, lambda: open(tmp, "wb"), write=True)
                try:
                    while True:
                        _check(self.cancel)
                        b = step("Quelldatei lesen", src, lambda: fi.read(CHUNK))
                        if not b:
                            break
                        step("Zieldatei schreiben", tmp, lambda: fo.write(b), write=True)
                        self.done_bytes += len(b)
                        if self.progress:
                            self.progress(self.done_bytes, self.total_bytes, None, None, a.rel)
                finally:
                    fo.close()
            finally:
                fi.close()
            # Änderungsdatum übernehmen – Fehler hier sind nicht fatal
            try:
                shutil.copystat(src, tmp)
            except OSError:
                try:
                    st = os.stat(src)
                    os.utime(tmp, (st.st_mtime, st.st_mtime))
                except OSError:
                    self.ts_failed += 1
            if os.path.getsize(tmp) != os.path.getsize(src):
                raise StepError(OSError(0, "Größe nach dem Kopieren stimmt nicht – Datei wurde während des "
                                           "Kopierens geändert?"), "Prüfen", dst)
            if os.path.exists(dst):
                if self.opts.archive:
                    step("alte Version ins Archiv", dst, lambda: self._to_archive(a.target_side, a.rel))
                else:
                    _make_writable(dst)
            step("Zieldatei ersetzen", dst, lambda: os.replace(tmp, dst))
        except BaseException:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            raise
        col = BLUE if a.color == BLUE else YELLOW
        self.log(f"{'→' if a.side == 'L' else '←'} {a.rel}  ({fmt_size(a.size)}, {a.reason})", col)

    def _delete(self, a):
        p = self._path(a.side, a.rel)
        if self.opts.archive:
            self._to_archive(a.side, a.rel)
        else:
            try:
                os.remove(p)
            except PermissionError:
                _make_writable(p)
                os.remove(p)
        self.log(f"✕ gelöscht ({'links' if a.side == 'L' else 'rechts'}): {a.rel}"
                 + ("  → Archiv" if self.opts.archive else ""), RED)

    def _rmdir(self, a):
        p = self._path(a.side, a.rel)
        try:
            os.rmdir(p)
            self.log(f"✕ Ordner entfernt ({'links' if a.side == 'L' else 'rechts'}): {a.rel}", RED)
        except FileNotFoundError:
            pass
        except OSError:
            self.log(f"Ordner nicht leer (ausgeschlossene Dateien) – bleibt erhalten: {a.rel}", YELLOW)
