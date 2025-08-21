@echo off
echo ============================================
echo    Stormshield CLI GUI - Build Script
echo ============================================
echo.

echo [1/5] Checking virtual environment...
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run scripts\setup.bat first
    pause
    exit /b 1
)

echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [3/5] Installing build dependencies...
pip install pyinstaller

echo.
echo [4/5] Cleaning previous build...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

echo.
echo [5/5] Building executable...
pyinstaller --onefile --windowed --name "Stormshield_Tools" --icon=assets\icon.ico src\main_gui.py

if exist "dist\Stormshield_Tools.exe" (
    echo.
    echo ============================================
    echo           Build completed successfully!
    echo ============================================
    echo.
    echo Executable created at: dist\Stormshield_Tools.exe
    echo.
) else (
    echo.
    echo ERROR: Build failed!
    echo.
)

pause
