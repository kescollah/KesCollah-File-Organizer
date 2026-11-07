@echo off
setlocal
cd /d "%~dp0"

:: Check if standalone executable exists
if exist "dist\KesCollah.exe" (
    start "" "dist\KesCollah.exe"
    exit /b 0
)

:: Otherwise run with Python without console window
where pythonw >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" pythonw main.py
    exit /b 0
)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python main.py
    exit /b 0
)

where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py main.py
    exit /b 0
)

echo [ERROR] Python not found on this computer.
pause
