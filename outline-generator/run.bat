@echo off
cd /d D:\NightChronicles\outline-generator
call venv\Scripts\activate
python generate_outline.py --parallel
pause
