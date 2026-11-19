"""Erzeugt assets/SyncWerk-Kurzanleitung.pdf (1 Seite A4).  Benötigt: pip install reportlab"""
import os
import sys

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from syncwerk import APP_VERSION, COPYRIGHT  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), "assets", "SyncWerk-Kurzanleitung.pdf")

for regular, bold in (("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                       "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
                      (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
                      (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf")):
    if os.path.exists(regular):
        pdfmetrics.registerFont(TTFont("R", regular))
        pdfmetrics.registerFont(TTFont("B", bold))
        pdfmetrics.registerFontFamily("R", normal="R", bold="B", italic="R", boldItalic="B")
        break

DARK, PANEL, CTRL = HexColor("#1c1c1f"), HexColor("#26262a"), HexColor("#3a3a41")
ORANGE, TEXT, MUTED = HexColor("#f28c28"), HexColor("#26262a"), HexColor("#6e6e73")
GREEN, BLUE, YELLOW, RED = HexColor("#2e9e55"), HexColor("#2f7fd1"), HexColor("#e0a800"), HexColor("#d64040")
TINTS = {"g": HexColor("#1c3324"), "b": HexColor("#1a2b40"), "y": HexColor("#36301a"), "r": HexColor("#402124")}

W, H = A4
M = 28
body = ParagraphStyle("b", fontName="R", fontSize=8.8, leading=11.4, textColor=TEXT)
small = ParagraphStyle("s", parent=body, fontSize=8, leading=10.2)


def para(c, text, x, y, w, style=body):
    p = Paragraph(text, style)
    _, h = p.wrap(w, 1000)
    p.drawOn(c, x, y - h)
    return y - h


def heading(c, text, x, y, w):
    c.setFillColor(ORANGE)
    c.rect(x, y - 15, 3, 13, stroke=0, fill=1)
    c.setFillColor(TEXT)
    c.setFont("B", 10.5)
    c.drawString(x + 8, y - 12.5, text)
    return y - 20


def badge(c, n, x, y, r=7):
    c.setFillColor(ORANGE)
    c.circle(x, y, r, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("B", 8)
    c.drawCentredString(x, y - 2.8, str(n))


def logo(c, x, y, s):
    c.setFillColor(ORANGE)
    c.circle(x, y, s, stroke=0, fill=1)
    c.setStrokeColor(white)
    c.setFillColor(white)
    c.setLineWidth(s * 0.16)
    c.line(x - s * 0.45, y + s * 0.2, x + s * 0.3, y + s * 0.2)
    p = c.beginPath(); p.moveTo(x + s * 0.55, y + s * 0.2); p.lineTo(x + s * 0.25, y + s * 0.45)
    p.lineTo(x + s * 0.25, y - s * 0.05); p.close(); c.drawPath(p, stroke=0, fill=1)
    c.line(x + s * 0.45, y - s * 0.22, x - s * 0.3, y - s * 0.22)
    p = c.beginPath(); p.moveTo(x - s * 0.55, y - s * 0.22); p.lineTo(x - s * 0.25, y + s * 0.03)
    p.lineTo(x - s * 0.25, y - s * 0.47); p.close(); c.drawPath(p, stroke=0, fill=1)


def mockup(c, x, y, w, h):
    """Schematische Darstellung des Hauptfensters mit nummerierten Bereichen."""
    c.setFillColor(DARK)
    c.roundRect(x, y - h, w, h, 6, stroke=0, fill=1)
    # Kopf
    c.setFillColor(HexColor("#141416")); c.rect(x, y - 22, w, 22, stroke=0, fill=1)
    logo(c, x + 13, y - 11, 7)
    c.setFillColor(white); c.setFont("B", 8); c.drawString(x + 25, y - 14, "SyncWerk")
    for i, t in enumerate(["Sprache: AN", "Ansicht", "A+", "Hilfe"]):
        c.setFillColor(ORANGE if i == 0 else CTRL)
        c.roundRect(x + w - 150 + i * 37, y - 17, 34, 12, 2, stroke=0, fill=1)
        c.setFillColor(white); c.setFont("R", 5); c.drawCentredString(x + w - 133 + i * 37, y - 13, t)
    c.setFillColor(ORANGE); c.rect(x, y - 24, w, 2, stroke=0, fill=1)
    # Steuerkarte
    c.setFillColor(PANEL); c.rect(x + 6, y - 58, w - 12, 30, stroke=0, fill=1)
    for i, (t, on) in enumerate((("Backup", 1), ("Spiegeln", 0), ("Zwei-Wege", 0))):
        c.setFillColor(ORANGE if on else CTRL)
        c.rect(x + 12 + i * 38, y - 46, 36, 11, stroke=0, fill=1)
        c.setFillColor(white); c.setFont("R", 5.2); c.drawCentredString(x + 30 + i * 38, y - 43, t)
    c.setFillColor(CTRL); c.rect(x + 132, y - 46, 50, 11, stroke=0, fill=1)
    c.setFillColor(white); c.drawCentredString(x + 157, y - 43, "Links → Rechts")
    for i in range(4):
        c.setFillColor(CTRL); c.rect(x + 12 + i * 60, y - 56, 54, 6, stroke=0, fill=1)
    # Zwei Seiten
    pw = (w - 30) / 2
    rows = [("g", "✔"), ("b", "→"), ("y", "≠"), ("g", "✔"), ("r", "✕"), ("y", "↪")]
    for k, px in enumerate((x + 6, x + 24 + pw)):
        c.setFillColor(PANEL); c.rect(px, y - 150, pw, 88, stroke=0, fill=1)
        c.setFillColor(CTRL if k == 0 else ORANGE); c.rect(px, y - 74, pw, 12, stroke=0, fill=1)
        c.setFillColor(white); c.setFont("B", 5.5)
        c.drawString(px + 4, y - 70.5, "LINKS · Quelle" if k == 0 else "RECHTS · Ziel")
        for i, (tint, sym) in enumerate(rows):
            ry = y - 86 - i * 10.5
            if k == 1 and i == 1:
                c.setFillColor(HexColor("#202024"))
            else:
                c.setFillColor(TINTS[tint])
            c.rect(px + 3, ry - 7, pw - 6, 9, stroke=0, fill=1)
            c.setFillColor(HexColor("#d6d6da")); c.rect(px + 7, ry - 4, pw * 0.45, 2.5, stroke=0, fill=1)
    c.setFillColor(CTRL); c.rect(x + 9 + pw, y - 100, 12, 10, stroke=0, fill=1)
    c.setFillColor(white); c.setFont("R", 6); c.drawCentredString(x + 15 + pw, y - 97.5, "⇄")
    # Aktionsliste
    c.setFillColor(PANEL); c.rect(x + 6, y - 186, w - 12, 30, stroke=0, fill=1)
    for i, tint in enumerate("byr"):
        c.setFillColor(TINTS[tint]); c.rect(x + 9, y - 168 - i * 6, w - 18, 5, stroke=0, fill=1)
    # Fußleiste
    c.setFillColor(PANEL); c.rect(x + 6, y - h + 6, w - 12, 22, stroke=0, fill=1)
    c.setFillColor(CTRL); c.rect(x + 12, y - h + 16, w * 0.5, 4, stroke=0, fill=1)
    c.setFillColor(ORANGE); c.rect(x + 12, y - h + 16, w * 0.3, 4, stroke=0, fill=1)
    c.setFillColor(CTRL); c.roundRect(x + w - 112, y - h + 10, 46, 14, 2, stroke=0, fill=1)
    c.setFillColor(ORANGE); c.roundRect(x + w - 62, y - h + 10, 52, 14, 2, stroke=0, fill=1)
    c.setFillColor(white); c.setFont("B", 5.5)
    c.drawCentredString(x + w - 89, y - h + 15, "Analysieren F5")
    c.drawCentredString(x + w - 36, y - h + 15, "▶ Sync F9")
    # Nummern
    for n, bx, by in ((1, x + w - 166, y - 11), (2, x + 4, y - 40), (3, x + 4, y - 68),
                      (4, x + w - 4, y - 68), (5, x + 4, y - 170), (6, x + w - 4, y - h + 17)):
        badge(c, n, bx, by)


def build():
    c = canvas.Canvas(OUT, pagesize=A4)
    c.setTitle(f"SyncWerk {APP_VERSION} – Kurzanleitung")
    c.setAuthor("Stefan J. Kaiser DM5CQ / OE8KKS")
    c.setSubject("Synchronisation & Backup – Kurzanleitung")
    # Kopf
    c.setFillColor(DARK); c.rect(0, H - 78, W, 78, stroke=0, fill=1)
    c.setFillColor(ORANGE); c.rect(0, H - 81, W, 3, stroke=0, fill=1)
    logo(c, M + 22, H - 39, 22)
    c.setFillColor(white); c.setFont("B", 22); c.drawString(M + 56, H - 38, "SyncWerk")
    c.setFillColor(ORANGE); c.setFont("B", 22); c.drawString(M + 56 + c.stringWidth("SyncWerk ", "B", 22), H - 38, APP_VERSION)
    c.setFillColor(HexColor("#d6d6da")); c.setFont("R", 10)
    c.drawString(M + 57, H - 55, "Kurzanleitung · Synchronisation & Backup – lokal · USB · Netzwerk · Cloud")

    top = H - 96
    lw = 300
    mockup(c, M, top, lw, 225)
    y = top - 234
    legend = [
        (1, "<b>Kopfzeile:</b> Sprachausgabe (F2), Ansicht Dunkel/Hell/Kontrast (F3/F4), Schrift A+/A−, Hilfe (F1)."),
        (2, "<b>Steuerung:</b> Profil, Modus, Richtung, Vergleich, Umbenennen erkennen, Archiv, Ausschlüsse."),
        (3, "<b>Linke Seite</b> – Laufwerk wählen, Pfad eintippen oder „Ordner …“."),
        (4, "<b>Rechte Seite</b> – Ziel ist orange markiert. Der Ketten-Knopf in der Mitte koppelt Navigation und Scrollen."),
        (5, "<b>Geplante Aktionen</b> (Strg+3) und Protokoll (Strg+4). Entf überspringt eine Aktion."),
        (6, "<b>Fortschritt</b> und die Knöpfe Analysieren (F5) / Synchronisieren (F9) / Abbrechen (Esc)."),
    ]
    for n, t in legend:
        badge(c, n, M + 7, y - 6, 6)
        y = para(c, t, M + 18, y, lw - 18, small) - 3

    # rechte Spalte
    rx, rw = M + lw + 18, W - 2 * M - lw - 18
    ry = heading(c, "In 5 Schritten", rx, top, rw)
    for i, t in enumerate([
            "Links und rechts einen Ordner wählen – auch USB, NAS (\\\\server\\freigabe), pCloud-Laufwerk "
            "oder Nextcloud-Ordner.",
            "Modus wählen (Alt+1/2/3), bei Bedarf Richtung umschalten (Alt+R).",
            "<b>Analysieren (F5)</b> – vergleicht nur, verändert nichts.",
            "Aktionen prüfen: Farben links/rechts und Liste unten.",
            "<b>Synchronisieren (F9)</b> – Zusammenfassung bestätigen, fertig."], 1):
        badge(c, i, rx + 7, ry - 6, 6)
        ry = para(c, t, rx + 18, ry, rw - 18) - 3
    ry = heading(c, "Modi", rx, ry - 6, rw)
    for t in ("<b>Backup</b> – Neues und Geändertes ins Ziel, im Ziel wird nie gelöscht.",
              "<b>Spiegeln</b> – Ziel wird exakte Kopie der Quelle.",
              "<b>Zwei-Wege</b> – beide Seiten gleich, inkl. Löschungen. Erster Lauf führt nur zusammen.",
              "Umbenannte/verschobene Dateien und Ordner werden <b>nur umbenannt</b>, nicht neu kopiert."):
        ry = para(c, "• " + t, rx, ry, rw) - 2
    ry = heading(c, "Farben", rx, ry - 6, rw)
    for col, t in ((GREEN, "Grün – identisch / erledigt"), (BLUE, "Blau – neu, wird kopiert"),
                   (YELLOW, "Gelb – geändert oder umbenannt"), (RED, "Rot – löschen, Konflikt, Fehler")):
        c.setFillColor(col); c.circle(rx + 5, ry - 5, 4.2, stroke=0, fill=1)
        ry = para(c, t, rx + 14, ry, rw - 14) - 2
    ry = para(c, "Ordner zeigen die auffälligste Farbe ihres Inhalts.", rx, ry - 2, rw, small)

    # untere Reihe
    y0 = min(y, ry) - 10
    cw = (W - 2 * M - 18) / 2
    y1 = heading(c, "Automatik & Archiv", M, y0, cw)
    for t in ("<b>Automatik …</b>: Zeitplan über die Windows-Aufgabenplanung.",
              "<b>USB-Auslöser</b>: Profil startet beim Anstecken einer bestimmten Platte – erkannt an der "
              "Seriennummer, nicht am Laufwerksbuchstaben. Dafür den Hintergrund-Wächter aktivieren.",
              "<b>Sammelaufträge</b> (Strg+J): mehrere Profile nacheinander, z. B. „Feierabend“.",
              "<b>Benachrichtigung</b> nach automatischen Läufen – grün = OK, rot = Fehler.",
              "<b>Archiv</b>: Gelöschtes/Überschriebenes landet in <i>_SyncWerk_Archiv</i>; Aufräumen nach "
              "90 Tagen bzw. 5 Versionen je Datei (einstellbar). <b>Wiederherstellen</b> mit Strg+R.",
              "Kommandozeile: <font name='B'>SyncWerk.exe --profil \"Name\" --auto</font> · "
              "<font name='B'>--auftrag \"Name\" --auto</font>"):
        y1 = para(c, "• " + t, M, y1, cw, small) - 2.5
    x2 = M + cw + 18
    y2 = heading(c, "Barrierefreiheit & Tasten", x2, y0, cw)
    keys = [("F1", "Hilfe"), ("F2", "Sprachausgabe ein/aus"), ("F3", "Hoher Kontrast"), ("F4", "Dunkel/Hell"),
            ("F5 / F9", "Analysieren / Synchronisieren"), ("Esc", "Abbrechen"),
            ("Strg+1 / 2", "Linke / rechte Seite"), ("Strg+3 / 4", "Aktionen / Protokoll"),
            ("Strg+L / D / O", "Pfad / Laufwerk / Ordner wählen"), ("Alt+1/2/3, Alt+R", "Modus, Richtung"),
            ("Strg+I", "Status vorlesen"), ("Strg+W", "Ansage wiederholen"),
            ("Strg+R / Strg+J", "Wiederherstellen / Sammelaufträge"), ("Strg+ + / − / 0", "Schriftgröße"),
            ("Tab, Pfeile, Enter", "Bewegen, wählen, öffnen")]
    for i, (k, d) in enumerate(keys):
        if i % 2 == 0:
            c.setFillColor(HexColor("#f1f1f2")); c.rect(x2, y2 - 11, cw, 11, stroke=0, fill=1)
        c.setFillColor(ORANGE); c.setFont("B", 7.6); c.drawString(x2 + 4, y2 - 8.2, k)
        c.setFillColor(TEXT); c.setFont("R", 7.6); c.drawString(x2 + 92, y2 - 8.2, d)
        y2 -= 11
    para(c, "Alle Bedienelemente sind mit Tab erreichbar und werden vorgelesen. Menüleiste: F10 oder "
            "Alt+Buchstabe (z. B. Alt+D), Menüpunkte werden ebenfalls vorgelesen.", x2, y2 - 4, cw, small)
    # Tipps
    tb_y, tb_h = 34, 74
    c.setFillColor(HexColor("#fdf0e2")); c.roundRect(M, tb_y, W - 2 * M, tb_h, 5, stroke=0, fill=1)
    c.setFillColor(ORANGE); c.rect(M, tb_y, 4, tb_h, stroke=0, fill=1)
    c.setFillColor(TEXT); c.setFont("B", 10); c.drawString(M + 14, tb_y + tb_h - 16, "Tipps")
    para(c, "• <b>Sicher testen:</b> Analysieren verändert nie etwas – erst F9 synchronisiert. "
            "• <b>Nichts geht verloren:</b> mit „Archivieren statt löschen“ ist jede gelöschte oder überschriebene "
            "Datei wiederherstellbar. • <b>USB-Platte nicht angesteckt?</b> Beim Spiegeln einer leeren Quelle "
            "warnt SyncWerk, automatische Läufe brechen ab. • <b>Einstellungen, Profile, Protokolle:</b> "
            "%APPDATA%\\SyncWerk", M + 14, tb_y + tb_h - 22, W - 2 * M - 28, small)
    # Fuß
    c.setFillColor(DARK); c.rect(0, 0, W, 22, stroke=0, fill=1)
    c.setFillColor(HexColor("#a3a3ab")); c.setFont("R", 7)
    c.drawCentredString(W / 2, 8, COPYRIGHT + f"  ·  SyncWerk {APP_VERSION}")
    c.showPage()
    c.save()
    print("geschrieben:", OUT)


if __name__ == "__main__":
    build()
