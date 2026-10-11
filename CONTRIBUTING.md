# Contributing

## Development setup

1. Install a supported Python 3 release with Tkinter on Windows.
2. Run `setup.bat` to create the local environment and install application
   dependencies.
3. Copy `settings.example.txt` to `settings.txt` and set `GULP_PATH` to a
   licensed GULP executable, or make `gulp.exe` available on `PATH`.
4. Run `start.bat`.

Keep machine-specific settings, generated calculation output, virtual
environments, and build artifacts out of commits. Keep reusable templates,
source code, and sample structures in the repository. Describe user-visible
changes and include focused reproduction steps when reporting defects.

## Building Windows packages

See the Windows build instructions in `README.md`. Builds require a Windows
Python installation with working Tkinter; installer creation additionally
requires Inno Setup 6.
