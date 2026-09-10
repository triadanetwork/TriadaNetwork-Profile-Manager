from __future__ import annotations
import os
import sys
from pathlib import Path
from loguru import logger
from .paths import logs_dir
def configure_logging(verbose: bool=False) -> Path:
    logger.remove(); level="DEBUG" if verbose else "INFO"
    if os.getenv("TRIADA_DESKTOP_STDERR") == "1" and getattr(sys,"stderr",None) is not None:
        logger.add(sys.stderr,level=level,enqueue=True,backtrace=False,diagnose=False)
    path=logs_dir()/"app.log"
    logger.add(path,rotation="10 MB",retention="14 days",compression="zip",encoding="utf-8",level="DEBUG",enqueue=True,backtrace=False,diagnose=False)
    return Path(path)
