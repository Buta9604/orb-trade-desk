@echo off
rem Windows: double-click to start the ORB Trade Desk at http://localhost:8787
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
where py >nul 2>nul && (py -3 desk\serve_desk.py %* & goto done)
where python >nul 2>nul && (python desk\serve_desk.py %* & goto done)
echo Python 3 is not installed. Install it from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH" in the installer), then double-click this file again.
:done
pause
