from __future__ import annotations
import os, sys, traceback
from datetime import datetime, timezone
from loguru import logger
from .paths import logs_dir
def install_exception_hook():
    def handle(exc_type, exc_value, exc_tb):
        text="".join(traceback.format_exception(exc_type,exc_value,exc_tb))
        logger.critical("Unhandled desktop exception\n{}",text)
        (logs_dir()/"crash.log").write_text(f"{datetime.now(timezone.utc).isoformat()}\nPID={os.getpid()}\n{text}",encoding="utf-8")
        if sys.__excepthook__: sys.__excepthook__(exc_type,exc_value,exc_tb)
    sys.excepthook=handle
