from typing import List, Any
from box import Box
from connectors.hypervisor_interface import VMConfig, VMInterface, HypervisorConnector

class MockVM(VMInterface):
    @property
    def id(self) -> str:
        raise NotImplementedError()

    @property
    def name(self) -> str:
        raise NotImplementedError()

    @property
    def status(self) -> str:
        raise NotImplementedError()

    @property
    def config(self) -> VMConfig:
        raise NotImplementedError()

    def start(self) -> None:
        raise NotImplementedError()

    def stop(self) -> None:
        raise NotImplementedError()

    def pause(self) -> None:
        raise NotImplementedError()

    def resume(self) -> None:
        raise NotImplementedError()

    def delete(self) -> None:
        raise NotImplementedError()

    def rename(self, new_name: str) -> None:
        raise NotImplementedError()

    def reconfigure(self, config: VMConfig) -> None:
        raise NotImplementedError()

    def update_config(self, config: VMConfig) -> None:
        raise NotImplementedError()

    def list_devices(self) -> List[Any]:
        raise NotImplementedError()

class MockHypervisorConnector(HypervisorConnector):
    def __init__(self, host: str, user: str, password: str, **kwargs):
        raise NotImplementedError()

    @property
    def info(self) -> Box:
        raise NotImplementedError()

    def list_vms(self) -> List[VMInterface]:
        raise NotImplementedError()

    def get_vm(self, vm_id: str) -> VMInterface:
        raise NotImplementedError()

    def create_vm(self, config: VMConfig) -> VMInterface:
        raise NotImplementedError()

    def clone_vm(self, source_vm: VMInterface, config: VMConfig) -> VMInterface:
        raise NotImplementedError()

    def search_vm(self, query: str) -> List[VMInterface]:
        raise NotImplementedError()
