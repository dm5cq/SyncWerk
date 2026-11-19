@echo off
cd /d "%~dp0"
where py >nul 2>nul && (py -3 SyncWerk.py) || (python SyncWerk.py)
