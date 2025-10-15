# TODO: simplifica VMconector, creo que vale con el VM_id, lo mínimo necesario para operar
# hacer tests , modificar lo que hay, para el conector de hypervisor y de VM.
# hacer tests del connections manager . Añadir logs y verlos


from typing import Any
import uuid
import httpx

from box import Box
from connectors.hypervisor_interface import VMConfig, VMConnector, HypervisorConnector, HypervisorSessionProtocol


##### Sessions #####
class MockvisorSession(HypervisorSessionProtocol):
    """
    A mock hypervisor session implementation.
    Uses REST API.

    Args:
        host_URL (str): The base URL of the hypervisor.
            Must include scheme (http:// or https://) and optionally port.
            Examples: "http://localhost:8000", "https://hypervisor.example.com"
        user (str): The username for authentication.
        password (str): The password for authentication.
    """
    def __init__(self, host_URL: str, user: str, password: str):
        self.base_URL = host_URL
        self.user = user
        self.password = password
        self.session_id = str(uuid.uuid4())
        self._client = httpx.Client(base_url=host_URL, auth=(user, password))

    def request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """
        Make an HTTP request to the hypervisor.
        raise_for_status() is called on the response.

        Args:
            method (str): The HTTP method (GET, POST, PUT, DELETE).
            endpoint (str): The API endpoint (path) to call.
            **kwargs: Additional arguments to pass to httpx request.
            example: session.request("GET", "/vms", params={"status": "running"})

        Returns:
            httpx.Response: The HTTP response object.
        """
        url = f"{self.base_URL}/{endpoint.lstrip('/')}"
        response = self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    @property
    def hypervisor_type(self) -> str:
        return "mock_hypervisor"

    @property
    def is_alive(self) -> bool:
        """Check if the session is alive by making a test request to the hypervisor."""
        try:
            resp = self.request("GET", "/status", timeout=2)
            return resp.status_code == 200
        except httpx.RequestError:
            return False
        
    def connect(self):
        """Establish the session.
        For mockvisor, this may be a no-op if it does not use authentication tokens
        """
        # just check connection
        if not self.is_alive:
            raise ConnectionError(f"Cannot connect to hypervisor at {self.base_URL}")

    def disconnect(self):
        """Disconnect the session. For mockvisor, this may be a no-op."""
        self._client.close()
             



##### Connectors #####

class MockVMConnector(VMConnector):
    """ A mock hypervisor VM implementation.
    references its hypervisor connector to make API calls.
    
    Args:
        config (dict or str): The VM configuration as a dictionary or JSON string.
        hypervisor (HypervisorConnector): The HypervisorConnector instance managing this VM.
    """

    def __init__(self, config: dict | str, hypervisor: "MockHypervisorConnector"):
        self._config = VMConfig(config)
        self.hypervisor: MockHypervisorConnector = hypervisor

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
        r= self.hypervisor.request("DELETE", f"/vms/{self.id}")
        r.raise_for_status()

    def rename(self, new_name: str) -> None:
        ur= self.hypervisor.request("PUT", f"/vms/{self.id}", json={"name": new_name})
        self._config.name = new_name

    def reconfigure(self, config: VMConfig) -> None:
        """ Update the entire VM configuration
        the new id must be the same as the old one"""
        if config.id != self.id:
            raise ValueError("VM ID cannot be changed")
        
        r = self.hypervisor.request("PUT", f"/vms/{self.id}", json=dict(config))
        self._config = config

    def update_config(self, config: VMConfig) -> None:
        """patch the VM configuration
        Merge the provided config with the current config, 
        overwriting only the specified fields.
        The new id must be the same as the old one"""
        if config.id is not None and config.id != self.id:
            raise ValueError("VM ID cannot be changed")

        r = self.hypervisor.request("PATCH", f"/vms/{self.id}", json=dict(config))
        self._config.update(config)


    def list_devices(self) -> list[Any]:
        # Not implemented in mockvisor
        return []

    def _lifecycle_action(self, action: str):
        r= self.hypervisor.request("POST", f"/vms/{self.id}/{action}")
        self._config.status = r.json().get("status", self._config.status)


class MockHypervisorConnector(HypervisorConnector):
    """ A mock hypervisor connector implementation.
    Uses REST API."""

    def __init__(self, session: MockvisorSession):
        self.session: MockvisorSession = session
        self.request = self.session.request  # "alias" Now self.request(...) is the same as self.session.request(...)

        
    @property
    def status(self) -> VMConfig:
        r = self.request("GET", "/status")
        return VMConfig(r.json())

    @property
    def info(self) -> Box:
        """ Returns information about the connector,
            such as type, version, and capabilities, as a Box.
        """
        return Box({
            "type": "mock_hypervisor",
            "hostURL": self.session.base_URL,
            "user": self.session.user
        })

    def list_vms(self) -> list[VMConnector]:
        r = self.request("GET", "/vms")
        return [MockVMConnector(vm, self) for vm in r.json()]

    def get_vm(self, vm_id: str) -> VMConnector:
        r= self.request("GET", f"/vms/{vm_id}")
        return MockVMConnector(r.json(), self)

    def create_vm(self, config: VMConfig) -> VMConnector:
        r= self.request("POST", "/vms", json=dict(config))
        return MockVMConnector(r.json(), self)

    def clone_vm(self, source_vm: VMConnector, config: VMConfig) -> VMConnector:
        r = self.request("POST", f"/vms/{source_vm.id}/clone", json=dict(config))
        return MockVMConnector(r.json(), self)

    def search_vm(self, query: str) -> list[VMConnector]:
        r = self.request("GET", f"/vms?search={query}")
        r.raise_for_status()
        return [MockVMConnector(vm, self) for vm in r.json()]

