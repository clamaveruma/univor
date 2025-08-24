
from typing import Protocol, Any, List, Optional

class VMConfig(Protocol):
    """
    Generic interface for a VM configuration object.
    Each backend (VMware, Proxmox, KVM, etc.) should implement this interface for its own config class.
    """
    def get(self, key: str) -> Any:
        """Get a configuration value by key."""
        ...

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value by key."""
        ...

    def as_dict(self) -> dict:
        """Return the configuration as a dictionary."""
        ...

    # Add more generic config methods as needed


class VMInterface(Protocol):
    """
    Interface (Protocol) for a Virtual Machine (VM) object.
    
    This is an abstract interface class. It must be subclassed to implement a specific VM representation
    for a real hypervisor or a mock/test environment.
    
    Implementations should provide properties and methods to represent and manage a VM.
    Do not instantiate this class directly.
    """
    
    @property
    def id(self) -> str:
        """Unique identifier for the VM."""
        ...

    @property
    def name(self) -> str:
        """Name of the VM."""
        ...

    @property
    def status(self) -> str:
        """Current status of the VM (e.g., running, stopped, paused)."""
        ...

    @property
    def config(self) -> VMConfig:
        """The configuration object for this VM."""
        ...

    def start(self) -> None:
        """Start this virtual machine."""
        ...

    def stop(self) -> None:
        """Stop this virtual machine."""
        ...

    def pause(self) -> None:
        """Pause this virtual machine."""
        ...

    def resume(self) -> None:
        """Resume this virtual machine."""
        ...

    def delete(self) -> None:
        """Delete this virtual machine."""
        ...

    def rename(self, new_name: str) -> None:
        """Rename this virtual machine."""
        ...

    def reconfigure(self, config: VMConfig) -> None:
        """Apply a new configuration to this VM."""
        ...

    def list_devices(self) -> List[Any]:
        """List all devices attached to this VM."""
        ...

class HypervisorConnector(Protocol):
    """
    Interface (Protocol) for hypervisor connectors.
    
    This is an abstract interface class. It must be subclassed to implement a specific real hypervisor connector
    (e.g., VMware, mock hypervisor, etc.).
    
    Implementations must provide synchronous methods to manage virtual machines (VMs)
    and interact with the hypervisor. This interface is designed for extensibility and clarity.
    
    Do not instantiate this class directly.
    
    Core operations:
        - Create a new VM
        - Clone an existing VM
    
    Objects managed:
        - Hypervisor
        - Virtual Machine (VM)
    
    Note:
        - Authentication is not included at this stage.
        - All methods are synchronous.
        - Extend this interface as needed for additional operations or objects.
    """

    def create_vm(self, hypervisor: Any, vm_spec: dict) -> VMInterface:
        """
        Create a new virtual machine on the specified hypervisor.
        Args:
            hypervisor: The hypervisor instance or identifier.
            vm_spec: A dictionary with VM configuration parameters.
        Returns:
            The created VM object or identifier.
        """
        ...

    def clone_vm(self, hypervisor: Any, source_vm: VMInterface, clone_spec: dict) -> VMInterface:
        """
        Clone an existing virtual machine.
        Args:
            hypervisor: The hypervisor instance or identifier.
            source_vm: The VM to be cloned.
            clone_spec: A dictionary with clone configuration parameters.
        Returns:
            The cloned VM object or identifier.
        """
        ...

    # VM lifecycle operations are now handled by the VMInterface itself.
    def search_vm(self, hypervisor: Any, query: str) -> List[VMInterface]:
        """
        Search for VMs matching a query string (e.g., by name or other criteria).
        Args:
            hypervisor: The hypervisor instance or identifier.
            query: The search string or pattern.
        Returns:
            A list of matching VMInterface objects.
        """
        ...
        
