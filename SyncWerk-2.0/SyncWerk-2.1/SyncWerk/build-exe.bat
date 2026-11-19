@echo off
setlocal
cd /d "%~dp0"
title SyncWerk 2.1 - EXE erstellen
echo.
echo  ==================================================
echo     SyncWerk 2.1  -  Standalone-EXE erstellen
echo  ==================================================
echo.

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto :nopython
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" || goto :nopython
%PY% -c "import tkinter" 2>nul || goto :notk

echo [1/4] Virtuelle Umgebung .venv vorbereiten ...
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv || goto :err
set "VPY=.venv\Scripts\python.exe"

echo [2/4] PyInstaller installieren ...
%VPY% -m pip install --upgrade pip --quiet
%VPY% -m pip install -r requirements.txt --quiet || goto :err

echo [3/4] Alte Build-Ordner entfernen ...
if exist build rmdir /s /q build
if exist dist\SyncWerk.exe del /q dist\SyncWerk.exe

echo [4/4] SyncWerk.exe wird gebaut - das dauert 1-2 Minuten ...
%VPY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name SyncWerk ^
  --icon assets\SyncWerk.ico ^
  --add-data "assets;assets" ^
  --version-file version_info.txt ^
  SyncWerk.py || goto :err

echo.
echo  FERTIG:  %CD%\dist\SyncWerk.exe
echo  Die EXE ist eigenstaendig und kann beliebig kopiert werden.
echo.
start "" explorer "%CD%\dist"
pause
exit /b 0

:nopython
echo  Python 3.9 oder neuer wurde nicht gefunden.
echo  Bitte von https://www.python.org installieren und dabei
echo  "Add python.exe to PATH" anhaken.
pause
exit /b 1

:notk
echo  Python ist installiert, aber ohne tkinter.
echo  Python-Installer erneut starten - Modify - "tcl/tk and IDLE" anhaken.
pause
exit /b 1

:err
echo.
echo  FEHLER beim Erstellen - bitte die Meldungen oben pruefen.
pause
exit /b 1
