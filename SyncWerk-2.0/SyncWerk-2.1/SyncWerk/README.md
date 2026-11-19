# SyncWerk 2.1 – Synchronisation & Backup

Eigenständige Windows-App (EXE) zum Abgleichen von Ordnern auf **lokalen Platten, USB-Laufwerken
und Netz-/Cloudlaufwerken** (pCloud Drive, Nextcloud, NAS, `\\server\freigabe`).
Dunkel als Standard, Hell und Hoher Kontrast, Sprachausgabe und vollständige Tastaturbedienung.

Idee und Prompt: **Stefan J. Kaiser DM5CQ / OE8KKS** · Umsetzung: Claude Opus 5.5 (Anthropic), 16.11.2026

**Kurzanleitung (1 Seite):** `assets/SyncWerk-Kurzanleitung.pdf` – auch im Programm unter Hilfe.

---

## EXE erstellen
1. Python 3.9 oder neuer installieren (python.org, Haken **„Add python.exe to PATH“**).
2. Ordner `SyncWerk` entpacken, **`build-exe.bat`** doppelklicken.
3. Ergebnis: `dist\SyncWerk.exe` – eine Datei, läuft ohne Python.

Test ohne Build: `start-ohne-build.bat`.
Wer die EXE verschiebt und den USB-Wächter oder Zeitpläne nutzt: danach im Programm unter
Automatik den Wächter erneut aktivieren bzw. die Aufgabe neu anlegen (Pfad ändert sich).

## Neu in 2.0
| Funktion | Wo |
|---|---|
| **USB-Auslöser** – Profil startet beim Anstecken einer bestimmten Platte (Seriennummer, nicht Laufwerksbuchstabe) | Automatik … → USB-Auslöser + Hintergrund-Wächter |
| **Archiv räumt sich selbst auf** (Standard 90 Tage, max. 5 Versionen je Datei) | Steuerleiste „aufbewahren“ |
| **Wiederherstellen-Fenster** für archivierte Versionen | Wiederherstellen … / Strg+R |
| **Umbenennen/Verschieben erkennen** – Ordner werden im Ziel nur umbenannt | Kästchen in der Steuerleiste |
| **Sammelaufträge** – mehrere Profile nacheinander, auch per Zeitplan | Sammelaufträge … / Strg+J |
| **Windows-Benachrichtigung** nach automatischen Läufen, rotes Symbol bei Fehlern | automatisch |
| **Dunkel** (Standard), **Hell**, **Hoher Kontrast** | Kopfzeile „Ansicht“, F3/F4 |
| **Sprachausgabe** für blinde und sehbehinderte Menschen | Kopfzeile, F2 |
| **Volle Tastaturbedienung**, Schriftgröße 80–200 % | siehe Tasten unten |

## Bedienung
1. Links und rechts einen Ordner wählen (Laufwerksliste, „Ordner …“ oder Pfad + Enter).
2. Modus: **Backup** (nie löschen) · **Spiegeln** (Ziel = Quelle) · **Zwei-Wege** (beide Seiten gleich).
3. **Analysieren (F5)** – verändert nichts.
4. Aktionen prüfen (Strg+3, Entf überspringt eine Aktion).
5. **Synchronisieren (F9)**, Abbrechen mit Esc.

### Farben
🟢 identisch · 🔵 neu · 🟡 geändert/umbenannt · 🔴 löschen/Konflikt/Fehler.
Ordner zeigen die auffälligste Farbe ihres Inhalts.

### Barrierefreiheit
- **Sprachausgabe** (F2): eingebaute Windows-Stimme, keine Zusatzsoftware. Liest Bedienelemente,
  Listenzeilen (Name, Größe, Datum, Status), Ergebnisse, Fortschritt (25 %-Schritte) und Meldungen.
  Tempo im Menü Barrierefreiheit.
- **Hoher Kontrast** (F3): Gelb/Weiß/Cyan auf Schwarz, fette Schrift, Rahmen um Knöpfe.
- **Schriftgröße**: Strg+Plus / Strg+Minus / Strg+0.
- **Tastatur**: alle Elemente per Tab erreichbar, deutlicher Fokusrahmen.
- **Menüleiste** (dunkel, ab 2.1): F10 oder Alt+unterstrichener Buchstabe (Alt+D Datei, Alt+S
  Synchronisation, Alt+A Archiv, Alt+U Automatik, Alt+N Ansicht, Alt+B Barrierefreiheit, Alt+H Hilfe).
  Menüpunkte und Meldungsfenster werden von der eingebauten Sprachausgabe vorgelesen.

