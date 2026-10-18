@echo off
REM ===================================================================
REM  ShopSphere - MCA Integrated Project
REM  Double-click this file to install dependencies and start the app.
REM ===================================================================
title ShopSphere - E-Commerce Web Application

echo.
echo  ============================================================
echo   ShopSphere  ^|  Flask + SQLite E-Commerce Application
echo  ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python is not installed or not on PATH.
    echo  Install Python 3.10+ from https://python.org and try again.
    pause
    exit /b 1
)

echo  Checking dependencies...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo  Installing Flask...
    python -m pip install -r requirements.txt
)

echo.
echo  Storefront :  http://127.0.0.1:5000
echo  Admin panel:  http://127.0.0.1:5000/admin
echo.
echo  Admin login:  admin@shopsphere.com / Admin@123
echo  User  login:  user@shopsphere.com  / User@123
echo.
echo  Press CTRL+C to stop the server.
echo.

start "" http://127.0.0.1:5000
python app.py
pause
