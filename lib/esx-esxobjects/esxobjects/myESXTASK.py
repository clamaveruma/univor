#!/bin/python
"""This file manages high level operations on Vmware ESX Tasks."""

import logging
from typing import Optional
mylogger = logging.getLogger()

from .myESXError import myESXError, myESXWarning

from pyVmomi import vim
import time

class myESXTASK():
    """Class to handle basic operations on tasks like waiting for it to end."""
    def __init__(self, task:vim.Task, wait:bool = False, answer = None, timeout:float = None, poll_interval:float = 1.0):
        self.task:vim.Task = task
        self.answer = answer
        if wait:
            self.wait(task, timeout, poll_interval)

    def wait(self, answer = None, timeout_seconds:float = None, poll_interval:float = 1.0) -> vim.TaskInfo:
        """
        Waits for a VMware ESX task to complete within a specified timeout.

        :param answer: Function to call when waiting for tasks over VMs to answer questions.
        :param timeout_seconds: Maximum time to wait for the task to complete, in seconds.
        :type timeout_seconds: float
        :param poll_inrteval: Time to sleep between polls. Default is 1s.
        :type poll_inrteval: float
        
        :return: The task result if completed, None if the task did not complete within the timeout.
        :rtype: vim.TaskInfo or None
        """
        if answer:
            self.answer = answer
        # Starting time of task
        start_time = time.time()
        # Poll until task ends
        while not self.isEnded():
            # Print progress if possible
            if self.task.info.progress != None and self.task.info.progress != "":
                mylogger.debug(f"Waiting for task {self.task.info.name} ({self.task.info.description}): {self.task.info.progress}%")
            else:
                mylogger.debug(f"Waiting for task {self.task.info.name} ({self.task.info.description})")
            # If answer handler was specified then answer questions
            if self.answer:
                self.answer()
            # If timeout was specified then check if exceeded            
            if timeout_seconds != None:
                if time.time() - start_time > timeout_seconds:
                    raise myESXWarning(f"Task {self.task.info.name} ({self.task.info.description}) didn't end before timeout expired.")
            # Sleep for before checking again
            time.sleep(poll_interval)

        if self.task.info.state == vim.TaskInfo.State.success:
            return self.task.info
        else:
            mylogger.error(f"Task failed with error: {self.getError()}")
            return None

    def getName(self) -> str:
        """Returns the name of the task.

        :return: A string with the name of the task.
        """
        return self.task.info.name

    def getError(self) ->Optional[str]:
        """Returns description of the error.

        :return: A string describing the error.
        """
        if self.isFailed():
            return self.task.info.error.msg
        else:
            return None

    def isEnded(self) -> bool:
        """Checks if task ended

        :return: True if task ended.
        """
        return self.task.info.state in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]

    def isOK(self) -> bool:
        """Checks if task succeedded.

                :return: True if result was success.
        """
        return self.task.info.state == vim.TaskInfo.State.success
    
    def isFailed(self) -> bool:
        """Checks if task failed.

        :return: True if result was error.
        """
        return self.task.info.state == vim.TaskInfo.State.error
    
