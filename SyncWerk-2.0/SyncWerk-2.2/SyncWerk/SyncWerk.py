"""SyncWerk 2.0 – Startpunkt.

  SyncWerk.exe                                Oberfläche starten
  SyncWerk.exe --profil "Name" --auto         Profil ohne Oberfläche ausführen
  SyncWerk.exe --auftrag "Name" --auto        Sammelauftrag (mehrere Profile) ausführen
  SyncWerk.exe --waechter                     Hintergrund-Wächter für USB-Auslöser

Idee und Prompt: Stefan J. Kaiser DM5CQ / OE8KKS · Umsetzung: Claude (Anthropic), 16.11.2026
"""
import argparse
import sys


def main():
    ap = argparse.ArgumentParser(prog="SyncWerk", add_help=True)
    ap.add_argument("--profil", help="Name eines gespeicherten Profils")
    ap.add_argument("--auftrag", help="Name eines Sammelauftrags")
    ap.add_argument("--auto", action="store_true", help="ohne Oberfläche ausführen")
    ap.add_argument("--waechter", action="store_true", help="USB-Wächter im Hintergrund")
    args, _ = ap.parse_known_args()
    if args.waechter:
        from syncwerk import watcher
        sys.exit(watcher.run())
    if args.auto and (args.profil or args.auftrag):
        from syncwerk import auto
        if args.auftrag:
            res = auto.run_batch(args.auftrag)
        else:
            res = [auto.run_profile(args.profil)]
        sys.exit(0 if all(r["ok"] for r in res) else 1)
    from syncwerk.gui import main as gui_main
    gui_main()


if __name__ == "__main__":
    main()
