@echo off
setlocal
cd /d "%~dp0"

call "%~dp0build-portable.bat"
if errorlevel 1 exit /b 1

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if defined ISCC goto compile_installer
echo Inno Setup 6 compiler was not found in its standard install locations.
set /p "ISCC=Path to ISCC.exe: "
set "ISCC=%ISCC:"=%"
if exist "%ISCC%" goto compile_installer
echo Inno Setup compiler not found: %ISCC%
pause
exit /b 1

:compile_installer
"%ISCC%" "%~dp0installer.iss"
if errorlevel 1 (
    echo Installer build failed.
    pause
    exit /b 1
)

echo.
echo Installer created at:
echo %~dp0dist\AtomLite-Setup.exe
pause
