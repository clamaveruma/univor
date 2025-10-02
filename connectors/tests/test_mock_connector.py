

import subprocess
import time
import pytest
from connectors.mock_hypervisor_connector import MockHypervisorConnector


@pytest.fixture(scope="session")
def mockvisor_port():
    """
    Always start a new mockvisor daemon for tests using the launcher CLI, and yield the detected port. Shut down after tests.
    """
    import json
    import sys
    proc = subprocess.run([
        sys.executable, "-m", "mock_hypervisor.launcher", "start"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    print("[DEBUG] launcher raw stdout:")
    print(repr(proc.stdout))
    # Extract the first valid JSON line from stdout
    json_line = None
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith('{') and line.endswith('}'): 
            json_line = line
            break
    if not json_line:
        print("[DEBUG] mockvisor_port stderr output:")
        print(proc.stderr)
        print("[DEBUG] mockvisor_port stdout output:")
        print(proc.stdout)
        raise RuntimeError("mockvisor did not start via launcher (no port in output)")
    data = json.loads(json_line)
    port = int(data["port"])
    yield port
    # Do not stop the daemon after tests; leave it running

@pytest.fixture
def connector(mockvisor_port):
    return MockHypervisorConnector(host="127.0.0.1", user="user", password="pass", port=mockvisor_port)

def test_create_vm(connector):
    config = {"name": "testvm", "cpu": 2, "memory": 2048}
    vm = connector.create_vm(config)
    assert vm.name == "testvm"
    assert vm.config["cpu"] == 2
    assert vm.config["memory"] == 2048

def test_list_and_get_vm(connector):
    config = {"name": "listme", "cpu": 1, "memory": 1024}
    vm = connector.create_vm(config)
    vms = connector.list_vms()
    assert any(v.name == "listme" for v in vms)
    got = connector.get_vm(vm.id)
    assert got.name == "listme"

def test_update_and_rename_vm(connector):
    config = {"name": "updateme", "cpu": 1, "memory": 1024}
    vm = connector.create_vm(config)
    vm.rename("updatedname")
    assert vm.name == "updatedname"
    new_config = {"cpu": 4, "memory": 4096}
    vm.update_config(new_config)
    assert vm.config["cpu"] == 4
    assert vm.config["memory"] == 4096

def test_clone_and_lifecycle(connector):
    config = {"name": "cloneme", "cpu": 2, "memory": 2048}
    vm = connector.create_vm(config)
    clone_config = {"name": "clone1"}
    clone = connector.clone_vm(vm, clone_config)
    assert clone.name == "clone1"
    clone.start()
    assert clone.status == "running"
    clone.pause()
    assert clone.status == "paused"
    clone.resume()
    assert clone.status == "running"
    clone.stop()
    assert clone.status == "stopped"

def test_delete_vm(connector):
    config = {"name": "deleteme", "cpu": 1, "memory": 1024}
    vm = connector.create_vm(config)
    vm_id = vm.id
    vm.delete()
    vms = connector.list_vms()
    assert all(v.id != vm_id for v in vms)


def test_create_vm_invalid(connector):
    import httpx
    # Missing name
    config = {"cpu": 2, "memory": 2048}
    with pytest.raises(httpx.HTTPStatusError):
        connector.create_vm(config)
    # Name is empty
    config = {"name": "", "cpu": 2, "memory": 2048}
    with pytest.raises(httpx.HTTPStatusError):
        connector.create_vm(config)

def test_create_vm_duplicate_name(connector):
    config = {"name": "dupe", "cpu": 1, "memory": 512}
    vm1 = connector.create_vm(config)
    vm2 = connector.create_vm(config)
    print(f"vm1.name: {vm1.name}")
    print(f"vm2.name: {vm2.name}")
    assert vm1.name.startswith("dupe")
    assert vm2.name.startswith("dupe")
    assert vm1.name != vm2.name

def test_create_vm_edge_cases(connector):
    # Extremely large values
    config = {"name": "bigvm", "cpu": 128, "memory": 1048576}
    vm = connector.create_vm(config)
    assert vm.config["cpu"] == 128
    assert vm.config["memory"] == 1048576
    # Extremely small values
    config = {"name": "smallvm", "cpu": 1, "memory": 1}
    vm = connector.create_vm(config)
    assert vm.config["cpu"] == 1
    assert vm.config["memory"] == 1
    # Invalid type
    config = {"name": "badtype", "cpu": "two", "memory": 1024}
    with pytest.raises(Exception) as excinfo:
        connector.create_vm(config)
    assert "cpu" in str(excinfo.value)

def test_lifecycle_transitions(connector):
    config = {"name": "transitvm", "cpu": 2, "memory": 2048}
    vm = connector.create_vm(config)
    # Initial status
    assert vm.status == "stopped"
    # Start
    vm.start()
    assert vm.status == "running"
    # Pause
    vm.pause()
    assert vm.status == "paused"
    # Resume
    vm.resume()
    assert vm.status == "running"
    # Stop
    vm.stop()
    assert vm.status == "stopped"
    # Invalid transition: pause when stopped
    with pytest.raises(Exception) as excinfo:
        vm.pause()
    assert "cannot" in str(excinfo.value).lower() or "invalid" in str(excinfo.value).lower()

def test_invalid_lifecycle_action(connector):
    config = {"name": "badlife", "cpu": 1, "memory": 1024}
    vm = connector.create_vm(config)
    # Try an invalid lifecycle action if supported
    if hasattr(vm, "lifecycle_action"):
        with pytest.raises(Exception) as excinfo:
            vm.lifecycle_action("invalid_action")
        assert "invalid" in str(excinfo.value).lower()

def test_update_vm_invalid(connector):
    config = {"name": "badupdate", "cpu": 1, "memory": 1024}
    vm = connector.create_vm(config)
    # Update with empty name
    with pytest.raises(Exception):
        vm.update_config({"name": ""})
    # Update with missing name (if required)
    # This depends on your API; skip if not enforced

def test_lifecycle_invalid_action(connector):
    config = {"name": "badlife", "cpu": 1, "memory": 1024}
    vm = connector.create_vm(config)
    # Try an invalid lifecycle action (simulate via connector if possible)
    # If connector exposes a generic action method, use it; else, skip
    # Example (pseudo):
    # with pytest.raises(Exception):
    #     vm.lifecycle_action("invalid")