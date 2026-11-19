"""Kompletter Ablauf eines Sync-Auftrags (für Oberfläche und Automatik)."""
import time
from dataclasses import dataclass, field

from . import archive
from . import engine as E
from . import storage


def options_from_profile(p: dict) -> E.Options:
    return E.Options(
        mode=p.get("mode", "backup"),
        direction=p.get("direction", "LR"),
        compare=p.get("compare", "fast"),
        archive=bool(p.get("archive", True)),
        conflict=p.get("conflict", "newer"),
        ignore_dst=bool(p.get("ignore_dst", True)),
        excludes=E.parse_excludes(p.get("excludes", "")),
        detect_moves=bool(p.get("detect_moves", True)),
        archive_days=int(p.get("archive_days", 90) or 0),
        archive_keep=int(p.get("archive_keep", 5) or 0),
    )


@dataclass
class Analysis:
    lroot: str
    rroot: str
    opts: E.Options
    L: dict = field(default_factory=dict)
    R: dict = field(default_factory=dict)
    cmp: dict = field(default_factory=dict)
    acts: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    state: dict = field(default_factory=dict)
    status: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


def analyze(lroot, rroot, opts: E.Options, info=None, cancel=None) -> Analysis:
    info = info or (lambda text, frac=None: None)
    an = Analysis(lroot, rroot, opts)
    info("Lese linke Seite ein …")
    an.L, el = E.scan(lroot, opts.excludes,
                      lambda n, d: info(f"Links: {n:,} Einträge – {d}".replace(",", ".")), cancel)
    info("Lese rechte Seite ein …")
    an.R, er = E.scan(rroot, opts.excludes,
                      lambda n, d: info(f"Rechts: {n:,} Einträge – {d}".replace(",", ".")), cancel)
    an.errors = [f"Links: {x}" for x in el] + [f"Rechts: {x}" for x in er]
    info("Vergleiche …")
    an.cmp = E.compare(an.L, an.R, lroot, rroot, opts,
                       lambda d, t, rel: info(f"Inhaltsvergleich: {rel}", d / t), cancel)
    if opts.mode == "twoway":
        an.state = storage.load_state(lroot, rroot)
    an.acts = E.plan(an.L, an.R, an.cmp, opts, an.state, (lroot, rroot))
    an.status = E.status_map(an.L, an.R, an.cmp, an.acts)
    an.warnings = E.space_warnings(an.acts, lroot, rroot)
    # Schutz: leere/abgesteckte Quelle beim Spiegeln
    if opts.mode == "mirror":
        S, D = (an.L, an.R) if opts.direction == "LR" else (an.R, an.L)
        nfs = sum(1 for e in S.values() if not e.is_dir)
        nfd = sum(1 for e in D.values() if not e.is_dir)
        if nfs == 0 and nfd > 0:
            an.warnings.insert(0, "ACHTUNG: Die Quelle ist leer – beim Spiegeln würde das Ziel "
                                  f"komplett geleert ({nfd} Dateien)!")
    if opts.mode == "twoway" and not an.state:
        an.warnings.append("Erster Zwei-Wege-Abgleich: es wird nur zusammengeführt, nichts gelöscht.")
    info("Analyse fertig.", 1.0)
    return an


def execute(an: Analysis, progress=None, log=None, cancel=None):
    ex = E.Executor(an.lroot, an.rroot, an.opts, progress, log, cancel)
    started = time.time()
    lines = [f"===== {time.strftime('%Y-%m-%d %H:%M:%S')}  {an.opts.mode}  "
             f"{an.lroot}  <->  {an.rroot}"]

    def _log(msg, col=None):
        lines.append(msg)
        if log:
            log(msg, col)

    ex.log = _log
    try:
        ok, failed = ex.run(an.acts)
    finally:
        if an.opts.mode == "twoway":
            # Zustand neu ermitteln (auch nach Abbruch, damit nichts doppelt passiert)
            L, _ = E.scan(an.lroot, an.opts.excludes)
            R, _ = E.scan(an.rroot, an.opts.excludes)
            fast = E.Options(**{**an.opts.__dict__, "compare": "fast"})
            cmp = E.compare(L, R, an.lroot, an.rroot, fast)
            storage.save_state(an.lroot, an.rroot, E.build_state(L, R, cmp, an.state))
        if an.opts.archive_days or an.opts.archive_keep:
            for root in (an.lroot, an.rroot):
                try:
                    n, freed = archive.cleanup(root, an.opts.archive_days, an.opts.archive_keep)
                    if n:
                        _log(f"Archiv aufgeräumt ({root}): {n} alte Versionen, {E.fmt_size(freed)} frei", E.GREEN)
                except OSError as e:
                    _log(f"Archiv-Aufräumen fehlgeschlagen ({root}): {e}", E.RED)
        lines.append(f"Ende: {ex.ok} ok, {ex.failed} Fehler, {time.time() - started:.1f} s")
        storage.write_log(lines)
    return ok, failed
