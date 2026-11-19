"""Ablage von Einstellungen, Profilen, Sync-Zuständen und Protokollen.

Alles liegt unter %APPDATA%\\SyncWerk (Windows) bzw. ~/.syncwerk.
"""
import hashlib
import json
import os
import sys
import time


def app_dir() -> str:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = os.path.join(base, "SyncWerk")
    else:
        path = os.path.join(os.path.expanduser("~"), ".syncwerk")
    os.makedirs(path, exist_ok=True)
    return path


def _sub(name: str) -> str:
    p = os.path.join(app_dir(), name)
    os.makedirs(p, exist_ok=True)
    return p


def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ---------------------------------------------------------------- Profile
DEFAULT_PROFILE = {
    "left": "",
    "right": "",
    "mode": "backup",          # backup | mirror | twoway
    "direction": "LR",         # LR | RL (nur Backup/Spiegeln)
    "compare": "fast",         # fast | exact
    "archive": True,           # gelöschte/überschriebene Dateien archivieren
    "conflict": "newer",       # newer | skip
    "ignore_dst": True,        # ±1 h Abweichung (FAT/exFAT) ignorieren
    "excludes": "Thumbs.db; desktop.ini; ~$*; *.tmp; .DS_Store; "
                "$RECYCLE.BIN; System Volume Information",
    "detect_moves": True,      # verschobene/umbenannte Dateien erkennen
    "archive_days": 90,        # Archiv: Versionen älter als N Tage löschen (0 = nie)
    "archive_keep": 5,         # Archiv: max. Versionen je Datei (0 = unbegrenzt)
    # USB-Auslöser (Seite, deren Laufwerk per Seriennummer erkannt wird)
    "usb_serial": "", "usb_label": "", "usb_side": "", "usb_rel": "", "usb_auto": False,
}


def profiles_path():
    return os.path.join(app_dir(), "profile.json")


def load_profiles() -> dict:
    data = _read_json(profiles_path(), {})
    return data if isinstance(data, dict) else {}


def save_profiles(profiles: dict):
    _write_json(profiles_path(), profiles)


def jobs_path():
    return os.path.join(app_dir(), "sammelauftraege.json")


def load_jobs() -> dict:
    """Sammelaufträge: {Name: [Profilname, ...]}"""
    data = _read_json(jobs_path(), {})
    return data if isinstance(data, dict) else {}


def save_jobs(jobs: dict):
    _write_json(jobs_path(), jobs)


def load_settings() -> dict:
    return _read_json(os.path.join(app_dir(), "einstellungen.json"), {})


def save_settings(settings: dict):
    _write_json(os.path.join(app_dir(), "einstellungen.json"), settings)


# ---------------------------------------------------------------- Zustand (Zwei-Wege)
def _norm(p: str) -> str:
    p = os.path.normpath(os.path.abspath(p))
    return p.lower() if sys.platform.startswith("win") else p


def state_file(left: str, right: str) -> str:
    key = hashlib.sha1((_norm(left) + "|" + _norm(right)).encode("utf-8")).hexdigest()[:20]
    return os.path.join(_sub("zustand"), key + ".json")


def load_state(left: str, right: str) -> dict:
    data = _read_json(state_file(left, right), {})
    return data.get("files", {}) if isinstance(data, dict) else {}


def save_state(left: str, right: str, files: dict):
    _write_json(state_file(left, right), {
        "left": left, "right": right,
        "saved": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": files,
    })


# ---------------------------------------------------------------- Protokolle
def log_path() -> str:
    return os.path.join(_sub("protokolle"), time.strftime("%Y-%m-%d") + ".log")


def write_log(lines):
    try:
        with open(log_path(), "a", encoding="utf-8") as f:
            for line in lines:
                f.write(line.rstrip("\n") + "\n")
    except OSError:
        pass
