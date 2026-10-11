"""AtomLite application entry point with startup diagnostics."""

import logging
from logging.handlers import RotatingFileHandler
from tkinter import messagebox

from atom_lite.config import LOG_DIR

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    handlers=[RotatingFileHandler(LOG_DIR / "app.log", maxBytes=1_000_000,
                                  backupCount=3, encoding="utf-8")],
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

if __name__ == "__main__":
    try:
        from atom_lite.ui import main

        main()
    except Exception as exc:
        logging.exception("AtomLite failed during startup")
        messagebox.showerror(
            "AtomLite could not start",
            f"The app encountered a startup error. Details are in {LOG_DIR / 'app.log'}.\n\n{exc}",
        )
