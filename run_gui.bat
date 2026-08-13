@echo off
REM S2P Tool - GUI Launcher
REM Runs the GUI from source code

title S2P Tool - Model Generator
cls

echo.
echo ====================================
echo  S2P Tool - SPICE Model Generator
echo ====================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo.
    echo Please install Python 3.8+ from:
    echo   https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [*] Python detected
python --version

REM Check if requirements are installed
echo.
echo [*] Checking dependencies...
python -c "import PyQt5; import numpy" >nul 2>&1
if errorlevel 1 (
    echo [!] Dependencies missing, installing...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
)

echo [*] Dependencies OK
echo.
echo [*] Starting GUI...
echo.

REM Run the GUI
python gui_main.py

if errorlevel 1 (
    echo.
    echo [ERROR] GUI failed to start
    echo.
    pause
)

exit /b 0
