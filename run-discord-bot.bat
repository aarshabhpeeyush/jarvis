@echo off
cd /d "%~dp0"
echo.
echo  Installing discord.py...
pip install discord.py anthropic python-dotenv --quiet
echo.
echo  Starting Jarvis Discord Bot...
echo  Keep this window open. Press Ctrl+C to stop.
echo.
python discord_bot.py
pause
