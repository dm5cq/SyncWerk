# Vorschläge für SyncWerk 3.0

In 2.0 umgesetzt: USB-Auslöser per Seriennummer, Archiv mit Aufräumen und Wiederherstellen,
Erkennen von Umbenennungen, Sammelaufträge, Windows-Benachrichtigungen, Dunkel/Hell/Hoher Kontrast,
Sprachausgabe und volle Tastaturbedienung.

## Hoher Nutzen
1. **Direkte Cloud-Anbindung per WebDAV** (Nextcloud, pCloud, NAS) – ohne Laufwerk oder Client.
2. **Parallel kopieren** (2–4 Dateien gleichzeitig) – deutlich schneller bei vielen kleinen Dateien
   über das Netzwerk.
3. **Symbol im Infobereich** (neben der Uhr) für den Wächter: Status, „Jetzt sichern“, letzte Läufe.
4. **Verifizieren nach dem Kopieren** per Prüfsumme (optional) – für Archivplatten.
5. **Bildschirmleser-Schnittstelle** (NVDA-Controller / UI Automation), damit NVDA statt der
   eingebauten Stimme spricht – für Nutzer, die NVDA ohnehin verwenden.

## Mittlerer Nutzen
6. **Drag & Drop** von Ordnern aus dem Explorer auf die linke/rechte Seite.
7. **Filter „nur Unterschiede“** und Suche in der Explorer-Ansicht.
8. **Bandbreitenbegrenzung** für Netz-/Cloudziele.
9. **Bericht als HTML/PDF** nach jedem Lauf.
10. **Speicherplatz-Balken** je Seite.

## Nice to have
11. **macOS-Version** (`build-app.sh`, wie FotoRahmen/YT-Lader).
12. **Verschlüsseltes Backup** für Cloud-Ziele.
13. **Einzelne Datei per Rechtsklick** nach links/rechts kopieren.
14. **Englische Oberfläche** (Sprachdatei).
