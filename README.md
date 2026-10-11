# Atom Lite

Atom Lite generates GULP input for rock salt oxides, runs volume scans, fits an
equation of state, and displays the fitted graph and crystal structure.

## Run from source on Windows

1. Install Python 3 with Tkinter support and install GULP separately.
2. Edit `settings.txt` and set `GULP_PATH` to that computer's `gulp.exe` path. If
   `settings.txt` is missing, copy `settings.example.txt` to `settings.txt`.
3. Run `setup.bat` once to create the local `.venv` and install Python packages.
4. Run `start.bat` to open the app.

When moving the source project to another computer, copy the project folder and
repeat steps 1–4 there. Do not copy `.venv`; Python virtual environments contain
computer-specific paths. App assets use paths relative to the project folder.

## Project layout

```text
app.py                  Application entry point
atom_lite/              UI, calculation engine, and settings
assets/                 Logo, icon, fonts, GULP library, and fit templates
data/                   Sample structures and local calculation data
docs/                   Project documentation
examples/               Standalone Gnuplot example
CONTRIBUTING.md          Contributor setup and workflow
logs/                   Local application diagnostics (created at runtime)
requirements.txt         Runtime Python dependencies
settings.example.txt     Safe template for the local GULP setting
setup.bat                Creates the local Python environment
start.bat                Starts the source app without a terminal window
```

GULP is not bundled. Use a licensed GULP installation and point `settings.txt`
to its executable. `settings.txt` is local machine configuration and is
excluded from version control; `settings.example.txt` is the safe template.

## Build for Windows

Build on a Windows computer. The build scripts find Python on `PATH` with a
working Tkinter, create a separate `.build-venv`, and install the packaging
dependencies there. The target computer does not need Python or Tcl/Tk.

### Portable folder and ZIP

1. Run `build-portable.bat`.
2. Find the build at `dist/Atom Lite/` and the ZIP at
   `dist/Atom-Lite-portable.zip`.
3. Copy and extract the ZIP on the target computer. Keep the extracted `Atom
   Lite` folder together.
4. Edit `settings.txt` beside `Atom Lite.exe` and set `GULP_PATH` to that
   computer's licensed `gulp.exe`, then launch `Atom Lite.exe`.

The portable app keeps generated inputs, outputs, results, structures, and
logs inside its folder. GULP is not included and must be available separately.

### Installer

1. Install Inno Setup 6 on the build computer.
2. Run `build-installer.bat`. It builds the app and creates
   `dist/AtomLite-Setup.exe`.
3. Run that setup file on the target computer, choose the installation
   location, and browse to its licensed `gulp.exe`. Setup will not continue
   unless the selected file exists and is named `gulp.exe`.
4. Launch Atom Lite from the Start menu or optional desktop shortcut.

The installer saves the GULP path in
`%LOCALAPPDATA%\AtomLite\settings.txt`, so no manual configuration is needed
after setup. GULP is not included; each target computer needs access to a
licensed installation. Inno Setup and PyInstaller are only needed on the
Windows build computer.

## GitHub notes

Local settings, generated inputs/results, logs, Python environments, and build
outputs are excluded by `.gitignore`. The sample CIF structures in
`data/snapshots/` are kept in the source tree. Review the bundled GULP library
and all third-party assets' redistribution terms before publishing. This project
does not currently declare a software license; add a license that matches your
intended use before inviting reuse or redistribution.
