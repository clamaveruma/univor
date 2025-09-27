from typing import Any
import httpx

from box import Box
from connectors.hypervisor_interface import VMConfig, VMInterface, HypervisorConnector

class MockVM(VMInterface):
    def __init__(self, config: dict | str, hypervisor: "HypervisorConnector"):
        self._config = VMConfig(config)
        self.hypervisor = hypervisor

    @property
    def id(self) -> str:
        return self._config.id

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def status(self) -> str:
        return self._config.status

    @property
    def config(self) -> VMConfig:
        return self._config  # type: ignore

    def start(self) -> None:
        self._lifecycle_action("start")

    def stop(self) -> None:
        self._lifecycle_action("stop")

    def pause(self) -> None:
        self._lifecycle_action("pause")

    def resume(self) -> None:
        self._lifecycle_action("resume")

    def delete(self) -> None:
        url = f"{self.hypervisor.base_url}/vms/{self.id}"
        r = httpx.delete(url)
        r.raise_for_status()

    def rename(self, new_name: str) -> None:
        url = f"{self.hypervisor.base_url}/vms/{self.id}"
        r = httpx.put(url, json={"name": new_name})
        r.raise_for_status()
        self._config.name = new_name

    def reconfigure(self, config: VMConfig) -> None:
        url = f"{self.hypervisor.base_url}/vms/{self.id}"
        r = httpx.put(url, json=dict(config))
        r.raise_for_status()
        self._config.update(config)

    def update_config(self, config: VMConfig) -> None:
        url = f"{self.hypervisor.base_url}/vms/{self.id}"
        r = httpx.put(url, json=dict(config))
        r.raise_for_status()
        self._config.update(config)

    def list_devices(self) -> list[Any]:
        # Not implemented in mockvisor
        return []

    def _lifecycle_action(self, action: str):
        url = f"{self.hypervisor.base_url}/vms/{self.id}/{action}"
        r = httpx.post(url)
        r.raise_for_status()
        self._config.status = r.json().get("status", self._config.status)

class MockHypervisorConnector(HypervisorConnector):
    def __init__(self, host: str, user: str, password: str, port: int , **kwargs):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.base_url = f"http://{host}:{port}"
        # Optionally, store kwargs for future use
        self._extra = kwargs

    @property
    def status(self) -> VMConfig:
        url = f"{self.base_url}/status"
        r = httpx.get(url)
        r.raise_for_status()
        return VMConfig(r.json())

    @property
    def info(self) -> Box:
        """ Returns information about the connector,
            such as type, version, and capabilities, as a Box.
        """
        return Box({
            "type": "mock_hypervisor",
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "base_url": self.base_url,
            "extra": self._extra,
        })

    def list_vms(self) -> list[VMInterface]:
        url = f"{self.base_url}/vms"
        r = httpx.get(url)
        r.raise_for_status()
        return [MockVM(vm, self) for vm in r.json()]

    def get_vm(self, vm_id: str) -> VMInterface:
        url = f"{self.base_url}/vms/{vm_id}"
        r = httpx.get(url)
        r.raise_for_status()
        return MockVM(r.json(), self)

    def create_vm(self, config: VMConfig) -> VMInterface:
        url = f"{self.base_url}/vms"
        r = httpx.post(url, json=dict(config))
        r.raise_for_status()
        return MockVM(r.json(), self)

    def clone_vm(self, source_vm: VMInterface, config: VMConfig) -> VMInterface:
        url = f"{self.base_url}/vms/{source_vm.id}/clone"
        r = httpx.post(url, json=dict(config))
        r.raise_for_status()
        return MockVM(r.json(), self)

    def search_vm(self, query: str) -> list[VMInterface]:
        url = f"{self.base_url}/vms?search={query}"
        r = httpx.get(url)
        r.raise_for_status()
        return [MockVM(vm, self) for vm in r.json()]

