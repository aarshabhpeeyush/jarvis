@echo off
cd /d "%~dp0"
start "" "http://localhost:8181/jarvis.html"
python server.py
