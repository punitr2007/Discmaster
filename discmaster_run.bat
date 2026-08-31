@echo off
:: discmaster_run.bat
:: Windows launcher for DiscMaster

title DiscMaster Launcher

:: Check if python is in PATH
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python 3 was not detected on your system.
    echo Please install Python from https://www.python.org/ or the Microsoft Store.
    echo.
    pause
    exit /b 1
)

:: Run discmaster.py without displaying a console window
start pythonw "%~dp0discmaster.py"
exit /b 0
