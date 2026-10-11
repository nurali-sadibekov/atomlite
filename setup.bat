@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv ".venv"
    ) else (
        where python >nul 2>nul
        if errorlevel 1 (
            echo Python 3 is required. Install Python 3 with Tk support, then run setup.bat again.
            pause
            exit /b 1
        )
        python -m venv ".venv"
    )
    if errorlevel 1 (
        echo Could not create the local Python environment.
        pause
        exit /b 1
    )
)

"%~dp0.venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo Dependency installation failed. Check your internet connection and setup log above.
    pause
    exit /b 1
)

echo Setup complete. Edit settings.txt to set GULP_PATH, then launch start.bat.
pause
