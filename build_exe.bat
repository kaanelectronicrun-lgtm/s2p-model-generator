@echo off
REM S2P Tool - EXE Builder for Windows
REM Creates releases/s2p-<version>-win64.exe

title S2P Tool - EXE Builder
cls

echo.
echo ====================================
echo  S2P Tool - EXE Builder
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

REM Check Python version (3.8+)
python -c "import sys; exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.8+ required
    pause
    exit /b 1
)

echo [*] Python version OK
echo.

REM Install/upgrade requirements
echo [*] Installing dependencies (this may take a few minutes)...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo [*] Dependencies installed
echo.

REM Run build script
echo [*] Building executable...
echo.
python build_exe.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo.
echo [OK] Build completed successfully!
echo.
echo The executable is located at:
echo   releases\s2p-*-win64.exe
echo.
pause
exit /b 0
