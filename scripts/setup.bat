@echo off
echo ============================================
echo    Stormshield CLI GUI - Setup Script
echo ============================================
echo.

echo [1/4] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)
echo  Python found

echo.
echo [2/4] Creating virtual environment...
if exist "venv" (
    echo Virtual environment already exists, removing old one...
    rmdir /s /q venv
)
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)
echo  Virtual environment created

echo.
echo [3/4] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [4/4] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo  Dependencies installed

echo.
echo ============================================
echo          Setup completed successfully!
echo ============================================
echo.
echo To launch the application, run:
echo   scripts\launch.bat
echo.
echo Or manually:
echo   venv\Scripts\activate.bat
echo   python src\main_gui.py
echo.
pause
