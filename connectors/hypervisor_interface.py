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
   

class HypervisorSessionProtocol(Protocol):
    """Interface Protocol for hypervisor session objects.
    To be subclassed by actual session implementations.
    """
    @property
    def hypervisor_type(self) -> str: ...
    @property
    def is_alive(self) -> bool: ...
    def connect(self): ...
    def disconnect(self): ...   


class VMConnector(Protocol):
    """
    Protocol for a Virtual Machine (VM) object.
    Implementations should provide properties and methods to represent and manage a VM.
    """
    def __init__(self, config: dict | str, hypervisor: "HypervisorConnector"):
        """
        Initialize the VM with a configuration and a reference to its hypervisor connector.
        :param config: The VM configuration as a dictionary or a JSON string.
        :param hypervisor: The HypervisorConnector instance managing this VM.
        """
        ...

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
       Protocol for a Hypervisor Connector.
       Implementations must provide methods to manage VMs and interact with the hypervisor.
       Implementations must accept a HypervisorSessionProtocol instance upon initialization.
       The 'session' attribute must be an instance of HypervisorSessionProtocol.    
    """
    
    
    
    def __init__(self, session: HypervisorSessionProtocol) -> None:
              ... 
              # In the implementation, initialize with a session object,
              # and store it as self.session.   
              
    @property
    def status(self) -> VMConfig: ...
    "returns information about the hypervisor"
    
    def list_vms(self) -> List["VMConnector"]: ...
    def get_vm(self, vm_id: str) -> "VMConnector": ...
    def create_vm(self, config: VMConfig) -> "VMConnector": ...
    def clone_vm(self, source_vm: "VMConnector", config: VMConfig) -> "VMConnector": ...
    def search_vm(self, query: str) -> List["VMConnector"]: ...

    @property
    def info(self) -> Box:
        """
        Returns information about the connector,
          such as type, version, and capabilities, as a Box.
        """
        ...

   
