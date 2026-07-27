"""Felles logg-oppsett. Skriver til både konsoll og logs/<navn>.log.

Bruk: `log = get_logger("pipeline")` og deretter log.info(...) / log.error(...).
Loggfilene spores ikke av git (se .gitignore: *.log).
"""
import logging
import os

from config import LOG_DIR


def get_logger(navn: str) -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger(navn)
    if logger.handlers:  # unngå doble handlers ved gjentatte kall
        return logger
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    fil = logging.FileHandler(os.path.join(LOG_DIR, f"{navn}.log"), encoding="utf-8")
    fil.setFormatter(fmt)
    logger.addHandler(fil)

    konsoll = logging.StreamHandler()
    konsoll.setFormatter(fmt)
    logger.addHandler(konsoll)

    return logger
