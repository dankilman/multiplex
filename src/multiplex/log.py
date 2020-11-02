import logging
import os
import tempfile


def init_logging(level=logging.INFO, log_path=None):
    formatter = logging.Formatter("{asctime} - {name:<20} - {levelname} - {message}", style="{")
    log_path = log_path or os.path.join(tempfile.gettempdir(), "multiplex.log")
    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger = logging.getLogger()
    for h in logger.handlers:
        logger.removeHandler(h)
    logger.setLevel(level)
    logger.addHandler(fh)
