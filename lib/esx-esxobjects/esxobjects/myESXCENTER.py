#!/usr/bin/python3
"""This file manages all the resources in a set of ESX servers similar to vCenter"""

# Initialize logger
import logging
mylogger = logging.getLogger()

from typing import Callable, MutableSequence, Optional, List, Tuple
from .myESXSERVER import myESXSERVER
from .myESXVM import myESXVM
from .myESXError import myESXError, myESXWarning

import os, getpass

class myESXCENTER:
    """
    Class to handle a set of standalone ESX servers
    """
    def __init__(self):
        """Create an empty ESXCENTER object and read connection parameters from environment if possible."""
        self.serverList:MutableSequence[myESXSERVER] = []

        # Get list of hosts from environment
        hostnames = os.getenv("MYESX_HOSTS","")
        if hostnames:
            self.hostnames = hostnames.split(":")
        # Get username from environment
        self.user = os.getenv("MYESX_USER", "root")
        # Get cacert from environment
        self.cacert = os.getenv("MYESX_CACERT","NONE")

    def __del__(self):
        """
        Close connections to all ESX hosts at the time of deleting this object.
        """
        self.disconnect_allservers()

    def _addESX(self, hostname: str, user:str, password:str, cacert:str, keepaliveinterval:int):
        """Open a connection to an ESX and add it to the list.
        :param hostname: The hostname of the server to be connected.
        :param user: The username to be user to connect the ESX API.
        :param password: The password of the user to connect the ESX API.
        :param cacert: The path of a PEM file containing the certificate of the signing CA of the ESX server certiificate.
        :param keepaliveinterval: The number of seconds between pings to keep the connection alive.

        ERRORS:
        - 
        """
        try:
            self.serverList.append( myESXSERVER(hostname, user, cacert, password, keepalive=keepaliveinterval) )
            mylogger.info(f'Connected to {hostname}')
        except myESXError as e:
            raise myESXError(f'Error adding ESX host {hostname}: {e.message}: {e.message}')

    def _delESX(self, server:myESXSERVER):
        """
        Close a connection to an ESX and remove it from the list of available servers.

        :param server: The ESX server to disconnect and remove.
        :raises myESXError: Raised if some exception was received while closing the server.
        """
        try:
            server.disconnect()
            mylogger.info("Disconnected from " + server.getName())
            self.serverList.remove( server )
        except myESXError as e:
            raise myESXError(f'Error closing connection to ESX host {server.getName()}: {e.message}: {e.message}')

    def _getpassword(self) -> str:
        """Read a string from console disabling terminal echo for privacy.
        
        :return: An string containing the password if read or an empty string if any exception different from a keyboard interrupt is received.
        :raises KeyboardInterrupt: Generated if CTRL-C is pressed.
        """
        try:
            # Prompt the user for a password (the default prompt is "Password:")
            password = getpass.getpass(f"Password for user {self.user}: ")
        except KeyboardInterrupt:
            mylogger.error("Operation canceled by user")
            password = ''
        except Exception:
            mylogger.error("Error reading password from console")
            password = ''

        return password

    def connect_servers(self, hostnames:List[str]=[], user:str="", password:str="", cacert:str="", keepaliveinterval:int=myESXSERVER.DEFAULT_KEEPALIVE_INTERVAL):
        """
        Add connections to additional ESX servers. Previous existing connections are kept open.
        
        Authentication data is read from environment variable for any argument which is not provided. If the variable is not found, default values are used.

        :param hostnames: This is a list of strings containing the hostnames of the servers to connect. If the list if empty, then a string containing a list of hostname separated by ':' is read from the environment variable MYESX_HOSTS. If the variable is not found, the default is an empty list of hostnames.
        :param user: This is the username used to connect the ESX server API. The operations available are restricted by the permissions of this account. If the parameter has the value None (Python null value), then it is read from the environment variable MYESX_USER. If the variable does not exists, the default value is 'root'.
        :param password: This is the password used to connect the ESX server API. If the value is None (Python null value), then it is read from the environment variable MYESX_PASSWORD. If the variable does not exist, then it is interactively read from the console.
        :param cacert: This is the path of a PEM file containing the CA certificate signing the server certificate. This is used to validate such certificate during connection. If your server uses a self signed certificate, use the value "NONE" for this parameters. If the parameter is None (null value in Python), the environment variable MYESX_CACERT is read. If it does not exists, the default value is the string "NONE".
        :param keepaliveinterval: The number of seconds between pings to keep the connection alive.

        :raises myESXError: Is generated if interactive password reading is interrupted or an empty string is given.
        :raises myESXError: Is raise if no hosts were connected.
        :raises myESXWarning: Is raised if some hosts failed to connect but some hosts were connected.
        """
        # Replace environment with arguments if present
        if not hostnames:
            hostnames = self.hostnames
        if not user:
            user = self.user
        if not cacert:
            cacert = self.cacert
        # Get password from environment and replace it by argument if not null
        if not password:
            password = os.getenv("MYESX_PASSWORD","")
        # Read password from console if null
                # Get cacert from environment
        if not password:
            password = self._getpassword()

        if not password:
            raise myESXError("Empty password. Can't connect to any server.")

        # Connect all hosts
        failed:List[str] = []
        for host in hostnames:
            try:
                self._addESX(host, user, password, cacert, keepaliveinterval)
            except myESXError as e:
                failed.append(host)

        # Check if we connected some host
        if self.serverList == []:
            raise myESXError(f'No host was connected.')
        # Check if any host failed
        if failed != []:
            raise myESXWarning(f'Connection failed to the following hosts: {failed}')

    def disconnect_allservers(self):
        """
        Disconnects all currently connected ESX servers.

        :raises myESXError: Raised when an exception was received while disconnecting any ESX server.
        """
        failed:List[myESXSERVER] = []
        # Make a copy of the list to avoid iterator problems with removal of list
        for server in [s for s in self.serverList]:
            try:
                self._delESX(server)
            except myESXError as e:
                failed.append(server)

        if self.serverList != []:
            raise myESXWarning(f'Error disconnecting from hosts {[server.getName() for server in self.serverList]}')

    def getESXServers(self) -> MutableSequence[myESXSERVER]:
        """Return the list of ESX servers currenly connected.
        
        :return: Returns a list of myESXSERVER objects.
        """
        return self.serverList
    
    def getServer(self, nodename:str) -> Optional[myESXSERVER]:
        """
        Search a server by its name and returns it.
        
        :param nodename: The hostname of the server as it was used during open.
        :return: A myESXSERVER object describing the server or None if not found.
        """
        for server in self.serverList:
            if server.getName() == nodename:
                return server
        return None
    
    def getVMsbyLambda(self, condition:Callable[[myESXVM],str]) -> List[Tuple[myESXSERVER, List[myESXVM]]]:
        """
        Returns a filtered subset of the list of VMs in all ESX servers. Machines are selected when the lambda
        function evaluates to True.
        
        :param condition: This parameter contains is a function which returns True if the machine should be selected.
        
        :return: A list of tuples of (server, list of VMs matching the condition.)

        :raises Exception: Raised when an error was catched while filtering the list.
        """
        try:
            return [ (server, server.VMgetByLambda(condition)) for server in self.serverList ]
        except Exception as e:
            raise myESXError(f'Error filtering the list of VMs: {str(e)}')

    def getVMsbyName(self, pattern:str) -> List[Tuple[myESXSERVER, List[myESXVM]]]:
        """
        Returns a filtered subset of the list of VMs whose name matches the pattern in all ESX servers.
        
        **Notes**: The regular expression must match the whole string. For example, `.*SERVER.*` will match `NFS_SERVER_001`, but `SERVER` will not do a partial match of `NFS_SERVER_001`.

        :param pattern: This is a string containing a regexp that matches VM names.
            
        :return: A list of tuples of `(server, list of VMs matching the pattern)`.

        """
        # Iterate on all servers and build a tuple for each server
        try:
            return [ (server, server.VMgetByName(pattern)) for server in self.serverList ]
        except Exception as e:
            raise myESXError(f'Error filtering the list of VMs the list of VMs for pattern {pattern}: {str(e)}')

