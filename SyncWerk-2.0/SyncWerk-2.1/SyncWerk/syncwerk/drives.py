"""Erkennung von Laufwerken: lokal, USB/Wechseldatenträger, Netzwerk, Cloud."""
import os
import string
import sys

IS_WIN = sys.platform.startswith("win")

KIND_ICON = {
    "lokal": "Lokal", "usb": "USB", "netz": "Netz", "cloud": "Cloud", "ordner": "Ordner", "cd": "CD",
}


def _quiet(k32):
    """Keine Windows-Fehlerfenster („Kein Datenträger im Laufwerk“) bei leeren Kartenlesern."""
    try:
        k32.SetErrorMode(0x0001 | 0x8000)   # SEM_FAILCRITICALERRORS | SEM_NOOPENFILEERRORBOX
    except (AttributeError, OSError):
        pass


def _win_drives():
    import ctypes
    k32 = ctypes.windll.kernel32
    _quiet(k32)
    mask = k32.GetLogicalDrives()
    out = []
    for i, letter in enumerate(string.ascii_uppercase):
        if not mask & (1 << i):
            continue
        root = f"{letter}:\\"
        dtype = k32.GetDriveTypeW(root)   # 2=Wechsel, 3=fest, 4=Netz, 5=CD
        label_buf = ctypes.create_unicode_buffer(261)
        fs_buf = ctypes.create_unicode_buffer(261)
        # Netzlaufwerke nicht abfragen: getrennte Freigaben blockieren sonst sekundenlang
        ok = 0 if dtype == 4 else k32.GetVolumeInformationW(root, label_buf, 261, None, None, None, fs_buf, 261)
        label = label_buf.value if ok else ""
        kind = {2: "usb", 3: "lokal", 4: "netz", 5: "cd"}.get(dtype, "lokal")
        low = label.lower()
        if "pcloud" in low or "nextcloud" in low or "onedrive" in low or "google" in low:
            kind = "cloud"
        if kind == "cd" and not ok:
            continue
        text = f"{letter}:  {label}" if label else f"{letter}:"
        if kind == "netz":
            try:
                buf = ctypes.create_unicode_buffer(1024)
                size = ctypes.c_ulong(1024)
                if ctypes.windll.mpr.WNetGetConnectionW(f"{letter}:", buf, ctypes.byref(size)) == 0:
                    text += f"  ({buf.value})"
            except (OSError, AttributeError):
                pass
        out.append((kind, text, root))
    return out


def _cloud_folders():
    """Typische lokale Ordner von Cloud-Clients (Nextcloud, OneDrive, …)."""
    home = os.path.expanduser("~")
    names = ["Nextcloud", "pCloud Drive", "OneDrive", "Dropbox", "Google Drive", "ownCloud",
             "Seafile", "MEGA"]
    out = []
    for n in names:
        p = os.path.join(home, n)
        if os.path.isdir(p):
            out.append(("cloud", n, p))
    for k in ("OneDrive", "OneDriveCommercial"):
        p = os.environ.get(k)
        if p and os.path.isdir(p) and all(p != x[2] for x in out):
            out.append(("cloud", os.path.basename(p), p))
    return out


def list_drives():
    """Liste aus (art, anzeigetext, pfad)."""
    out = []
    if IS_WIN:
        try:
            out += _win_drives()
        except Exception:  # noqa: BLE001
            out += [("lokal", f"{c}:", f"{c}:\\") for c in "CDEFGH" if os.path.exists(f"{c}:\\")]
    else:
        out.append(("lokal", "/", "/"))
        for base in ("/Volumes", "/media", "/mnt", f"/media/{os.environ.get('USER', '')}",
                     f"/run/media/{os.environ.get('USER', '')}"):
            if os.path.isdir(base):
                for n in sorted(os.listdir(base)):
                    p = os.path.join(base, n)
                    if os.path.isdir(p) and not os.path.islink(p):
                        out.append(("usb", n, p))
    home = os.path.expanduser("~")
    out.append(("ordner", "Benutzerordner", home))
    out += _cloud_folders()
    return out


def display(kind, text):
    return f"[{KIND_ICON.get(kind, 'Ordner')}]  {text}"


# ---------------------------------------------------------------- Seriennummern (USB-Auslöser)
def volume_info(path: str):
    """(Seriennummer 'XXXX-XXXX', Laufwerkswurzel, Bezeichnung, Art) für einen Pfad – oder None."""
    if not IS_WIN or not path:
        return None
    import ctypes
    k32 = ctypes.windll.kernel32
    _quiet(k32)
    buf = ctypes.create_unicode_buffer(300)
    if not k32.GetVolumePathNameW(os.path.abspath(path), buf, 300):
        return None
    root = buf.value
    dtype = k32.GetDriveTypeW(root)
    if dtype == 4 or root.startswith("\\\\"):
        return None
    serial = ctypes.c_ulong(0)
    label = ctypes.create_unicode_buffer(261)
    if not k32.GetVolumeInformationW(root, label, 261, ctypes.byref(serial), None, None, None, 0):
        return None
    sn = f"{serial.value >> 16:04X}-{serial.value & 0xFFFF:04X}"
    return sn, root, label.value, {2: "usb"}.get(dtype, "lokal")


def serial_map() -> dict:
    """{Seriennummer: Laufwerkswurzel} aller lokalen/USB-Laufwerke (ohne Netz/CD)."""
    if not IS_WIN:
        return {}
    import ctypes
    k32 = ctypes.windll.kernel32
    mask = k32.GetLogicalDrives()
    out = {}
    for i, letter in enumerate(string.ascii_uppercase):
        if mask & (1 << i):
            root = f"{letter}:\\"
            if k32.GetDriveTypeW(root) in (2, 3):
                info = volume_info(root)
                if info:
                    out[info[0]] = info[1]
    return out
