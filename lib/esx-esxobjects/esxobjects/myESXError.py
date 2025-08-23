#!/bin/python
"""This file defines a custom exception for myESX library modules"""

import logging
mylogger = logging.getLogger()

class myESXError(Exception):
    """Custom exception with a message."""
    def __init__(self, message="An ESXAPI error occurred", log = False):
        self.message = message
        super().__init__(self.message)
        if log:
            mylogger.error(message)

class myESXWarning(Exception):
    """Custom exception with a message."""
    def __init__(self, message="An ESXAPI error occurred", log = False):
        self.message = message
        super().__init__(self.message)
        if log:
            mylogger.warning(message)
