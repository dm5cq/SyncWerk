"""Profile und Sammelaufträge ohne Rückfrage ausführen (Zeitplan, USB-Auslöser, Sammelauftrag)."""
import os

from . import drives
from . import engine as E
from . import jobs
from . import notify
from . import storage


def resolve(p: dict):
    """Ersetzt bei USB-gebundenen Profilen den Laufwerksbuchstaben anhand der Seriennummer.
    Rückgabe: (Profil-Kopie, Fehlertext oder "")."""
    p = {**storage.DEFAULT_PROFILE, **p}
    if p.get("usb_serial") and p.get("usb_side") in ("L", "R"):
        key = "left" if p["usb_side"] == "L" else "right"
        root = drives.serial_map().get(p["usb_serial"])
        if root:
            p[key] = os.path.join(root, p.get("usb_rel", "")) if p.get("usb_rel") else root
        elif drives.IS_WIN:
            return p, f"USB-Laufwerk „{p.get('usb_label') or p['usb_serial']}“ ist nicht angeschlossen."
    return p, ""


def _result(name, ok, msg, done=0, failed=0):
    return {"name": name, "ok": ok, "msg": msg, "done": done, "failed": failed}


def run_profile(name: str, notify_result=True, progress=None, log=None, cancel=None, info=None) -> dict:
    profiles = storage.load_profiles()
    if name not in profiles:
        res = _result(name, False, "Profil nicht gefunden")
    else:
        res = _run(name, profiles[name], progress, log, cancel, info)
    storage.write_log([f"AUTO „{name}“: {'OK' if res['ok'] else 'FEHLER'} – {res['msg']}"])
    if notify_result:
        notify.result_toast([res], "SyncWerk: ")
    return res


def _run(name, p, progress, log, cancel, info):
    p, miss = resolve(p)
    if miss:
        return _result(name, False, miss)
    errs = E.sanity_check(p.get("left", ""), p.get("right", ""))
    if errs:
        return _result(name, False, " ".join(errs).replace("\n", " "))
    an = jobs.analyze(p["left"], p["right"], jobs.options_from_profile(p), info=info, cancel=cancel)
    blocking = [w for w in an.warnings if w.startswith("ACHTUNG") or "zu wenig Speicher" in w]
    if blocking:
        return _result(name, False, blocking[0])
    todo = [a for a in an.acts if a.kind != "conflict"]
    if not todo:
        return _result(name, True, "bereits synchron – nichts zu tun")
    ok, failed = jobs.execute(an, progress=progress, log=log, cancel=cancel)
    s = E.summarize(an.acts)
    msg = (f"{ok} Aktionen, {E.fmt_size(s['bytes'])} übertragen" if not failed
           else f"{failed} Fehler, {ok} erfolgreich – siehe Protokoll")
    return _result(name, failed == 0, msg, ok, failed)


def run_batch(job: str, notify_result=True, progress=None, log=None, cancel=None, info=None,
              on_profile=None) -> list:
    names = storage.load_jobs().get(job)
    if not names:
        res = [_result(job, False, "Sammelauftrag nicht gefunden oder leer")]
    else:
        res = []
        for i, n in enumerate(names, 1):
            if cancel is not None and cancel.is_set():
                break
            if on_profile:
                on_profile(i, len(names), n)
            try:
                res.append(run_profile(n, False, progress, log, cancel, info))
            except E.Cancelled:
                res.append(_result(n, False, "abgebrochen"))
                break
    storage.write_log([f"SAMMELAUFTRAG „{job}“: " + "; ".join(
        f"{r['name']}={'OK' if r['ok'] else 'FEHLER'}" for r in res)])
    if notify_result:
        notify.result_toast(res, f"SyncWerk „{job}“: ")
    return res
