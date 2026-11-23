@echo off
title InstaStudio Server
cd /d "%~dp0"
echo ========================================================
echo          INSTASTUDIO LOCAL BACKEND & FRONTEND
echo ========================================================
echo.
echo PC Browser:     http://localhost:5000/login
echo Mobile (Wi-Fi): http://192.168.43.102:5000/login
echo.
echo Keys Panel:     http://localhost:5000/keys-panel
echo.
start http://localhost:5000/login
python server.py
pause
