@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo  Building Standalone KesCollah.exe (No-Install Bundle)
echo ========================================================
echo.

python -m PyInstaller --noconsole --onefile --icon=assets/icon.ico --add-data "assets;assets" --name KesCollah main.py

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================================
    echo  SUCCESS! Your standalone app is ready at:
    echo  dist\KesCollah.exe
    echo ========================================================
) else (
    echo.
    echo [ERROR] Build failed. Please ensure PyInstaller and PyQt6 are installed.
)

pause
