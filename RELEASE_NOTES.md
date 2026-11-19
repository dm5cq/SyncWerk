## SyncWerk – Synchronisation & Backup

**Download:** `SyncWerk.exe` herunterladen und starten. Es ist keine Installation nötig, die Datei läuft ohne Python.
Die einseitige Kurzanleitung liegt als PDF dabei.

### Neu in 2.2
- Fehler „Invalid argument“ beim Kopieren behoben: Das Langpfad-Präfix `\\?\` wird nur noch bei Pfaden ab 240 Zeichen verwendet. Bei kürzeren Pfaden lehnten pCloud Drive, WebDAV/Nextcloud und manche NAS es ab.
- Fehlermeldungen nennen den Schritt, den Pfad und die echte Windows-Ursache mit Hinweis. Gleiche Fehler werden zusammengefasst.
- Kann das Ziel das Änderungsdatum nicht setzen, wird die Datei trotzdem kopiert (Hinweis im Protokoll).

### Seit 2.0 / 2.1
- Profil startet automatisch beim Anstecken einer bestimmten USB-Platte (erkannt an der Seriennummer)
- Das Archiv räumt sich selbst auf (90 Tage / 5 Versionen), Fenster zum Wiederherstellen
- Umbenannte und verschobene Ordner werden im Ziel nur umbenannt
- Sammelaufträge (mehrere Profile nacheinander), Windows-Benachrichtigungen
- Dunkelmodus, Hell, Hoher Kontrast, Sprachausgabe (F2), vollständige Tastaturbedienung
- Dunkle Menüleiste, Info-Fenster und Meldungen im FotoRahmen-Stil

### Hinweis
Windows SmartScreen kann beim ersten Start warnen, weil die EXE nicht signiert ist: **Weitere Informationen → Trotzdem ausführen**.

Idee und Prompt: Stefan J. Kaiser DM5CQ / OE8KKS · Umsetzung: Claude Opus 5.5 (Anthropic) · Lizenz: GPL-3.0
