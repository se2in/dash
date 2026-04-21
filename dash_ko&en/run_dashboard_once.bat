@echo off
setlocal
cd /d "%~dp0"
python update_dashboard.py all --config config.json
pause
