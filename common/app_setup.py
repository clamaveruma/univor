"""
common/app_setup.py
--------------------
Reusable logging and print setup for all parts of the project.

Usage:
    from common.app_setup import setup_logging, set_print_logger, monkeypatch_print, print_and_log, print_error
    logger = setup_logging(app_name="univor", daemon=False)
    set_print_logger(logger)
    monkeypatch_print()
    print_and_log("Info message")
    print_error("Error message")
"""

import logging
import logging.handlers
import os
from typing import Optional
import builtins
import typer
import sys

# Module-level variable to hold the logger for print_and_log and print_error
_monkeypatch_logger = None

def setup_logging(app_name: str = "univor", daemon: bool = False, loglevel: int = logging.INFO, logfile: Optional[str] = None):
    """
    Set up logging for the application.
    - If daemon=True, logs to syslog (Linux only).
    - Otherwise, logs to a file in ~/.<app_name>/log.txt or to a custom logfile.
    Returns the configured logger.
    """
    logger = logging.getLogger()
    logger.setLevel(loglevel)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(process)d %(message)s')

    # Remove any existing handlers
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    handler: logging.Handler
    if daemon:
        try:
            handler = logging.handlers.SysLogHandler(address='/dev/log')
        except Exception:
            handler = logging.StreamHandler()
    else:
        if logfile is None:
            log_dir = os.path.expanduser(f"~/.{app_name}")
            os.makedirs(log_dir, exist_ok=True)
            logfile = os.path.join(log_dir, "log.txt")
        handler = logging.FileHandler(logfile)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def set_print_logger(logger: logging.Logger):
    """
    Set the logger to be used by print_and_log and print_error.
    Call this after setting up logging in your app.
    """
    global _monkeypatch_logger
    _monkeypatch_logger = logger

def monkeypatch_print():
    """
    Monkeypatch built-in print to use typer.echo only (no logging).
    """
    def print_to_typer(*args, **kwargs):
        sep = kwargs.get('sep', ' ')
        end = kwargs.get('end', '\n')
        file = kwargs.get('file', sys.stdout)
        message = sep.join(str(arg) for arg in args) + end
        if file == sys.stderr:
            typer.echo(message, err=True, nl=False)
        else:
            typer.echo(message, nl=False)
    builtins.print = print_to_typer     # monkeypatch print

def print_and_log(message: str):
    """
    Print to console (via print) and log as info.
    """
    print(message)
    if _monkeypatch_logger is not None:
        _monkeypatch_logger.info(message)

def print_error(message: str):
    """
    Print and log an error message (stderr and error level), using the logger set by set_print_logger.
    """
    typer.echo(message, err=True)
    if _monkeypatch_logger is not None:
        _monkeypatch_logger.error(message)
