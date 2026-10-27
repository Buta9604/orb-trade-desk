@echo off
rem Install the 11 trader-* skills for Claude Code (personal skills folder).
cd /d "%~dp0"
if not exist "%USERPROFILE%\.claude\skills" mkdir "%USERPROFILE%\.claude\skills"
for /d %%S in (skills\trader-*) do xcopy /e /i /y "%%S" "%USERPROFILE%\.claude\skills\%%~nxS" >nul
echo Installed the trader skills to %USERPROFILE%\.claude\skills
where py >nul 2>nul || echo Python not found: install it from python.org (3.8 or newer).
echo Next: py desk\run_desk.py --scan skip   (creates trader\config.json; edit your limits)
pause
