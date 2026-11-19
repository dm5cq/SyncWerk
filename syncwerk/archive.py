"""Archiv: alte Versionen auflisten, aufräumen und wiederherstellen.

Aufbau:  <Ordner>/_SyncWerk_Archiv/<JJJJ-MM-TT_hhmmss>/<relativer Pfad>
"""
import os
import shutil
import time
from dataclasses import dataclass

from . import engine as E

STAMP_FMT = "%Y-%m-%d_%H%M%S"


@dataclass
class Version:
    root: str          # synchronisierter Ordner (linke oder rechte Seite)
    stamp: str         # Zeitstempel-Ordner
    rel: str           # ursprünglicher relativer Pfad
    size: int
    when: float        # Zeitpunkt der Archivierung

    @property
    def path(self):
        return E.join(self.root, f"{E.ARCHIVE_DIR}/{self.stamp}/{self.rel}")

    @property
    def original(self):
        return E.join(self.root, self.rel)


def _stamp_time(stamp):
    try:
        return time.mktime(time.strptime(stamp, STAMP_FMT))
    except ValueError:
        return None


def list_versions(root: str) -> list:
    base = E.join(root, E.ARCHIVE_DIR)
    out = []
    if not root or not os.path.isdir(E.lp(base)):
        return out
    for stamp in os.listdir(E.lp(base)):
        when = _stamp_time(stamp)
        sdir = os.path.join(base, stamp)
        if when is None or not os.path.isdir(E.lp(sdir)):
            continue
        for d, _, files in os.walk(E.lp(sdir)):
            for f in files:
                full = os.path.join(d, f)
                rel = os.path.relpath(full, E.lp(sdir)).replace(os.sep, "/")
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = 0
                out.append(Version(root, stamp, rel, size, when))
    out.sort(key=lambda v: (v.rel.lower(), -v.when))
    return out


def cleanup(root: str, days: int = 90, keep: int = 5):
    """Löscht Versionen älter als `days` Tage und mehr als `keep` Versionen je Datei.
    Rückgabe: (Anzahl gelöschter Dateien, freigegebene Bytes)."""
    versions = list_versions(root)
    if not versions:
        return 0, 0
    remove = set()
    if days and days > 0:
        cutoff = time.time() - days * 86400
        remove |= {id(v) for v in versions if v.when < cutoff}
    if keep and keep > 0:
        by_rel = {}
        for v in versions:
            by_rel.setdefault(v.rel, []).append(v)
        for vs in by_rel.values():
            vs.sort(key=lambda v: -v.when)
            remove |= {id(v) for v in vs[keep:]}
    n = freed = 0
    for v in versions:
        if id(v) in remove:
            try:
                p = E.lp(v.path)
                try:
                    os.remove(p)
                except PermissionError:
                    os.chmod(p, 0o666)
                    os.remove(p)
                n += 1
                freed += v.size
            except OSError:
                pass
    _remove_empty(E.join(root, E.ARCHIVE_DIR))
    return n, freed


def _remove_empty(base):
    b = E.lp(base)
    if not os.path.isdir(b):
        return
    for d, _, _ in sorted(os.walk(b), key=lambda x: -len(x[0])):
        try:
            if d != b:
                os.rmdir(d)
        except OSError:
            pass
    try:
        os.rmdir(b)
    except OSError:
        pass


def restore(v: Version, target: str = None) -> str:
    """Stellt eine Version wieder her. Ohne `target` an den ursprünglichen Ort –
    eine dort vorhandene aktuelle Datei wird vorher selbst ins Archiv gelegt.
    Die archivierte Version bleibt erhalten. Rückgabe: Zielpfad."""
    dst = target or v.original
    dst_l = E.lp(dst)
    os.makedirs(os.path.dirname(dst_l), exist_ok=True)
    if os.path.exists(dst_l) and target is None:
        stamp = time.strftime(STAMP_FMT)
        keep = E.lp(E.join(v.root, f"{E.ARCHIVE_DIR}/{stamp}/{v.rel}"))
        os.makedirs(os.path.dirname(keep), exist_ok=True)
        if os.path.exists(keep):
            os.remove(keep)
        os.replace(dst_l, keep)
    tmp = dst_l + E.TMP_SUFFIX
    shutil.copy2(E.lp(v.path), tmp)
    os.replace(tmp, dst_l)
    return dst
