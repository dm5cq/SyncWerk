# Code-Review SyncWerk 2.0

Datum: 16.11.2026 · Geprüft: alle Module unter `syncwerk/` und `SyncWerk.py`
Vorgehen: Durchsicht des Codes, eigene statische Prüfung (unbenutzte Importe, undefinierte Namen),
Kompilierung mit Python 3.11 und 3.13, automatische Tests der Engine, der Automatik und der
Oberflächenlogik (mit einer tkinter-Attrappe, da in der Build-Umgebung kein Tk verfügbar war).

## Gefundene und behobene Fehler

| # | Schwere | Fundstelle | Problem | Behebung |
|---|---|---|---|---|
| 1 | **hoch** | `engine.detect_moves` | Zwei *verschiedene* Dateien mit gleicher Größe und gleicher Uhrzeit (z. B. kleine Textdateien, im selben Moment erzeugt) wurden als „umbenannt“ erkannt → falscher Inhalt im Ziel möglich. Vom Test gefunden. | Zusätzliche Inhalts-Signatur (`quick_sig`: Größe + erste und letzte 64 KB, kleine Dateien komplett; im Modus „Genau“ volle Prüfsumme). Ohne Prüfmöglichkeit nur bei gleichem Dateinamen. |
| 2 | mittel | `engine.detect_moves` | Ordnerpfade wurden als Tupel übergeben, aber per „L“/„R“ abgefragt → Absturz im Modus „Genau“. | Umwandlung in Zuordnung. |
| 3 | mittel | `notify.py` | f-String mit Backslash im Ausdruck – mit Python 3.9–3.11 wäre der Build fehlgeschlagen. | Ausdruck vorab berechnet; Kompilierung mit 3.11 geprüft. |
| 4 | mittel | `drives._win_drives` (1.0) | Abfrage von getrennten Netzlaufwerken (`GetVolumeInformationW`) blockiert die Oberfläche mehrere Sekunden. | Netzlaufwerke werden nicht mehr abgefragt, Name kommt aus `WNetGetConnection`. |
| 5 | mittel | `drives` | Leere Kartenleser-Schächte können das Windows-Fenster „Kein Datenträger im Laufwerk“ auslösen – besonders beim Wächter alle 3 Sekunden. | `SetErrorMode(SEM_FAILCRITICALERRORS)`. |
| 6 | mittel | `gui.analyze` (1.0) | `sanity_check` (prüft Ordner) lief im Oberflächen-Thread → Hänger bei nicht erreichbaren Netzpfaden. | Prüfung in den Hintergrund-Thread verlegt. |
| 7 | mittel | Dialoge | Escape zum Schließen eines Dialogs hätte gleichzeitig eine laufende Synchronisation abgebrochen (globale Taste). | Escape im Dialog wird dort abgefangen („break“). |
| 8 | niedrig | `gui` | Taste `<App>` (Kontextmenü) gibt es nur unter Windows → Fehler beim Start auf macOS/Linux. | Nur unter Windows binden. |
| 9 | niedrig | `Pane.refresh` (1.0) | Bei jeder Navigation wurden alle Dateien gezählt (bei 500 000 Dateien spürbar). | Summen einmal nach der Analyse berechnet. |
| 10 | niedrig | Zeitplan (1.0) | Keine Prüfung von Uhrzeit-Format und der 261-Zeichen-Grenze von `schtasks /TR`. | Beides geprüft, verständliche Meldung. |
| 11 | niedrig | `dialogs`, `gui` | Unbenutzte Importe. | Entfernt. |

## Nachtrag 2.2 – Fehler aus dem Praxistest

