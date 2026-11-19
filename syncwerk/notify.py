"""Windows-Benachrichtigungen (Toast) ohne Zusatzbibliotheken – über PowerShell/WinRT.

Erfolg: grünes Symbol, Fehler: rotes Symbol + „FEHLER“ im Titel.
"""
import base64
import os
import shutil
import subprocess
import sys

from . import APP_NAME
from . import storage

IS_WIN = sys.platform.startswith("win")
AUMID = "SKaiser.SyncWerk"
PS_AUMID = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe"
NO_WINDOW = 0x08000000


def _asset(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", name)


def _icon(name):
    """Symbol dauerhaft nach %APPDATA% kopieren (der EXE-Temp-Ordner verschwindet)."""
    dst = os.path.join(storage.app_dir(), name)
    if not os.path.exists(dst):
        try:
            shutil.copy(_asset(name), dst)
        except OSError:
            return ""
    return dst


def _register_aumid():
    """Eigenen Absendernamen „SyncWerk“ mit Symbol für Benachrichtigungen registrieren."""
    try:
        import winreg
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{AUMID}")
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        icon = _icon("SyncWerk.png")
        if icon:
            winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, icon)
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


def _esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def toast(title: str, text: str, ok: bool = True) -> bool:
    if not IS_WIN:
        return False
    icon = _icon("ok.png" if ok else "fehler.png")
    img = f'<image placement="appLogoOverride" src="{_esc(icon)}"/>' if icon else ""
    scen = "" if ok else ' scenario="reminder"'
    xml = (f'<toast{scen}><visual><binding template="ToastGeneric">'
           f"<text>{_esc(title)}</text><text>{_esc(text)}</text>{img}"
           "</binding></visual>"
           + ("" if ok else '<actions><action content="OK" arguments="ok" activationType="system"/></actions>')
           + "</toast>")
    for aumid in ((AUMID, PS_AUMID) if _register_aumid() else (PS_AUMID,)):
        script = (
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
            "ContentType = WindowsRuntime] | Out-Null;"
            "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, "
            "ContentType = WindowsRuntime] | Out-Null;"
            "$x = New-Object Windows.Data.Xml.Dom.XmlDocument;"
            f"$x.LoadXml('{xml.replace(chr(39), chr(39) * 2)}');"
            "$t = New-Object Windows.UI.Notifications.ToastNotification $x;"
            f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{aumid}').Show($t)"
        )
        enc = base64.b64encode(script.encode("utf-16-le")).decode()
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                "-EncodedCommand", enc], capture_output=True, timeout=30,
                               creationflags=NO_WINDOW)
            if r.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            return False
    return False


def result_toast(results: list, title_prefix: str = ""):
    """Zusammenfassung eines oder mehrerer Läufe als Benachrichtigung."""
    if not results:
        return
    bad = [r for r in results if not r["ok"]]
    if len(results) == 1:
        r = results[0]
        title = f"{title_prefix}„{r['name']}“ " + ("erfolgreich ✔" if r["ok"] else "– FEHLER")
        text = r["msg"]
    else:
        title = f"{title_prefix}{len(results) - len(bad)} von {len(results)} Profilen erfolgreich" + \
                (" – FEHLER" if bad else " ✔")
        text = "\n".join(("✔ " if r["ok"] else "✕ ") + f"{r['name']}: {r['msg']}" for r in results)[:240]
    toast(title, text, ok=not bad)
