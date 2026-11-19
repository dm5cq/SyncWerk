"""Hintergrund-Wächter: startet Profile, sobald eine bestimmte USB-Platte angesteckt wird.

Erkennung über die Volume-Seriennummer (nicht über den Laufwerksbuchstaben).
Läuft unsichtbar als  SyncWerk.exe --waechter  und wird über eine kleine VBS-Datei im
Autostart-Ordner des Benutzers gestartet (keine Administratorrechte nötig).
"""
import os
import subprocess
import sys
import time

from . import auto
from . import drives
from . import notify
from . import storage

IS_WIN = sys.platform.startswith("win")
MUTEX = "Local\\SyncWerkWaechter"
POLL = 3            # Sekunden zwischen zwei Prüfungen
SETTLE = 5          # Wartezeit nach dem Anstecken, bis Windows das Laufwerk bereit hat
COOLDOWN = 600      # dasselbe Profil frühestens nach 10 Minuten erneut


def stop_file():
    return os.path.join(storage.app_dir(), "waechter.stop")


def startup_file():
    base = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
                        "SyncWerk-Waechter.vbs")


def launch_args():
    if getattr(sys, "frozen", False):
        return [sys.executable, "--waechter"]
    pyw = sys.executable.replace("python.exe", "pythonw.exe")
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SyncWerk.py")
    return [pyw, script, "--waechter"]


def is_running() -> bool:
    if not IS_WIN:
        return False
    import ctypes
    h = ctypes.windll.kernel32.OpenMutexW(0x00100000, False, MUTEX)
    if h:
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    return False


def is_installed() -> bool:
    return os.path.exists(startup_file())


def install():
    """Autostart einrichten und Wächter sofort starten."""
    args = launch_args()
    cmd = " ".join(f'""{a}""' if " " in a or "\\" in a else a for a in args)
    os.makedirs(os.path.dirname(startup_file()), exist_ok=True)
    with open(startup_file(), "w", encoding="utf-16") as f:
        f.write(f'CreateObject("WScript.Shell").Run "{cmd}", 0, False\r\n')
    start()


def start():
    if is_running():
        return
    try:
        os.remove(stop_file())
    except OSError:
        pass
    subprocess.Popen(launch_args(), creationflags=0x00000008 | 0x08000000 if IS_WIN else 0,
                     close_fds=True)


def uninstall():
    try:
        os.remove(startup_file())
    except OSError:
        pass
    stop()


def stop():
    with open(stop_file(), "w") as f:
        f.write("stop")


def usb_profiles():
    return {n: p for n, p in storage.load_profiles().items() if p.get("usb_auto") and p.get("usb_serial")}


def run():
    """Hauptschleife des Wächters (eigener, unsichtbarer Prozess)."""
    if not IS_WIN:
        return 1
    import ctypes
    k32 = ctypes.windll.kernel32
    handle = k32.CreateMutexW(None, True, MUTEX)
    if k32.GetLastError() == 183:          # läuft bereits
        return 0
    try:
        os.remove(stop_file())
    except OSError:
        pass
    storage.write_log(["WÄCHTER gestartet"])
    known = set(drives.serial_map())
    last = {}
    try:
        while True:
            time.sleep(POLL)
            if os.path.exists(stop_file()):
                os.remove(stop_file())
                break
            current = set(drives.serial_map())
            arrived, known = current - known, current
            if not arrived:
                continue
            for name, p in usb_profiles().items():
                if p["usb_serial"] in arrived and time.time() - last.get(name, 0) > COOLDOWN:
                    last[name] = time.time()
                    label = p.get("usb_label") or p["usb_serial"]
                    notify.toast("SyncWerk", f"„{label}“ erkannt – „{name}“ startet …")
                    time.sleep(SETTLE)
                    auto.run_profile(name, notify_result=True)
    finally:
        storage.write_log(["WÄCHTER beendet"])
        k32.CloseHandle(handle)
    return 0
