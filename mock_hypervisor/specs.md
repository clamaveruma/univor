# Mock Hypervisor
A linux service serving a mock hypervisor in a TCP port web REST API

The hypervisors look like run Virtual Machines (VM), buy it only saves in memory a list of mock VM and its state.

The program is a CLI linux command. With it we can:
-  start a new server. We can pass a port or auto
-  get the list of current servers and its PORTs
-  kill a server
-  enter commands to one of the running servers (hypervisor), that will use a internal REST client to perform the operation
 
thru The REST API we can:
- create MV, as well as change its config, or delete
- clone a VM from other
- manage VM lifecycle
- get or search the list of VMs
  