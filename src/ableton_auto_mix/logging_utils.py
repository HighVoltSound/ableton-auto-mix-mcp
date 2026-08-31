"""Structured logging and timing utilities for MusicMixCode backend."""

from __future__ import annotations

import logging
import os
import time
from functools import wraps
from typing import Any, Callable

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int | None = None) -> None:
    """Configure structured logging for the entire package.

    Call once at startup (from api_app or __main__).
    """
    if level is None:
        level_str = os.environ.get("MMC_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_str, logging.INFO)

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        force=True,
    )

    # Quiet noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("pythonosc").setLevel(logging.WARNING)
    logging.getLogger("scipy").setLevel(logging.WARNING)
    logging.getLogger("pyloudnorm").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a module-level logger."""
    return logging.getLogger(f"mmc.{name}")


class Timer:
    """Context manager that logs elapsed time."""

    def __init__(self, label: str, logger: logging.Logger | None = None):
        self.label = label
        self.logger = logger or get_logger("timer")
        self.start = 0.0
        self.elapsed = 0.0

    def __enter__(self) -> Timer:
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.elapsed = time.perf_counter() - self.start
        self.logger.info("%s completed in %.3fs", self.label, self.elapsed)


def timed(func: Callable) -> Callable:
    """Decorator that logs function execution time.

    Usage:
        @timed
        def my_function():
            ...
    """
    logger = get_logger("timing")

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            logger.info("%s executed in %.3fs", func.__qualname__, elapsed)
            return result
        except Exception:
            elapsed = time.perf_counter() - start
            logger.error("%s failed after %.3fs", func.__qualname__, elapsed)
            raise

    return wrapper  # type: ignore[return-value]


def log_call(
    logger: logging.Logger | None = None, level: int = logging.DEBUG
) -> Callable:
    """Decorator that logs function entry/exit with args summary.

    Usage:
        @log_call()
        def process(audio, sr):
            ...
    """
    _logger = logger or get_logger("calls")

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Summarize args (don't log huge arrays)
            arg_summary = []
            for a in args[:3]:  # first 3 positional
                if hasattr(a, "shape"):
                    arg_summary.append(f"ndarray{a.shape}")
                elif isinstance(a, (list, tuple)) and len(a) > 5:
                    arg_summary.append(f"{type(a).__name__}({len(a)} items)")
                else:
                    arg_summary.append(repr(a)[:80])

            _logger.log(level, "→ %s(%s)", func.__qualname__, ", ".join(arg_summary))
            try:
                result = func(*args, **kwargs)
                if hasattr(result, "shape"):
                    _logger.log(
                        level, "← %s → ndarray%s", func.__qualname__, result.shape
                    )
                elif isinstance(result, (list, tuple)) and len(result) > 5:
                    _logger.log(
                        level,
                        "← %s → %s(%d items)",
                        func.__qualname__,
                        type(result).__name__,
                        len(result),
                    )
                else:
                    _logger.log(
                        level, "← %s → %s", func.__qualname__, repr(result)[:80]
                    )
                return result
            except Exception as exc:
                _logger.error(
                    "✗ %s raised %s: %s", func.__qualname__, type(exc).__name__, exc
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator
