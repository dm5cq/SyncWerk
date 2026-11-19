# SyncWerk – Prompt-Export und Projektstand

Dieses Dokument enthält alle Aufträge im Wortlaut und den technischen Stand, damit mit einem
KI-Modell nahtlos weitergearbeitet werden kann. Einfach diese Datei (und bei Bedarf den Code)
mitgeben.

---

## Prompt 1 – Version 1.0 (Stefan J. Kaiser, 16.11.2026)

> ich benötige eine eigenständige App als EXE – die Funktion soll sein – die Synchronisation von
> lokalen HDDs/SSDs, angeschlossenen HDDs/SSDs per USB und oder Netzlaufwerken wie pCloud,
> NextCloud, etc. – es soll geprüft werden ob bereits der Datenbestand vorliegt und ggf. dann nur
> die neuen und geänderten Daten synchronisiert werden. Möglichkeit zum Backup, Sync in eine
> Richtung – Sync in beide Richtungen. Die Anwendung soll einfach zu bedienen sein – Layout im
> Stil der FotoRahmen App und in Grau, Orange, Weiß, für weitere Status ROT, GRÜN, GELB und BLAU –
> Anzeige ggf. von 2 Quellen links und rechts wie ein Explorer – mach dann auch noch Vorschläge.
> Erstelle das alles damit ich das lokal mit der build-exe.bat dann zur Standalone-Anwendung
> kompilieren kann.

## Prompt 2 – Version 2.0 (Stefan J. Kaiser, 16.11.2026)

> setze das bitte in Version 2.0 um – Vorschläge für Version 2.0, die fünf wichtigsten:
> 1. Backup startet automatisch beim Einstecken einer bestimmten USB-Platte. Die Platte wird an
>    ihrer Seriennummer erkannt, nicht am Laufwerksbuchstaben.
> 2. Das Archiv räumt sich selbst auf, zum Beispiel nach 90 Tagen oder ab 5 Versionen je Datei,
>    plus ein Fenster zum Wiederherstellen.
> 3. Verschobene oder umbenannte Ordner werden erkannt und im Ziel nur umbenannt statt komplett
>    neu kopiert. Das spart bei großen Fotoarchiven viel Zeit.
> 4. Mehrere Profile laufen nacheinander als ein gemeinsamer Feierabend-Auftrag.
> 5. Nach automatischen Läufen erscheint eine Windows-Benachrichtigung, bei Fehlern rot.
> 6. Ich möchte die App primär im Dunkel-Modus, also mit Dunkelgrau wie die FotoRahmen-App und
>    der YT-Lader dargestellt haben – die helle Version kann so bleiben. Zusätzlich möchte ich, dass
>    die App barrierefrei ist – also auch mit Sprachausgabe für Blinde und Sehbehinderte –
>    Sprachausgabe direkt darüber ein- und ausschalten – Hoher-Kontrast-Modus – Review des Codes
>    und Export des Prompts und Erstellung einer Quickguide, 1 Seite als PDF.

## Prompt 3 – Version 2.1 (Stefan J. Kaiser, 16.11.2026)

> der Menübalken und die Menüs oben sind noch in Hell – die sollten auch in Grau mit weißer Schrift
> sein. Das Info-Feld sollte so ähnlich aussehen wie in dieser App
> *(Screenshot „Über FotoRahmen“: dunkles Fenster, oranges Quadrat mit „i“, Textzeilen Version,
> Beschreibung, ©, Idee und Prompt, Umsetzung, Lizenz, Funktionsstatus; Fußleiste mit orangem
> OK-Knopf rechts)*

## Prompt 4 – Version 2.2 (Stefan J. Kaiser, 16.11.2026)

> da kommen immer Fehlermeldungen – invalid argument – da passt was nicht
> `21:50:57  FEHLER  → kopieren  N1MM Logger+/Wav/DM5CQ2/MHz.wav: Invalid argument` (… viele weitere
> Dateien im selben Ordner)

---

## Rahmenbedingungen
- Autor/Copyright: „Idee und Prompt: Stefan J. Kaiser DM5CQ / OE8KKS“, Umsetzung Claude (Anthropic) + Datum
- Versionsnummern zweistellig (1.0, 2.0 …)
- Optik: Dunkel (Standard) wie FotoRahmen/YT-Lader; Hell wie 1.0; Hoher Kontrast
- Akzent Orange; Statusfarben Grün = identisch, Blau = neu, Gelb = geändert/umbenannt,
  Rot = löschen/Konflikt/Fehler
- Build lokal per `build-exe.bat` (PyInstaller, eine EXE)

## Technischer Stand 2.2
- Python 3.9+, nur Standardbibliothek (Tkinter/ttk „clam“); Build mit PyInstaller `--onefile --windowed`
- Module:
  - `engine.py` – Einlesen, Vergleich, Planung, Ausführung; neu: `detect_moves` (Aktionen
    `move`/`movedir`, abgesichert über `quick_sig`)
  - `jobs.py` – Ablauf Analyse → Ausführung, Zwei-Wege-Zustand, Archiv-Aufräumen nach dem Lauf
  - `archive.py` – Versionen auflisten, aufräumen (Tage/Anzahl), wiederherstellen
  - `auto.py` – Profil/Sammelauftrag ohne Rückfrage; `resolve()` setzt bei USB-Profilen den
    Laufwerksbuchstaben anhand der Seriennummer
  - `watcher.py` – Hintergrund-Wächter (`--waechter`), Mutex `Local\SyncWerkWaechter`,
    Autostart per VBS im Benutzer-Autostart, Stopp über Datei `waechter.stop`
  - `notify.py` – Windows-Toast über PowerShell/WinRT, eigener Absender `SKaiser.SyncWerk`
  - `speech.py` – Sprachausgabe über dauerhaften PowerShell-Prozess (System.Speech, deutsche Stimme),
    Texte Base64-übertragen; Symbole werden in sprechbaren Text umgeschrieben
  - `theme.py` – Farbschemata `dunkel`/`hell`/`kontrast`, Schriftskalierung
  - `widgets.py` – fokussierbare Schaltflächen, Umschalter, Dialog-Basis, Sprach-Hooks, Tastenliste;
    ab 2.1 `MenuBar` (eigene dunkle Menüleiste, Alt+Buchstabe/F10), `dark_menu` (dunkle Menüs mit
    Vorlesen per `<<MenuSelect>>`), `MessageDialog` (Info/Warnung/Fehler/Frage/Eingabe im FotoRahmen-Stil)
  - `gui.py` – Hauptfenster; Theme-/Schriftwechsel baut die Oberfläche neu auf (Zustand bleibt)
  - `dialogs.py` – Hilfe, Wiederherstellen, Sammelaufträge, Automatik (Zeitplan, USB, Wächter)
- Ablage: `%APPDATA%\SyncWerk\` → `profile.json`, `sammelauftraege.json`, `einstellungen.json`,
  `zustand\`, `protokolle\`, `waechter.stop`
- Profil-Felder: left, right, mode, direction, compare, archive, conflict, ignore_dst, excludes,
  detect_moves, archive_days, archive_keep, usb_serial, usb_label, usb_side, usb_rel, usb_auto
- Kommandozeile: `--profil NAME --auto`, `--auftrag NAME --auto`, `--waechter`
- Kurzanleitung: `assets/SyncWerk-Kurzanleitung.pdf`, erzeugt mit `tools/kurzanleitung_erstellen.py`
- Review-Ergebnis: siehe `REVIEW.md`

## Nächste Schritte
Siehe `VORSCHLAEGE.md` (Ideen für 3.0).