| # | Schwere | Fundstelle | Problem | Behebung |
|---|---|---|---|---|
| 12 | **hoch** | `engine.lp` | Das Präfix `\\?\` wurde für *jeden* Pfad gesetzt. Virtuelle/Cloud-/WebDAV-Laufwerke lehnen es teils ab → jede Kopie scheiterte mit „Invalid argument“ (gemeldet bei `N1MM Logger+/Wav/…`). | Präfix nur noch ab 240 Zeichen Pfadlänge. |
| 13 | mittel | `Executor._copy` | Python meldet viele unterschiedliche Windows-Fehler beim Öffnen nur als „Invalid argument“ – Ursache nicht erkennbar. | Fehler nennen Schritt + Pfad; bei „Invalid argument“ wird die echte Windows-Fehlernummer per `CreateFileW` ermittelt und mit Klartext-Hinweis ausgegeben (z. B. Cloud-Client läuft nicht, Datei gesperrt, Name unzulässig). |
| 14 | mittel | `Executor._copy` | Konnte das Ziel das Änderungsdatum nicht setzen, schlug die ganze Kopie fehl. | Nicht mehr fatal, Hinweis am Ende des Laufs. |
| 15 | niedrig | Protokoll | Hunderte gleiche Fehlerzeilen. | Je Ursache max. 3 Zeilen, danach Zusammenfassung „N × Ursache“; die häufigste Ursache steht auch im Meldungsfenster. |

## Bewusste Entscheidungen / bekannte Grenzen

- **Backup überschreibt neuere Zieldateien.** Die Quelle gilt als maßgeblich. Schutz: alte Version
  wandert ins Archiv; in der Aktionsliste steht „Ziel ist neuer – wird überschrieben“.
- **Symbolische Links und Verzeichnis-Verknüpfungen** werden übersprungen (Schutz vor Endlosschleifen).
- **Zwei-Wege-Zustand** liegt pro Ordnerpaar in `%APPDATA%\SyncWerk\zustand`. Wird dasselbe Paar
  zusätzlich von einem zweiten PC synchronisiert, kennt jeder PC nur seinen eigenen Stand.
- **Ordner, die nach dem Löschen noch ausgeschlossene Dateien enthalten** (z. B. `Thumbs.db`),
  bleiben stehen – wird im Protokoll gelb vermerkt.
- **Wächter und Oberfläche** können theoretisch gleichzeitig dasselbe Profil synchronisieren.
  Selten; Folge wären nur doppelte Kopierversuche, keine Datenverluste (Temp-Datei + atomares Ersetzen).
- **Sprachausgabe** nutzt die Windows-Stimme über PowerShell. In stark abgesicherten
  Firmenumgebungen (Constrained Language Mode) kann sie stumm bleiben.
- **Ab 2.1 eigene, dunkle Menüleiste und eigene Meldungsfenster**: Die Windows-Standardleiste lässt sich
  nicht einfärben. Folge: Externe Bildschirmleser wie NVDA lesen sie nicht automatisch – das übernimmt
  die eingebaute Sprachausgabe (Menüpunkte, Meldungen, Fragen). Ordnerauswahl bleibt der
  Windows-Standarddialog (hell, aber von NVDA lesbar).
- **Benachrichtigungen** registrieren den Absender „SyncWerk“ in `HKCU\Software\Classes\AppUserModelId`.
  Falls Windows das ablehnt, erscheint die Meldung unter „Windows PowerShell“.
- **Autostart des Wächters** erfolgt über eine kleine VBS-Datei im Autostart-Ordner des Benutzers
  (ohne Administratorrechte). Manche Virenscanner fragen hier einmal nach.
- Die **Live-Ordneransicht vor der Analyse** liest eine Ordnerebene im Oberflächen-Thread
  (max. 20 000 Einträge). Auf sehr langsamen Netzfreigaben kann das kurz verzögern.

## Testabdeckung (automatisiert)

- Backup, Spiegeln, Richtung Rechts→Links, Zwei-Wege (Zusammenführen, Löschen, Änderung, Konflikt
  „überspringen“/„neuere gewinnt“, Ordnerlöschung), Inhaltsvergleich, Schutz bei leerer Quelle
- Umbenennen: einzelne Datei, ganzer Ordner (eine Aktion), teilweise verschobener Ordner,
  Zwei-Wege-Umbenennen, **keine** Fehl-Erkennung bei gleich großen verschiedenen Dateien
- Archiv: Versionen auflisten, Aufräumen nach Anzahl und Alter, Wiederherstellen inkl. Sicherung
  der aktuellen Datei
- Automatik: `--profil … --auto`, `--auftrag … --auto` mit absichtlich defektem Profil
  (läuft weiter, Exit-Code 1, Protokoll)
- Oberfläche (Logik): Analyse, Moduswechsel, Synchronisieren, Umbenennen, alle drei Ansichten,
  Schriftgröße, Profile, alle Dialoge, Sammelauftrag, Sprachausgabe-Texte

**Nicht automatisch prüfbar (bitte unter Windows ansehen):** Optik der drei Ansichten, Windows-Stimme,
Benachrichtigungen, Aufgabenplanung, USB-Erkennung per Seriennummer, Autostart des Wächters.
