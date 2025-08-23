#!/usr/bin/python3
"""This module provides an object to implement several operations on VMWare ESX virtual machines using the pyvmomi API. This file is part if the myESX library."""

from typing import Optional, List, Tuple
from pyVmomi import vim

# Initialize logger
import logging

mylogger = logging.getLogger()

from .myESXTASK import myESXTASK
from .myESXError import myESXError, myESXWarning

import re, datetime, time

class myESXVM:
    """This object manages VM objects through a ESXAPI object"""

    def __init__(self, vm:vim.VirtualMachine):
        """Wrap a vim.VirtualMachine object with this object to provide high level functions.
        """
        self.vm:vim.VirtualMachine = vm

    def getName(self) -> str:
        """Get the label of the VM.
        
        Returns a string with the name of the VM."""
        return self.vm.name

    def rename(self, newName:str):
        """Set a new label for a VM.
        :param newName: A string with the new name for the VM.

        """
        # Prepare the VM reconfiguration spec
        spec = vim.vm.ConfigSpec()
        spec.name = newName
        # Rename the VM
        try:
            task = myESXTASK ( self.vm.Reconfigure(spec=spec) )
        except Exception as e:
            raise myESXError(f'Error renaming VM {self.vm.name}') from e

        return self.vm.name
    
    def reconfigRes(self, config:vim.vm.ConfigSpec) -> myESXTASK:
        """Changes configuration parameters of a VM.
        :param config: An myESXCONFIG object containing the changes to the configuration of the VM
        """
        # Reconfigure the VM
        try:
            task = myESXTASK ( self.vm.Reconfigure(spec=config) )
        except Exception as e:
            raise myESXError(f'Error reconfiguring VM {self.vm.name}') from e
        return task
    
    def getHost(self) -> vim.ComputeResource:
        """Gets the host executing this virtual machine.
        
        Returns a HostSystem object."""
        return self.vm.resourcePool.owner # type: ignore

    def unregister(self):
        """Unregister VM without removing machine.
        """
        name = self.vm.name
        if self.vm.runtime.powerState == 'poweredOn':
            raise myESXError(f'Error unregistering VM {name} in power on state.')
        try:
            self.vm.UnregisterVM() # type: ignore
            mylogger.debug(f'Unregistered VM {name}')
        except Exception as e:
            raise myESXError(f'Error unregistering VM {name}') from e

    def moveintoPool(self, pool:vim.ResourcePool):
        """Move VM into a resource pool.
        :param pool: Pool to move the VM into. Must be obtained calling PoolbyName.
        """

        # Move VM into pool
        try:
            mylogger.debug(f'Moving vm {self.getName()} into pool {pool}')
            pool.MoveInto([self.vm])
        except Exception as e:
            raise myESXError(f'Error moving VM {self.getName()} into ') from e

    def managePower(self, operation:str) -> myESXTASK | str:
        """Manage power states of the VM

        - operation: Operation is one of on, off, reset, shutdown, reboot, status
        """
        try:
            task = None
            # Decode operation and call function
            match (operation):
                ##############################################
                # These operations return a task (default answer to questions is to manually cancel in UI)
                # wait() can specify a different method of cancelling
                case 'on':
                    if self.vm.runtime.powerState != 'poweredOn':
                        task = myESXTASK( task=self.vm.PowerOn(None), answer=self.answerManually )
                case 'off':
                    if self.vm.runtime.powerState == 'poweredOn':
                        task = myESXTASK( task=self.vm.PowerOff(), answer=self.answerManually )
                case 'reset':
                    if self.vm.runtime.powerState == 'poweredOn':
                        task = myESXTASK( task=self.vm.Reset(), answer=self.answerManually )

                case 'shutdown':
                    if self.vm.runtime.powerState == 'poweredOn':
                        self.vm.ShutdownGuest()
                case 'reboot':
                    if self.vm.runtime.powerState == 'poweredOn':
                        self.vm.RebootGuest()
                case 'status':
                    pass
                
            if task:
                return task
            else:
                return self.vm.runtime.powerState
        except Exception as e:
            raise myESXError(f'Error changing power state of VM {self.vm.name} ({self.vm._moId}) from {self.vm.runtime.powerState} to {operation}') from e

    def currentSnapshot(self) -> Optional[vim.vm.SnapshotTree]:
        """Obtains the current snapshot of the VM.

        :return: A list with the current snapshot, or an empty list if there are no snapshots."""

        current_MoID = self._currentSnapshot_moID()
        for snapshot in self.listSnapshots():
            if snapshot.snapshot._GetMoId() == current_MoID:
                return snapshot
        return None

    def snapshotByName(self, name: str) -> Optional[vim.vm.SnapshotTree]:
        """Obtains a list with a snapshot with the given name.
        
        :return: A list with the snapshot with the name, or an empty list if not found."""
        snapshotList:List[vim.vm.SnapshotTree] = self.listSnapshots()
        for snapshot in snapshotList:
            if snapshot.name == name:
                return snapshot
        return None

    def listSnapshots(self) -> List[vim.vm.SnapshotTree]:
        """Obtains a list with all snapshots.
        
        Returns a list with all snapshots or an empty list if none is found."""
        if not self.vm.snapshot:
            mylogger.debug(f"No snapshots found for VM '{self.vm.name}'.")
            return []
        return self._list_snapshots_recursive(self.vm.snapshot.rootSnapshotList)  

    def listDevices(self) -> List[vim.vm.device.VirtualDevice]:
        if self.vm.config:
            return self.vm.config.hardware.device
        else:
            return []

    def createSnapshot(self, snapshot_name:str, snapshot_description:str, memory:bool=False, quiesce:bool=False) -> myESXTASK:
        """Creates a new snapshot for this VM."""
        return myESXTASK( 
            task = self.vm.CreateSnapshot(
                name = snapshot_name,
                description = snapshot_description,
                memory = memory,
                quiesce = quiesce
            ),
            answer = self.answerManually
        )

    def rmSnapshot(self, snapshot:vim.vm.SnapshotTree) -> myESXTASK:
        """Creates a new snapshot for this VM."""
        return myESXTASK(
            task = snapshot.snapshot.Remove(removeChildren=False, consolidate=False),
            answer = self.answerManually
        )
    
    def revertSnapshot(self, snapshot:vim.vm.SnapshotTree) -> myESXTASK:
        """Creates a new snapshot for this VM."""
        return myESXTASK(
            task = snapshot.snapshot.Revert(host=None, suppressPowerOn=True),
            answer = self.answerManually
        )
    
    def manageSnapshots(self, operation:str, label:str) -> Tuple[List[vim.vm.SnapshotTree],Optional[myESXTASK]]:
        """Manage snapshots of the VM

        - operation: operation is one of current, list, create, remove, revert
        """
        try:
            # Decode snapshot operation and call function on VM
            match (operation):
                case 'current':
                    current = self.currentSnapshot()
                    if current:
                        return ([current],None)
                    else:
                        return ([],None)
                case 'ls':
                    return (self.listSnapshots(),None)
                case 'create':
                    return ([],self.createSnapshot(label, ""))
                case 'rm':
                    snapshot = self.snapshotByName(label)
                    if snapshot:
                        return ([],self.rmSnapshot(snapshot=snapshot))
                    else:
                        mylogger.error(f'snapshot {label} not found')
                        return ([],None)
                case 'revert':
                    snapshot = self.snapshotByName(label)
                    if snapshot:
                        return ([],self.revertSnapshot(snapshot=snapshot))
                    else:
                        mylogger.error(f'snapshot {label} not found')
                        return ([],None)
            # Should not happen                    
            raise myESXError(f'Unknow snapshot operation {self.vm.name} ({self.vm._moId}). op={operation}')

        except Exception as e:
            raise myESXError(f'Error operating on snapshot of {self.vm.name} ({self.vm._moId}). op={operation}') from e

    def listSnapshotDiskLayout(self, ident:str = ""):
        """Lists the disk layout of the current snapshot of this VM."""
        print(f'{ident} SNAPSHOT LIST for {self.vm.name}')
        for snapshot in self.vm.layoutEx.snapshot: # type: ignore
            print(self._listSnapshotDisks(self.vm.layoutEx.file, snapshot, ident+"  ")) # type: ignore

    def listDiskLayout(self, ident:str = ""):
        """Lists the current disk layout of this VM."""
        print(self._listDisks(self.vm.layoutEx.file, self.vm.layoutEx.disk, ident)) # type: ignore

    # Helper function to get moID of current snapshot
    def _currentSnapshot_moID(self) -> str:
        """Helper function to get moID of current snapshot
        
        Returns moId of current snapshot"""
        if self.vm.snapshot and self.vm.snapshot.currentSnapshot:
            return str(self.vm.snapshot.currentSnapshot._moId)
        else:
            return ''

    def _list_snapshots_recursive(self, snapshot_tree: List[vim.vm.SnapshotTree]) -> List[vim.vm.SnapshotTree]:
        """Helper function to build a list from the tree of snapshots.

        :return: A list through a depth-first search of the snapshot tree."""
        resList = []
        for snapshot in snapshot_tree:
            resList.append(snapshot)
            if snapshot.childSnapshotList:
                for sub_snapshot in self._list_snapshots_recursive(snapshot.childSnapshotList):
                   resList.append(sub_snapshot)
        return resList

    # Helper function to get the full path of the VMX file of a machine
    def _get_vmx_path(self) -> str:
        """Helper function to get the full path of the VMX file of a machine.
        
        Returns an string with the path of the VMX file of this Virtual Machine."""
        tmp = [f.name for f in self.vm.layoutEx.file if f.type=='config'] # type: ignore
        vmx_file = tmp.pop()
        m = re.match(r'(.*)/[^/]+.vmx$', vmx_file)
        if not m:
            raise myESXError(f'VM Path could not be extracted from VMX pathname of VM {self.getName()}')
        else:
            return m.group(1)

    def _listDisks(self, files, disks, ident:str = "") -> str:
        """Helper function to convert to text the chain of overlays for each disk of a VM.

        Returns a string listing snapshots through a depth-first search of the tree."""
        result = ""
        for disk in disks:
            result += ident + "DISK Layout (key="+str(disk.key)+")\n"
            for overlay in disk.chain:
                result += ident + "  -Overlay:\n"
                for fileidx in overlay.fileKey:
                    result += ident + "    +"+files[fileidx].type+" "+str(files[fileidx].size)+" "+files[fileidx].name + '\n'
        return result

    def _listSnapshotDisks(self, files, snapshot, ident="") -> str:
        """Helper function to recursively list the snapshots of a disk.
        
        Returns a string listing the snapshots of a disk."""
        result = ident + "SNAPSHOT Disk Layout (key="+str(snapshot.key)+")\n"
        result += self._listDisks(files, snapshot.disk, ident+"  ")
        return result

    #######################################################################
    # VM Questions
    #######################################################################

    def _checkQuestion(self) -> Optional[vim.vm.QuestionInfo]:
        """Return the question that the VM waits for.
        
        :return: A question or None if not waiting.
        """
        return self.vm.runtime.question

    def _waitsQuestion(self) -> bool:
        """ Check if the VM is waiting a question.
        
        :return: True if waiting for a question.
        """
        return self.vm.runtime.question != None
    
    def _answerQuestion(self, message:str = '', answer:str = ''):
        """Answer a VM's question."""
        question = self.vm.runtime.question
        if not question:
            mylogger.debug(f'VM {self.vm.name} has no question to answer.')
            return

        # If message is None answer any question. If specified, check that the question matches the given message
        if not message or message == question.message[0].text:
            # If answer is defined
            if answer:
                choice = None
                for option in question.choice.choiceInfo:
                    if option.label == answer:
                        choice = option.key
                        break
                if choice is None:
                    raise ValueError(f"Answer '{answer}' not found in question choices.")
            # Use default option if answer is not defined
            else:
                choice = question.choice.choiceInfo[question.choice.defaultIndex].key # type: ignore
            # Answer using choice
            self.vm.Answer(question.id, choice)
            return True
        else:
            mylogger.error(f'Answering wrong question for vm {self.vm.name}. Question={question.message[0].text}')

    # Question regarding Moving or Copying VM to change MACs
    question_about_macs = 'This virtual machine might have been moved or copied. In order to configure certain management and networking features, VMware ESX needs to know if this virtual machine was moved or copied. If you don\'t know, answer "I Copied It". '
    
    def answerMovedMachine(self):
        """Answer the moved or copied with Moved"""
        self._answerQuestion(self.question_about_macs, 'button.uuid.movedTheVM')

    def answerCopiedMachine(self):
        """Answer the moved or copied with Copied"""
        self._answerQuestion(self.question_about_macs, 'button.uuid.copiedTheVM')

    def answerCancel(self):
        """"Answer any question with Cancel choice."""
        self._answerQuestion('', 'Cancel')

    def answerDefault(self):
        """Answer any question with default choice."""
        self._answerQuestion('', '')

    def answerManually(self):
        """In case of waiting for any question warn to go to the VI Client and answer interactively."""
        if self._waitsQuestion():
            mylogger.warning(f"VM {self.getName()}@{self.getHost().name} is waiting for a Question. Go to the ESX console, answer it and come back. **DO NOT INTERRUPT** THIS PROGRAM.")
            time.sleep(10)
