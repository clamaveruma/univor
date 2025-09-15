"""
Reusable logging and print setup for all parts of the project.

Functions:
    setup_logging      - Configure and return a logger.
    set_print_logger   - Set the logger for print_and_log and print_error.
    monkeypatch_print  - Replace built-in print with rich print.
    print_and_log      - Print and log an info message.
    print_error        - Print and log an error message.
"""

import logging
import logging.handlers
import os
from typing import Optional
import builtins
from rich import print as rich_print
import sys

# Module-level variable to hold the logger for print_and_log and print_error
_print_logger = None

def setup_logging(app_name: str = "univor", daemon: bool = False, loglevel: int = logging.INFO, logfile: Optional[str] = None) -> logging.Logger:
    """
    Set up logging for the application.
    - If daemon=True, logs to syslog (Linux only).
    - Otherwise, logs to a file in ~/.<app_name>/log.txt or to a custom logfile.
    Returns the configured logger.
    """
    logger = logging.getLogger()
    logger.setLevel(loglevel)
    from logging import Handler
    if daemon:
        formatter = logging.Formatter(f'%(asctime)s %(levelname)s %(process)d [{app_name}] %(message)s')
        try:
            handler: Handler = logging.handlers.SysLogHandler(address='/dev/log')
            print("[DEBUG] SysLogHandler set up for /dev/log", file=sys.stderr)
        except Exception as e:
            print(f"[DEBUG] Failed to set up SysLogHandler: {e}", file=sys.stderr)
            handler = logging.StreamHandler()
    else:
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(process)d %(message)s')
        if logfile is None:
            log_dir = os.path.expanduser(f"~/.{app_name}")
            os.makedirs(log_dir, exist_ok=True)
            logfile = os.path.join(log_dir, "log.txt")
        handler = logging.FileHandler(logfile)

    # Remove any existing handlers
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    set_print_logger(logger)
    logger.info("[DEBUG] Logger initialized and test message from setup_logging.")
    return logger

def set_print_logger(logger: logging.Logger):
    """
    Set the logger to be used by print_and_log and print_error.
    Call this after setting up logging in your app.
    """
    global _print_logger
    _print_logger = logger
    print(f"[DEBUG] set_print_logger called: logger={logger!r}", file=sys.stderr)

def monkeypatch_print():
    """
    Monkeypatch built-in print to use rich.print for all output (no logging).
    """
    def print_to_rich(*args, **kwargs):
        rich_print(*args, **kwargs)
    builtins.print = print_to_rich  # monkeypatch print


def print_and_log(message: str, **kwargs):
    """
    Print to console (via print) and log as info.
    """
    print(message, **kwargs)
    print(f"[DEBUG] print_and_log: _print_logger={_print_logger!r}", file=sys.stderr)
    if _print_logger is not None:
        _print_logger.info(message)
        print(f"[DEBUG] print_and_log: logged '{message}' to logger", file=sys.stderr)

def print_error(message: str, **kwargs):
    """
    Print and log an error message (stderr and error level), using the logger set by set_print_logger.
    """
    print(f'[bold red]{message}[/bold red]', file=sys.stderr, **kwargs)
    if _print_logger is not None:
        _print_logger.error(message)
