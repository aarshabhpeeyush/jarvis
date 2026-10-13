@echo off
cd /d "%~dp0"
set PYTHON=C:\Users\Peeyush\AppData\Local\Programs\Python\Python311\python.exe
echo Installing / updating dependencies...
"%PYTHON%" -m pip install -r requirements.txt -q
echo.
echo Starting J.A.R.V.I.S. ...
start "" "http://localhost:8181/jarvis.html"
"%PYTHON%" server.py
pause
