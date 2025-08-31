from typing import Protocol, Any, List
from box import Box  

class VMConfig(Box):
    """
    Protocol for VM configuration objects. Must be compatible with Box (dot-access dict).
    See: https://box-python-sdk.readthedocs.io/en/latest/ for Box documentation.
    Implementations should inherit from Box or provide equivalent attribute and dict access.
    Examples:
        config = MyVMConfig(cpu=2, memory=4096, name='testvm')
        print(config.cpu)         # 2
        print(config['memory'])  # 4096
        config.disk = 50
        config['net'] = 'eth0'
    """
   

class VMInterface(Protocol):
    """
    Protocol for a Virtual Machine (VM) object.
    Implementations should provide properties and methods to represent and manage a VM.
    """
    @property
    def id(self) -> str: ...
    @property
    def name(self) -> str: ...
    @property
    def status(self) -> str: ...
    @property
    def config(self) -> VMConfig: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def delete(self) -> None: ...
    def rename(self, new_name: str) -> None: ...
    def reconfigure(self, config: VMConfig) -> None:
        """
        Replace the entire configuration of the VM with the provided config.
        All previous settings are lost unless included in the new config.
        """
        ...

    def update_config(self, config: VMConfig) -> None:
        """
        Merge the provided config with the current config, overwriting only the specified fields.
        Unspecified fields remain unchanged.
        """
        ...
    def list_devices(self) -> List[Any]: ...


class HypervisorConnector(Protocol):
   
    """
    Protocol for hypervisor connectors.
    Implementations must provide methods to manage VMs and interact with the hypervisor.
    """

    def __init__(self, host: str, user: str, password: str, **kwargs): ...
    def list_vms(self) -> List["VMInterface"]: ...
    def get_vm(self, vm_id: str) -> "VMInterface": ...
    def create_vm(self, config: VMConfig) -> "VMInterface": ...
    def clone_vm(self, source_vm: "VMInterface", config: VMConfig) -> "VMInterface": ...
    def search_vm(self, query: str) -> List["VMInterface"]: ...
    @property
    def info(self) -> Box:
        """
        Returns information about the connector,
          such as type, version, and capabilities, as a Box.
        """
        ...
        
