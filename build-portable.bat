@echo off
setlocal
cd /d "%~dp0"

set "BUILD_PYTHON="
set "BUILD_BASE_PYTHON="

if exist "%~dp0.build-venv\bin\python.exe" set "BUILD_PYTHON=%~dp0.build-venv\bin\python.exe"
if not defined BUILD_PYTHON if exist "%~dp0.build-venv\Scripts\python.exe" set "BUILD_PYTHON=%~dp0.build-venv\Scripts\python.exe"

if not defined BUILD_PYTHON (
    for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined BUILD_BASE_PYTHON set "BUILD_BASE_PYTHON=%%P"
)

if defined BUILD_BASE_PYTHON "%BUILD_BASE_PYTHON%" -c "import tkinter; root=tkinter.Tk(); root.withdraw(); root.update(); root.destroy()" >nul 2>nul
if errorlevel 1 set "BUILD_BASE_PYTHON="
if not defined BUILD_BASE_PYTHON if exist "%~dp0.venv\Scripts\python.exe" set "BUILD_BASE_PYTHON=%~dp0.venv\Scripts\python.exe"

if defined BUILD_BASE_PYTHON goto base_python_ready
echo No working Tkinter Python was found on PATH.
set /p "BUILD_BASE_PYTHON=Full path to the Python that opens Tkinter: "
set "BUILD_BASE_PYTHON=%BUILD_BASE_PYTHON:"=%"
if not exist "%BUILD_BASE_PYTHON%" goto invalid_python_path
"%BUILD_BASE_PYTHON%" -c "import tkinter; root=tkinter.Tk(); root.withdraw(); root.update(); root.destroy()" >nul 2>nul
if errorlevel 1 goto invalid_tk_python

:base_python_ready

if not defined BUILD_PYTHON (
    "%BUILD_BASE_PYTHON%" -m venv --without-pip "%~dp0.build-venv"
    if errorlevel 1 (
        echo Could not create the local build environment.
        pause
        exit /b 1
    )
    if exist "%~dp0.build-venv\bin\python.exe" (
        set "BUILD_PYTHON=%~dp0.build-venv\bin\python.exe"
    ) else (
        set "BUILD_PYTHON=%~dp0.build-venv\Scripts\python.exe"
    )
    "%BUILD_PYTHON%" -m ensurepip --upgrade
    if errorlevel 1 (
        echo Could not initialize pip in the local build environment.
        pause
        exit /b 1
    )
)

"%BUILD_PYTHON%" -m pip install --disable-pip-version-check -r "%~dp0requirements-build.txt"
if errorlevel 1 (
    echo Could not install the build dependencies.
    pause
    exit /b 1
)

if not exist "%~dp0build\spec" mkdir "%~dp0build\spec"
"%BUILD_PYTHON%" -m PyInstaller --noconfirm --clean --onedir --windowed --name "AtomLite" --icon "%~dp0assets\app.ico" --add-data "%~dp0assets;assets" --collect-all customtkinter --distpath "%~dp0dist" --workpath "%~dp0build\pyinstaller" --specpath "%~dp0build\spec" "%~dp0app.py"
if errorlevel 1 (
    echo Portable build failed. Review the PyInstaller output above.
    pause
    exit /b 1
)

set "PORTABLE_DIR=%~dp0dist\AtomLite"
if not exist "%PORTABLE_DIR%\settings.txt" copy "%~dp0settings.example.txt" "%PORTABLE_DIR%\settings.txt" >nul
type nul > "%PORTABLE_DIR%\portable.mode"
for %%D in (inputs outputs results snapshots) do if not exist "%PORTABLE_DIR%\data\%%D" mkdir "%PORTABLE_DIR%\data\%%D"
if not exist "%PORTABLE_DIR%\logs" mkdir "%PORTABLE_DIR%\logs"
copy "%~dp0README-PORTABLE.txt" "%PORTABLE_DIR%\README.txt" >nul
set "PORTABLE_ZIP=%~dp0dist\AtomLite-portable.zip"
powershell.exe -NoProfile -Command "Compress-Archive -Path $env:PORTABLE_DIR -DestinationPath $env:PORTABLE_ZIP -Force"
if errorlevel 1 (
    echo Could not create the portable ZIP archive.
    pause
    exit /b 1
)

echo.
echo Portable app created at:
echo %PORTABLE_DIR%
echo Portable ZIP created at:
echo %PORTABLE_ZIP%
echo Edit settings.txt there to set GULP_PATH, then run "AtomLite.exe".
pause
goto :eof

:invalid_python_path
echo Python executable not found. Paste the path to the Python that opens Tkinter.
pause
exit /b 1

:invalid_tk_python
echo This Python does not have a working Tcl/Tk runtime.
pause
exit /b 1

