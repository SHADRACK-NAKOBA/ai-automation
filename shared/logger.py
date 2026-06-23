"""
shared/logger.py
================
Centralized logging setup.

WHY: Every agent gets consistent, timestamped, colored console output.
     In production, swap StreamHandler for a file or cloud logging handler.
"""

import logging
import sys
from datetime import datetime


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger for a module."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger
