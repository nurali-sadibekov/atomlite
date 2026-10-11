# Development notes

The application is split into three layers:

- `atom_lite/config.py` owns portable paths and the per-computer GULP setting.
- `atom_lite/engine.py` owns input generation, GULP process execution, data
  parsing, fitting, and scientific calculations.
- `atom_lite/ui.py` owns Tk and CustomTkinter widgets and rendering.
- `app.py` configures rotating diagnostics and starts the interface.

Generated data lives under `data/`; reusable inputs and visual assets live
under `assets/`. GULP runs with the project root as its working directory so
its input file can refer to the bundled library and output folders by relative
path. The executable is resolved from `settings.txt` or the operating system's
`PATH`. Process invocation uses an argument list and does not invoke a shell.

`script.py` remains as a small compatibility entry point. New launchers should
use `app.py` or `start.bat`.
