"""
logger.py — Logging estructurado a consola y archivo rotativo.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_logger(name: str = "rca_extractor", log_file: Path | None = None) -> logging.Logger:
    """
    Retorna un logger configurado con:
      - Handler de consola con colores simples (nivel INFO+).
      - Handler de archivo rotativo (nivel DEBUG+), si se indica log_file.
    """
    logger = logging.getLogger(name)

    if logger.handlers:          # evitar duplicar handlers en reimports
        return logger

    logger.setLevel(logging.DEBUG)

    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    # ── Consola ───────────────────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(fmt, datefmt=date_fmt))
    logger.addHandler(console_handler)

    # ── Archivo ───────────────────────────────────────────────────────────────
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(fmt, datefmt=date_fmt))
        logger.addHandler(file_handler)

    return logger
