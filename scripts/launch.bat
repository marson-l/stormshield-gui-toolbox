@echo off
echo ============================================
echo    Stormshield CLI GUI - Launcher
echo ============================================
echo.

echo Checking virtual environment...
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run scripts\setup.bat first
    pause
    exit /b 1
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Launching Stormshield CLI GUI...
python src\main_gui.py

echo.
echo Application closed.
pause