| Taste | Funktion |
|---|---|
| F1 / F2 / F3 / F4 | Hilfe / Sprachausgabe / Hoher Kontrast / Dunkel–Hell |
| F5 / F9 / Esc | Analysieren / Synchronisieren / Abbrechen |
| Strg+1 / 2 / 3 / 4 | Linke Seite / rechte Seite / Aktionen / Protokoll |
| Strg+L / D / O | Pfadfeld / Laufwerk / Ordner wählen (aktive Seite) |
| Alt+1 / 2 / 3, Alt+R | Modus Backup / Spiegeln / Zwei-Wege, Richtung |
| Strg+S / P | Profil speichern / Profilauswahl |
| Strg+R / J | Wiederherstellen / Sammelaufträge |
| Strg+I / W | Status vorlesen / letzte Ansage wiederholen |
| Pfeile, Enter, Rücktaste | Bewegen, Ordner öffnen, Ebene höher |

### Automatik
- **Zeitplan**: Automatik … → täglich, wöchentlich, stündlich oder bei Anmeldung.
- **USB-Auslöser**: Seite wählen, die auf der USB-Platte liegt (Platte dafür anstecken), Häkchen
  „automatisch starten“, dann **Wächter aktivieren**. Der Wächter startet unsichtbar mit Windows.
- Automatische Läufe brechen ab, wenn die Quelle leer/nicht erreichbar ist oder Platz fehlt.
- Kommandozeile: `SyncWerk.exe --profil "Name" --auto` · `--auftrag "Name" --auto` · `--waechter`

### Sicherheit
- Archiv statt Löschen, Kopie über Temp-Datei, Größenprüfung, Prüfung des freien Speichers.
- Warnung beim Spiegeln einer leeren Quelle; Sperre bei verschachtelten oder gleichen Ordnern.
- Umbenennungen nur nach Inhaltsprüfung (Anfang + Ende bzw. ganze Datei).

### Ablage
`%APPDATA%\SyncWerk\` → Profile, Sammelaufträge, Einstellungen, Zwei-Wege-Zustände, Protokolle.

## Projektstruktur
```
SyncWerk/
├─ SyncWerk.py                Start (Oberfläche, --auto, --auftrag, --waechter)
├─ syncwerk/
│  ├─ engine.py               Einlesen, Vergleich, Planung, Umbenennen erkennen, Ausführung
│  ├─ jobs.py                 Ablauf Analyse → Ausführung, Archiv-Aufräumen
│  ├─ archive.py              Archiv: Versionen, Aufräumen, Wiederherstellen
│  ├─ auto.py                 Automatik: Profile, Sammelaufträge, USB-Auflösung
│  ├─ watcher.py              Hintergrund-Wächter (USB-Seriennummer)
│  ├─ notify.py               Windows-Benachrichtigungen
│  ├─ speech.py               Sprachausgabe
│  ├─ theme.py                Dunkel / Hell / Hoher Kontrast, Schriftgröße
│  ├─ widgets.py              barrierefreie Bedienelemente
│  ├─ gui.py                  Hauptfenster
│  ├─ dialogs.py              Hilfe, Wiederherstellen, Sammelaufträge, Automatik
│  ├─ drives.py               Laufwerke & Seriennummern
│  └─ storage.py              Profile, Einstellungen, Protokolle
├─ assets/                    Icon, Benachrichtigungs-Symbole, Kurzanleitung (PDF)
├─ tools/kurzanleitung_erstellen.py   PDF neu erzeugen (pip install reportlab)
├─ build-exe.bat · start-ohne-build.bat · version_info.txt · requirements.txt
├─ PROMPT.md                  Prompt-Export + Stand für die Weiterarbeit
├─ REVIEW.md                  Code-Review
└─ VORSCHLAEGE.md             Ideen für 3.0
```

## Versionen
- **2.1** (16.11.2026) – Menüleiste und alle Menüs dunkelgrau mit weißer Schrift, Info-Fenster und alle
  Meldungen/Fragen im FotoRahmen-Stil (Symbol-Quadrat, Fußleiste, oranger OK-Knopf), dunkle Titelleisten.
- **2.0** (16.11.2026) – USB-Auslöser, Archiv-Aufräumen & Wiederherstellen, Umbenennen erkennen,
  Sammelaufträge, Benachrichtigungen, Dunkelmodus, Hoher Kontrast, Sprachausgabe, Tastaturbedienung,
  Code-Review mit Fehlerbehebungen.
- **1.0** (16.11.2026) – erste Version.
