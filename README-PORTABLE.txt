Atom Lite portable build

Portable folder use:

1. Keep the entire folder together when moving the app to another computer.
2. Set GULP_PATH in settings.txt to the location of that computer's gulp.exe.
3. Run "Atom Lite.exe". Python does not need to be installed on the target PC.

For a guided installation, use AtomLite-Setup.exe instead. The installer asks
for the installation location and validates the selected gulp.exe itself.

Build instructions for the portable package and installer are in README.md.

Generated inputs, outputs, results, structures, and logs are stored in folders
beside the executable. The GULP executable is not included in this package.
The package must be built on Windows using a Python installation with a
working Tcl/Tk runtime. If prompted during the build, enter the full path to
that Python's python.exe.
