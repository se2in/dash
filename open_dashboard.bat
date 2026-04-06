@echo off
cd /d %~dp0
python -m pip install -r requirements.txt
python update_dashboard.py
start index.html
