# Vytvoř run_gui.bat v root projektu
@"
@echo off
REM NightChronicles Studio GUI Launcher
echo Starting NightChronicles Studio GUI...
call .venv\Scripts\activate.bat
python -m studio_gui.src.main
pause
"@ | Out-File -FilePath run_gui.bat -Encoding ascii
