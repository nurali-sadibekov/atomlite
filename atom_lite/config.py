"""Portable application paths and user supplied GULP configuration."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


# In a PyInstaller one-folder build, immutable application resources live under
# _internal while settings and generated data stay beside AtomLite.exe.
if getattr(sys, "frozen", False):
    INSTALL_ROOT = Path(sys.executable).resolve().parent
    RESOURCE_ROOT = Path(sys._MEIPASS)
    if (INSTALL_ROOT / "portable.mode").is_file():
        APP_ROOT = INSTALL_ROOT
    else:
        LOCAL_APP_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        APP_ROOT = LOCAL_APP_DATA / "AtomLite"
else:
    APP_ROOT = Path(__file__).resolve().parent.parent
    RESOURCE_ROOT = APP_ROOT

ASSETS_DIR = RESOURCE_ROOT / "assets"
DATA_DIR = APP_ROOT / "data"
INPUT_DIR = DATA_DIR / "inputs"
OUTPUT_DIR = DATA_DIR / "outputs"
RESULT_DIR = DATA_DIR / "results"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
CONFIG_FILE = APP_ROOT / "settings.txt"
LOG_DIR = APP_ROOT / "logs"
LIBRARY_PATH = ASSETS_DIR / "bush.lib"
FONT_DIR = ASSETS_DIR / "fonts" / "ibm-plex-sans"
GNUPLOT_TEMPLATE = ASSETS_DIR / "templates" / "gnuplot-template.txt"
DEFAULT_LATTICE_STEP = 0.01
GULP_TIMEOUT_SECONDS = 300
CATION_SITES = (
    "0.000000   0.000000   0.000000",
    "0.000000   0.500000   0.500000",
    "0.500000   0.000000   0.500000",
    "0.500000   0.500000   0.000000",
)
OXYGEN_SITES = (
    "0.500000   0.500000   0.500000",
    "0.500000   0.000000   0.000000",
    "0.000000   0.500000   0.000000",
    "0.000000   0.000000   0.500000",
)
FIT_TEMPLATES = {
    "Linear": ASSETS_DIR / "templates" / "linear-template.txt",
    "Quadratic": ASSETS_DIR / "templates" / "quadratic-template.txt",
    "Third order": ASSETS_DIR / "templates" / "third-order-template.txt",
    "Murnaghan EOS": ASSETS_DIR / "templates" / "murnaghan-template.txt",
}


class ConfigurationError(ValueError):
    """Raised when required local application settings are missing or invalid."""


def resolve_gulp_executable() -> Path:
    """Resolve the GULP executable path from settings.txt or the system PATH."""
    configured_path = ""
    try:
        for line in CONFIG_FILE.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith(("#", ";")):
                continue
            key, separator, value = line.partition("=")
            if separator and key.strip().upper() == "GULP_PATH":
                configured_path = value.strip().strip('"')
                break
    except OSError as exc:
        raise ConfigurationError(
            f"Could not read {CONFIG_FILE.name} in {APP_ROOT}. Run the installer and select gulp.exe."
        ) from exc

    if not configured_path or configured_path.upper() in {"CHANGE_ME", "TODO"}:
        raise ConfigurationError(
            f"Set GULP_PATH in {CONFIG_FILE.name} to your GULP executable, "
            "or put gulp.exe on your system PATH."
        )

    expanded = os.path.expandvars(os.path.expanduser(configured_path))
    candidate = Path(expanded)
    if candidate.is_absolute():
        if candidate.is_file():
            return candidate.resolve()
    else:
        local_candidate = APP_ROOT / candidate
        if local_candidate.is_file():
            return local_candidate.resolve()
        path_candidate = shutil.which(expanded)
        if path_candidate:
            return Path(path_candidate).resolve()

    raise ConfigurationError(
        f"GULP executable not found: {configured_path}\n"
        f"Update GULP_PATH in {CONFIG_FILE.name}."
    )
