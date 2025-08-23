#!/usr/bin/python3
"""
This module manages a connection to a VMWare ESX server through its remote API
and implements high level operations to get access to objects on it such as
Virtual Machines, Datastores, Pools, etc.
"""

from optparse import Option
from typing import Any, Callable, Optional, List, Tuple

# Initialize logger
import logging

mylogger = logging.getLogger()

from .myESXError import myESXError, myESXWarning
from .myESXVM import myESXVM
from .myESXTASK import myESXTASK
from .myESXCONFIG import myESXCONFIG, myESXPath

import pyVim.connect
from pyVmomi import vim

import ssl
import time
import re


# This object manages ESX server
class myESXSERVER:
    """Class to handle basic operations on the API like connection, disconnection and getting resource lists."""

    RES_VM = [vim.VirtualMachine]
    """This symbol is used to get a list of VMs with getresources()"""
    RES_NET = [vim.Network]
    """This symbol is used to get a list of Networks with getresources()"""
    DEFAULT_KEEPALIVE_INTERVAL = 300
    """This is the number of seconds between pings to keep the connection alive."""
        
    def __init__(self, hostname:str, username:str, certfile:str, password:str = '', keepalive:int = DEFAULT_KEEPALIVE_INTERVAL):
        """
        Initializes the handler for the connection and connects the given host with user and password.
        If the password is provided, the initialization function includes connecting to the server and reading some API objects from
        the server.
        
        :param host: This is the ip or dns name of the ESX server.
        :param user: A username with valid permissions to operate on the server.
        :param certfile: This is the full pathname of a PEM file containing the public certificate of the CA
            signing the server certificate. If certfile is "NONE" (string) then verification is disabled.
        :param password: The password of the user is never stored in the object after connection.
        :param keepalive: The time in seconds between pings to keep the connection alive. Default is 300 seconds. If keepalive is 0, the keepalive thread is not launched.
        """
        # Store connection parameters
        self.hostname = hostname
        self.user = username
        self.certfile = certfile
        self.keepalive_interval:int = keepalive
        self.keepalive_terminate:bool = False
        
        self.si:Optional[vim.ServiceInstance] = None
        self.vms:List[myESXVM] = []

        if password:
            # Open connection (do not store password) and get server content
            self._connect(password)
        else:
            raise myESXError('No password for connection.')            

    def _keepalive(self):
        """Keep the connection alive by sending a ping every interval seconds.
        
        The time in seconds between pings is set during the initialization of the object.
        """
        if self.si == None:
            raise myESXError(f'No connection to server {self.hostname} to keep alive.', True)
        try:
            # Run while the connection is not terminated
            while not self.keepalive_terminate:
                self.si.RetrieveContent()  # This will ping the server
                mylogger.debug(f'Pinged server {self.hostname} to keep connection alive.')
                count:int = 0
                while count < self.keepalive_interval and not self.keepalive_terminate:
                    count += 1
                    time.sleep(1)
        except Exception as e:
            raise myESXError(f'Error keeping connection alive to server {self.hostname}', True) from e
        

    def _connect(self, password:str):
        """Open the connection to this ESX host. In case of error, an exception is raised.
        
        :param password: The password of the user. The password is never stored in this object after being used.
        :raises myESXError: Raised if an exception is received while connecting the server.
        """
        if self.certfile != "NONE":
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.load_verify_locations(self.certfile)
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
        else:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        try:
            # Connect to the vSphere server
            self.si = pyVim.connect.SmartConnect(
                host=self.hostname,
                user=self.user,
                pwd=password,
                sslContext=context
            )
            mylogger.debug(f'Connection to host {self.hostname} as {self.user} succeeded.')
            # Create shortcuts for important objects
            self.content:vim.ServiceInstanceContent = self.si.RetrieveContent()
            # Retrieve the datacenter from the connection
            self.datacenter:vim.Datacenter = self.content.rootFolder.childEntity[0] # type: ignore
            # Retrieve the host from the datacenter
            self.host:vim.ComputeResource = self.datacenter.hostFolder.childEntity[0] # type: ignore

            # Retrieve the fileManager from the connection
            self.fileManager:vim.FileManager = self.content.fileManager # type: ignore
            # Retrieve the virtualDiskManager from the connection
            self.virtualDiskManager:vim.VirtualDiskManager = self.content.virtualDiskManager # type: ignore

            # Start the keepalive thread if keepalive is not 0
            if self.keepalive_interval > 0:
                import threading
                self.keepalive_thread = threading.Thread(target=self._keepalive, daemon=True)
                self.keepalive_thread.start()
                mylogger.debug(f'Keepalive thread started for server {self.hostname} every {self.keepalive_interval} seconds.')

        except Exception as e:
            raise myESXError(f'Error connecting to server {self.hostname} as user {self.user}', True) from e

    def disconnect(self):
        """
        Closes connection to ESX host.

        :raises myESXError: Raised if an exception was received while disconnecting the server. 
        """
        if self.si == None:                
            raise myESXWarning(f'Closing already closed connection to {self.hostname}', True)
        try:
            # Stop the keepalive thread if it exists
            if self.keepalive_thread is not None:
                self.keepalive_terminate = True
                self.keepalive_thread.join()
                self.keepalive_thread = None
            mylogger.debug(f'Keepalive thread stopped for server {self.hostname}.')

            # Remove shortcuts for some important objects
            del self.virtualDiskManager
            del self.fileManager
            del self.host
            del self.datacenter
            del self.content
            # Disconnect from the vSphere server
            pyVim.connect.Disconnect(self.si)
            self.si = None
        except Exception as e:
            raise myESXError(f'Error disconnecting from server {self.hostname}', True) from e

    def getName(self) -> str:
        """
        Return the hostname of this server.

        :return: A string containing the hostname of this server.
        """
        return self.hostname

    #######################################################################
    # Virtual Machines
    #######################################################################

    def VMgetByLambda(self, condition:Callable[[myESXVM],str]) -> List[myESXVM]:
        """
        Return a filtered subset of the list of VMs. Machines are selected when the lambda
        function evaluates to True.
        
        :param function: This is a function which returns True if the machine should be selected.
        :return: Returns a list of VMs matching the condition.
        :raises myESXError: Raised when an exception was received while filtering the list of VMs.
        """
        try:
            return [ v for v in self.vms if condition(v) ]
        except Exception as e:
            raise myESXError(f'Error filtering the list of VMs the list of VMs from server {self.hostname}', True) from e

    def VMgetByanyfield(self, pattern:str, getfield:Callable[[myESXVM],str]) -> List[myESXVM]:
        """
        Return a filtered subset of the list of VMs.
        
        :param pattern: This is a string containing a regexp that the machines in the list match.
            The regular expression must match the whole string. For example, ".*SERVER.*"
            will match NFS_SERVER_001, but "SERVER" will not match it.
            
        :param getfield: This parameter is a function which returns one string from the VM to match.
            This function is applied to each VM to generate a string to match with the pattern.
            Useful examples are using lambda functions to extract one field of the VM like:
                con.VMbyanyfield("pattern", lambda v:v.name) -> This matches the VM name.
                con.VMbyanyfield("pattern", lambda v:v.config.annotation) -> This matches
                    the vm annotation.
            
        :return: A list of VMs matching the pattern.
        :raises myESXError: Raised if an exception was received while filtering the VMs. 
        """
        try:
            return [ v for v in self.vms if re.match(pattern, getfield(v)) ]
        except Exception as e:
            raise myESXError(f'Error filtering the list of VMs the list of VMs from server {self.hostname}', True) from e

    def VMgetByName(self, pattern:str) -> List[myESXVM]:
        """
        Returns a filtered subset of the list of VMs whose name matches the pattern.
        
        :param pattern: This is a string containing a regexp that matches VM names.
            The regular expression must match the whole string. For example, ".*SERVER.*"
            will match NFS_SERVER_001, but "SERVER" will not match it.
        :return: A list of VMs matching the pattern.
        :raises myESXError: Raised if an exception was received while filtering the VMs. 
        """
        try:
            self._VMgetAll()
            return self.VMgetByanyfield(pattern, myESXVM.getName)
        except Exception as e:
            raise myESXError(f'Error filtering the list of VMs the list of VMs from server {self.hostname}', True) from e

    def VMMigrateHere(self, vm:myESXVM, dstPool:Optional[vim.ResourcePool] = None) -> bool:
        """
        Migrate to this host an existing virtual machine from another ESX host. The VM must already be in powered off state. The VM files must be in a data store shared by the source and destination ESX.
        The migration process consists in unregistering from the source ESX server and registering in this server.
        
        :param vm: The VM to migrate.
        :type vm: myESXVM
        :param dstPool: Destination resource pool in this ESX server.
        :return: True if migration succeeded.
        :rtype: bool
        :raises myESXError: Raised when migration conditions are not fulfilled (no destination pool) or the migration fails (unregistering or registering).
        """

        # Check power state
        if vm.managePower('status') != 'poweredOff':
            raise myESXError(f'VM ({vm.getName()}) is not in power off state and can not be migrated.', True)

        # Get VM name
        name:str = vm.getName()
        # Get VM directory
        vmx_dir:str = vm._get_vmx_path()

        # Destination pool from source machine if not specified as argument
        if not dstPool:
            srcpool_name = vm.vm.resourcePool.name # type: ignore
            dstPool=self.PoolgetByName(srcpool_name)
            if not dstPool:
                raise myESXError(f"Pool {srcpool_name} not found at host {self.getName()}. VM not migrated.", True)

        # Unregister from machine's host
        try:
            mylogger.debug(f'Unregistering VM {vm.getName()} from host {vm.getHost().name}')
            vm.unregister()
        except Exception as e:
            raise myESXError(f'VM ({vm.getName()}) failed to unregister from source host.', True)

        # Register in current host after 1 second
        time.sleep(1)
        mylogger.debug(f'Registering VM <{vmx_dir}, {name}, {dstPool}> on server {self.hostname}')
        try:
            return self.VMRegister(name=name, vmPath=vmx_dir, pool=dstPool)
        except Exception as e:
            raise myESXError(f'VM ({vm.getName()}) failed to register at host {self.getName()}.', True)

    def VMRegister(self, name:str, vmPath:str, pool:vim.ResourcePool) ->bool:
        """
        Register an existing virtual machine directory indicating the path to the directory containing the virtual machine, its name, and the pool to register in. The directory path can be in one of the following formats:
                  - /vmfs/volumes/datastore/path/to/VM/directory
                  - [datastore] path/to/VM/directory

        A *.vmx file must exist inside the VM directory.

        :param name: Label of the virtual machine.
        :type name: str
        :param vmPath: This is the path to the directory containing the files of the VM.
        :type vmPath: str
        :param pool: Pool to register the VM in. Must be obtained calling PoolbyName.  If no pool is provided, the VM will be registered at the top resource pool of the server.
        :type pool: vim.ResourcePool
        :return: True if success.
        :rtype: bool
        :raises myESXError: Raised if the .vmx file could not be found, or the VM could not be registered.
        """

        if pool == None:
            pool = self.PoolgetByName()

        # Find the vmx file
        vmx_paths = self._findFiles(vmPath, '*.vmx')
        if len(vmx_paths) != 1:
            raise myESXError(f'Error looking for VMX file at directory {vmPath}')
        else:
            vmx_path = vmx_paths.pop()
        # Register the VM
        task = myESXTASK(
            self.datacenter.vmFolder.RegisterVm(
                path=vmx_path,  # Path to the .vmx file
                name=name,  # Name of the VM (can be different from the .vmx file)
                asTemplate=False,  # Set to True if registering as a template
                pool=pool,  # Resource pool (optional)
                host=None  # Host to register the VM on (optional)
            )
        )

        # Wait for the task to end
        task.wait()
        if task.isOK():
            return True
        else:
            raise myESXError(f"Failed to register VM: {task.getError()} on host {self.hostname}")

    def VMCreate(self, vmconfig:myESXCONFIG, vmPath:str, name:str, pool:Optional[vim.ResourcePool] = None) -> myESXTASK:
        """
        Create a new virtual machine directory indicating the path to the new directory containing the virtual machine, its name, and the pool to register in. The directory path can be in one of the following formats:
                  - /vmfs/volumes/datastore/path/to/VM/directory
                  - [datastore] path/to/VM/directory

        :type vmdir_path: str
        :param vmdir_path: This is the path to the directory containing the files of the VM.
        :param name: Label of the virtual machine.
        :type name: str
        :param pool: Pool to register the VM in. Must be obtained calling PoolbyName. If no pool is provided, the VM will be registered at the top resource pool of the server.
        :type pool: vim.ResourcePool
        :return: The task which creates the VM.
        :rtype: myESXTASK 
        """

        if pool == None:
            pool = self.PoolgetByName()

        # Set VM name and destination path
        vmconfig.setName(name)
        vmconfig.setDir(vmPath)

        # Create the VM
        return myESXTASK(
            self.datacenter.vmFolder.CreateVm(
                config=vmconfig.getConfigSpec(), # ConfigSpec of the new machine
                pool=pool, # Resource pool
                host=None
            )
        )

    #######################################################################
    # Files and directories
    #######################################################################

    def FSexists(self, path: str) -> bool:
        """Query a FS to check if a directory exists.
        
        :param path: The path of the directory including the data store between brackets.
        :return: True if directory exists and false otherwise.
        """
        # Check if directory exists
        esxpath = myESXPath(path)
        res = self._findFiles(esxpath.dirname(), esxpath.basename() )
        return res != []
    
    def FSmkDir(self, path: str):
        """Create a new directory. The parent directories are created automatically.
        
        :param path: The path of the new directory including the data store between brackets. 
        """
        
        try:
            self.fileManager.MakeDirectory(name=path, datacenter=None, createParentDirectories=True)
        except Exception as e:
            raise myESXError(f'Error creating directory {path} at server {self.hostname}') from e
 
    def FSrm(self, path: str) -> myESXTASK:
        """Delete a file or directory. The contents of directories are removed recursively.
        WARNING: This function is very dangerous because it removes non empty directories.
        
        :param path: The path of the file or directory including the data store between brackets.
        :return: A task to control the removal.
        """
        
        try:
            return myESXTASK( self.fileManager.DeleteFile(name=path, datacenter=None) )
        except Exception as e:
            raise myESXError(f'Error removing directory {path} at server {self.hostname}') from e

    def FScp(self, srcPath: str, dstPath:str, force = False) -> myESXTASK:
        """
        Copy a file or directory into the destination Path. Copying directories of VM can be very long tasks and should be monitored asynchronously.

        :param srcPath: The source path of a file or directory.
        :param dstPath: If the source is a file, this is the name of the file. If the source is a directory, the destination is the name of the new directory.
        :param force: If true overwrite the destination if exists.
        :return: A task that allows to monitor the result of the operation.
        """
        
        try:
            return myESXTASK( self.fileManager.CopyFile(sourceName=srcPath, sourceDatacenter=None, destinationName=dstPath, destinationDatacenter=None, force=False) )
        except Exception as e:
            raise myESXError(f'Error copying file or dir {srcPath} to {dstPath} at server {self.hostname}') from e
 
    def FSmv(self, srcPath: str, dstPath:str, force = False) -> myESXTASK:
        """
        Copy a file or directory into the destination Path. Copying directories of VM can be very long tasks and should be monitored asynchronously.

        :param srcPath: The source path of a file or directory.
        :param dstPath: If the source is a file, this is the name of the file. If the source is a directory, the destination is the name of the new directory.
        :param force: If true overwrite the destination if exists.
        :return: A task that allows to monitor the result of the operation.
        """
        
        try:
            return myESXTASK( self.fileManager.MoveFile(sourceName=srcPath, sourceDatacenter=None, destinationName=dstPath, destinationDatacenter=None, force=False) )
        except Exception as e:
            raise myESXError(f'Error moving file or dir {srcPath} to {dstPath} at server {self.hostname}') from e
 
    #######################################################################
    # Virtual Disks
    #######################################################################

    def VDcreate(self, dstPath:str, sizeMb:int, dstDiskSpec:Optional[vim.VirtualDiskManager.VirtualDiskSpec] = None) -> myESXTASK:
        """
        Duplicates a virtual disk with the destination name. Copying VDs can be very long tasks and should be monitored asynchronously.

        :param dstPath: The path of the new Virtual Disk.
        :param dstDiskSpec: Disk specs describing the disk size and implementation.

        :return: A task that allows to monitor the result of the operation.
        """
        # Default disk type is lsilogic+thin
        vdSpecs = vim.VirtualDiskManager.FileBackedVirtualDiskSpec()
        vdSpecs.diskType = vim.VirtualDiskManager.VirtualDiskType.thin
        vdSpecs.adapterType = vim.VirtualDiskManager.VirtualDiskAdapterType.lsiLogic
        vdSpecs.capacityKb = 1024 * sizeMb

        # If the user provided specs, replace the defaults
        if dstDiskSpec != None:
            if dstDiskSpec.diskType != None:
                vdSpecs.diskType = dstDiskSpec.diskType
            if dstDiskSpec.adapterType != None:
                vdSpecs.adapterType = dstDiskSpec.adapterType

        try:
            # Create the virtual disk
            task = myESXTASK(
                self.virtualDiskManager.CreateVirtualDisk(name=dstPath, spec=vdSpecs) # type: ignore
            )
            return task
        
        except Exception as e:
            raise myESXError(f'Error creating VD {dstPath} at server {self.hostname}') from e
        
    def VDcp(self, srcPath: str, dstPath:str, dstDiskSpec:vim.VirtualDiskManager.VirtualDiskSpec = None, force = False) -> myESXTASK:
        """
        Duplicates a virtual disk with the destination name. Copying VDs can be very long tasks and should be monitored asynchronously.

        :param srcPath: The source path of a Virtual Disk.
        :param dstPath: The name of the destination Virtual Disk.
        :param dstDiskSpec: Disk specs to select another implementation.
        :param force: If true overwrite the destination if exists.

        :return: A task that allows to monitor the result of the operation.
        """
        
        try:
            # Delete the virtual disk
            task = myESXTASK(
                self.virtualDiskManager.CopyVirtualDisk(sourceName=srcPath, destName=dstPath, destSpec=dstDiskSpec, force=False)
            )
            return task
        
        except Exception as e:
            raise myESXError(f'Error duplicating VD {srcPath} to {dstPath} at server {self.hostname}') from e
        
    def VDmv(self, srcPath: str, dstPath:str, dstDiskSpec:vim.VirtualDiskManager.VirtualDiskSpec = None, force = False) -> myESXTASK:
        """
        Moves a virtual disk to the destination name. Moving VDs between datastores can be very long tasks and should be monitored asynchronously.

        :param srcPath: The source path of a Virtual Disk.
        :param dstPath: The name of the destination Virtual Disk.
        :param force: If true overwrite the destination if exists.

        :return: A task that allows to monitor the result of the operation.
        """
        
        try:
            # Delete the virtual disk
            task = myESXTASK(
                #self.virtualDiskManager.MoveVirtualDisk(sourceName=srcPath, sourceDatacenter=None, destName=dstPath, destDatacenter=None, force=False, destSpec=dstDiskSpec)
                self.virtualDiskManager.MoveVirtualDisk_Task(sourceName=srcPath, destName=dstPath, destDiskSpec=dstDiskSpec, force=False)
            )
            return task
        
        except Exception as e:
            raise myESXError(f'Error duplicating VD {srcPath} to {dstPath} at server {self.hostname}') from e
        
    def VDrm(self, path: str) -> myESXTASK:
        """Deletes a virtual disk.
        
        :param path: The path of the virtual disk to remove including the data store between brackets. 
        :return: A task that allows to monitor the result of the operation.
        """
        
        try:
            # Delete the virtual disk
            task = myESXTASK(
                self.virtualDiskManager.DeleteVirtualDisk(name = path) # type: ignore
            )
            return task
        
        except Exception as e:
            raise myESXError(f'Error removing VD {path} at server {self.hostname}') from e

    def VDinflate(self, path: str) -> myESXTASK:
        """Inflates a thin virtual disk to its declared size. This operations claims space in the datastore to guarantee that the VD can reach its maximum declared size.
        
        :param path: The path of the virtual disk to inflate including the data store between brackets. 
        :return: A task that allows to monitor the result of the operation.
        """
        
        try:
            # Inflate the virtual disk
            task = myESXTASK(
                self.virtualDiskManager.InflateVirtualDisk(name = path, datacenter= None)
            )
            return task
        
        except Exception as e:
            raise myESXError(f'Error inflating VD {path} at server {self.hostname}') from e

    def VDextend(self, path: str, newSizeMb:int, eagerZero:bool = False) -> myESXTASK:
        """Expands a virtual disk to a new size. If desired, the new blocks will be initialized to zero.
        
        :param path: The path of the virtual disk to extend including the data store between brackets. 
        :param newSizeMb: The new size in Mbytes.
        :param eagerZero: If true, fill the added space with zeroes.

        :return: A task that allows to monitor the result of the operation.
        """
        
        try:
            # Extend the virtual disk
            task = myESXTASK(
                self.virtualDiskManager.ExtendVirtualDisk(name = path, newCapacityKb = newSizeMb*1024, eagerZero= eagerZero ) # type: ignore
            )
            return task
        
        except Exception as e:
            raise myESXError(f'Error extending VD {path} at server {self.hostname}') from e
        
    #######################################################################
    # Other resources
    #######################################################################

    def _getresources(self, resource_list) -> List[Any]:
        """
        Get a list of resources from the ESX server.
        
        :param resource_list: A list with some vmomi object types to get.
        Predefined symbols RES_VM and RES_NET are defined to get VMs and Networks.
        """
        try:
            # Retrieve a view of a list of resources
            container = self.content.viewManager.CreateContainerView(self.content.rootFolder, resource_list, True)
        except Exception as e:
            raise myESXError(f'Error retrieving a list of resources from server {self.hostname}') from e
        
        return container.view

    def NetgetByName(self, net_name:str) -> Optional[vim.Network]:
        """
        Search for a network by name in the vSphere/ESXi inventory.

        :param net_name: The name of the network to locate.

        :return: A network if found or None if no pool existed with that name.
        """
        # Default pool is root level pool (Resources)
        if net_name is None:
            return None

        # Traverse compute resources (clusters or standalone hosts)
        for net in self.host.network:
            if net.name == net_name:
                return net
        return None

    def PoolgetByName(self, resource_pool_name:str = None) -> Optional[vim.ResourcePool]:
        """
        Search for a resource pool by name in the vSphere/ESXi inventory.

        :param resource_pool_name: The name of the pool to locate. If not specified, the top resource pool of the server is returned.
        :return: A pool if found or None if no pool exists with that name.
        """
        # Default pool is root level pool (Resources)
        if resource_pool_name is None:
            resource_pool_name = 'Resources'

        # Traverse compute resources (clusters or standalone hosts)
        for host in self.datacenter.hostFolder.childEntity:
            # Traverse nested resource pools
            for pool in self._PoolgetAll(host.resourcePool):
                if pool.name == resource_pool_name:
                    return pool
        return None

    def DSgetByName(self, datastore_name:str) -> Optional[vim.Datastore]:
        """
        Search for datastore by name.

        :param datastore_name: The name of the data store to return.
        :return: The datastore object or None if not found..
        """
        for datastore in self.datacenter.datastore:
            if datastore.name == datastore_name:
                return datastore
        return None

    def DSgetAll(self) -> List[vim.Datastore]:
        """Return the list of data stores of this server.

        :return: A list of datastore objects.
        """
        return self.datacenter.datastore

    def _VMgetAll(self):
        """Refresh the list of vms from the ESX server.
        
        The list of VMs can be accessed in the vms field."""
        if self.si == None:                
            self.vms = []
            raise myESXError(f'Error getting VMs from already closed connection to {self.hostname}')
        try:
            self.vms = [myESXVM(v) for v in self._getresources(self.RES_VM)]
        except Exception as e:
            raise myESXError(f'Error refreshing the list of VMs from server {self.hostname}') from e

    def _PoolgetAll(self, resource_pool:vim.ResourcePool) -> List[vim.ResourcePool]:
        """
        Recursively traverse nested resource pools.

        Returns a list of all resource pools of this ESX server.
        """
        pools = [resource_pool]
        for pool in resource_pool.resourcePool:
            pools.extend(self._PoolgetAll(pool))
        return pools

    def _findFilesByName(self, dsname:str, directory_path:str, filter:str = "*") -> List[str]:
        """
        Returns a list of all filenames inside [datastore] directory_path/<filter> matching the given filter.

        :param dsname: The name of the datastore.
        :param directory_path: The path inside which file search starts. 
        :param filter: That is a string that can contain wildcard expression for filenames.
        :return: A list of strings with the names of the files found.
        """
        try:
            datastore:vim.Datastore = self.DSgetByName(dsname)

            # Get the datastore browser
            browser = datastore.browser

            # Specify the directory to list
            search_spec = vim.host.DatastoreBrowser.SearchSpec()
            search_spec.matchPattern = [filter]  # List files and directories with given filter

            # Search the directory
            task = myESXTASK(
                browser.SearchSubFolders(
                    datastorePath=f"[{datastore.name}] {directory_path}",
                    searchSpec=search_spec
                )
            )

            # Wait for the task to end
            taskInfo = task.wait()
            if task.isOK():
                res = []
                for result in taskInfo.result: # type: ignore
                    for file in result.file:
                        res.append(f"[{datastore.name}] {directory_path}/{file.path}")
                return res
            else:
                raise myESXError(f"Failed to list directory: {task.getError()} on host {self.hostname}")
                
        except Exception as e:
            mylogger.exception(e)
            raise myESXError(f'Error listing directory [{dsname}]{directory_path} at server {self.hostname}') from e

    def _findFiles(self, vmx_path:str, filter:str) -> List[str]:
        """Get the name of the vmx file of a VM inside the given directory.

        :param vmx_path: The directory of a VM containing a .vmx file. The path can be
         either [datastore] path/to/the/directory
         or /vmfs/volumes/datastore/path/to/the/directory
        :param filter: A wildcard to filter files.
        
        :return: A list of valid paths to files found or an empty string."""
        # Check if path is [datastore] path/to/VM/directory
        span=re.match(r'^\[([^]]+)\] *(.*) *', vmx_path)
        if span != None:
            dsname=span.group(1)
            pathname=span.group(2)
        else:
            span=re.match(r' */vmfs/volumes/([^/]+)/(.*) *', vmx_path)
            if span != None:
                dsname=span.group(1)
                pathname=span.group(2)
            else:
                raise myESXError(f'Path does not contain a valid ESX path.')
        filelist = self._findFilesByName(dsname, pathname, filter=filter)
        return filelist

    def _splitPath(self, path:str) -> Tuple[str, str]:
        """Split a pathname into datastore name and directory path.

        :param path: A pathname to split. The path can be either [datastore] path/to/the/directory or /vmfs/volumes/datastore/path/to/the/directory
        :return: A tuple with a DS name and a pathname."""
        # Check if path is [datastore] path/to/VM/directory
        span=re.match(r'^\[([^]]+)\] *(.*) *', path)
        if span != None:
            dsname=span.group(1)
            pathname=span.group(2)
        else:
            span=re.match(r' */vmfs/volumes/([^/]+)/(.*) *', path)
            if span != None:
                dsname=span.group(1)
                pathname=span.group(2)
            else:
                raise myESXError(f'Path does not contain a valid ESX path.')
        return dsname, pathname

    def lsFiles(self, path:str, filter:str = "*", recurse:bool = False, type:List[vim.host.DatastoreBrowser.Query] = [], details:bool = False) -> List[Tuple[str, vim.host.DatastoreBrowser.FileInfo]]:
        """
        Returns a list of all filenames inside [datastore] directory_path/<filter> matching the given filter.

        :param dsname: The name of the datastore.
        :param directory_path: The path inside which file search starts. 
        :param filter: That is a string that can contain wildcard expression for filenames.
        :return: A list of strings with the names of the files found.
        :raises myESXError: Datastore not found or failed to list directory.
        """
        try:
            dsname, directory_path = self._splitPath(path)
            # Get the datastore
            datastore:Optional[vim.Datastore] = self.DSgetByName(dsname)
            # Get the datastore browser
            if datastore:
                browser = datastore.browser
            else:
                raise myESXError(f'Datastore {dsname} not found.')

            # Specify the directory to list
            search_spec = vim.host.DatastoreBrowser.SearchSpec()
            search_spec.matchPattern = [filter]  # List files and directories with given filter

            # Set the type of search
            if type:
                search_spec.type = type
            # Set the details returned by the search           
            if details:
                search_spec.details = vim.host.DatastoreBrowser.FileInfo.Details()
                search_spec.details.fileSize = True # type: ignore
                search_spec.details.fileType = True # type: ignore
                search_spec.details.modification = True # type: ignore
                search_spec.details.fileOwner = True # type: ignore

            if recurse:
                # Search the directory
                task = myESXTASK(
                    browser.SearchSubFolders(
                        datastorePath=f"[{datastore.name}] {directory_path}",
                        searchSpec=search_spec
                    )
                )
            else:
                # Search the directory
                task = myESXTASK(
                    browser.Search(
                        datastorePath=f"[{datastore.name}] {directory_path}",
                        searchSpec=search_spec
                    )
                )

            searchResults:List[vim.host.DatastoreBrowser.SearchResults] = []
            # Wait for the task to end
            taskInfo = task.wait()
            if task.isOK():
                if recurse:
                    searchResults = taskInfo.result # type: ignore
                else:
                    searchResults = [taskInfo.result] # type: ignore

                res = []
                for result in searchResults: # type: ignore
                    files:List[vim.host.DatastoreBrowser.FileInfo] = result.file
                    for file in files:
                        res.append((f"{result.folderPath}/{file.path}", file)) # type: ignore
                return res
            else:
                raise myESXError(f"Failed to list directory: {task.getError()} on host {self.hostname}")
                
        except Exception as e:
            mylogger.exception(e)
            raise myESXError(f'Error listing path {path} at server {self.hostname}') from e
