"""Sprachausgabe für blinde und sehbehinderte Menschen.

Windows: eingebaute Windows-Stimme (SAPI, System.Speech) über einen dauerhaft laufenden,
unsichtbaren PowerShell-Prozess – keine Zusatzbibliothek nötig, deutsche Stimme wird
automatisch gewählt. macOS: „say“, Linux: „spd-say“.
"""
import base64
import re
import subprocess
import sys
import threading

IS_WIN = sys.platform.startswith("win")
NO_WINDOW = 0x08000000

_PS = r"""
$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$v = $s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'de*' } | Select-Object -First 1
if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }
$s.Rate = __RATE__
while ($true) {
  $l = [Console]::In.ReadLine()
  if ($l -eq $null) { break }
  if ($l -eq '!STOP') { $s.SpeakAsyncCancelAll(); continue }
  if ($l.StartsWith('!RATE ')) { $s.Rate = [int]$l.Substring(6); continue }
  if ($l.StartsWith('+')) { $l = $l.Substring(1) } else { $s.SpeakAsyncCancelAll() }
  $t = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($l))
  [void]$s.SpeakAsync($t)
}
"""

# Symbole so umschreiben, dass sie sinnvoll vorgelesen werden
_REPLACE = [
    ("→ kopieren", "kopieren nach rechts"), ("← kopieren", "kopieren nach links"),
    ("→ Ordner anlegen", "Ordner rechts anlegen"), ("← Ordner anlegen", "Ordner links anlegen"),
    ("Links  →  Rechts", "von links nach rechts"), ("Links  ←  Rechts", "von rechts nach links"),
    ("Links ⇄ Rechts", "in beide Richtungen"),
    ("→", " nach "), ("←", " von "), ("⇄", ""), ("⇆", " und "), ("✕", ""), ("✔", ""), ("⚠", "Warnung: "),
    ("≠", "verschieden"), ("●", ""), ("↪", ""), ("■", ""), ("▶", ""), ("…", ""), ("·", ","),
    ("—", ""), ("⛓", ""), ("⟳", ""), ("(F5)", ", Taste F5"), ("(F9)", ", Taste F9"),
    ("%", " Prozent"), ("„", ""), ("“", ""), ("\\", " "), (" / ", " von "),
]


def clean(text: str) -> str:
    t = str(text)
    for a, b in _REPLACE:
        t = t.replace(a, b)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([,.])", r"\1", t).strip(" ,")
    return t


class Speaker:
    def __init__(self, enabled=False, rate=1):
        self.enabled = enabled
        self.rate = rate          # -10 … 10
        self.p = None
        self.lock = threading.Lock()
        self.last = ""

    def _ensure(self):
        if self.p and self.p.poll() is None:
            return True
        if not IS_WIN:
            return False
        try:
            script = _PS.replace("__RATE__", str(int(self.rate)))
            enc = base64.b64encode(script.encode("utf-16-le")).decode()
            self.p = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-EncodedCommand", enc],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=NO_WINDOW)
            return True
        except OSError:
            self.p = None
            return False

    def _send(self, line):
        with self.lock:
            if not self._ensure():
                return
            try:
                self.p.stdin.write((line + "\n").encode("ascii"))
                self.p.stdin.flush()
            except (OSError, ValueError):
                self.p = None

    def say(self, text, interrupt=True, force=False):
        if not (self.enabled or force) or not text:
            return
        t = clean(text)
        if not t:
            return
        self.last = t
        if IS_WIN:
            self._send(("" if interrupt else "+") + base64.b64encode(t.encode("utf-8")).decode())
        else:
            try:
                if sys.platform == "darwin":
                    if interrupt:
                        subprocess.run(["killall", "say"], capture_output=True)
                    subprocess.Popen(["say", t])
                else:
                    if interrupt:
                        subprocess.run(["spd-say", "-C"], capture_output=True)
                    subprocess.Popen(["spd-say", "-l", "de", "-r", str(self.rate * 10), t])
            except OSError:
                pass

    def repeat(self):
        self.say(self.last, force=True)

    def stop(self):
        if IS_WIN and self.p and self.p.poll() is None:
            self._send("!STOP")

    def set_rate(self, rate):
        self.rate = max(-10, min(10, int(rate)))
        if IS_WIN and self.p and self.p.poll() is None:
            self._send(f"!RATE {self.rate}")

    def warmup(self):
        if IS_WIN:
            threading.Thread(target=lambda: self._send("!STOP"), daemon=True).start()

    def close(self):
        if self.p and self.p.poll() is None:
            try:
                self.p.stdin.close()
                self.p.terminate()
            except OSError:
                pass
        self.p = None
