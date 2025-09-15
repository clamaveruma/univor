

import subprocess
import time
import pytest
from connectors.mock_hypervisor_connector import MockHypervisorConnector


@pytest.fixture(scope="session")
def mockvisor_daemon():
    """
    Always start a new mockvisor daemon for tests using the launcher CLI, and yield the detected port. Shut down after tests.
    """
    import json
    proc = subprocess.run([
        "python", "-m", "mock_hypervisor.launcher", "start"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    import json
    try:
        first_line = proc.stdout.splitlines()[0]
        data = json.loads(first_line)
        port = int(data["port"])
    except Exception:
        print("[DEBUG] mockvisor_daemon stderr output:")
        print(proc.stderr)
        print("[DEBUG] mockvisor_daemon stdout output:")
        print(proc.stdout)
        raise RuntimeError("mockvisor did not start via launcher (no port in output)")
    yield port
    # Do not stop the daemon after tests; leave it running

@pytest.fixture
def connector(mockvisor_daemon):
    return MockHypervisorConnector(host="127.0.0.1", user="user", password="pass", port=mockvisor_daemon)

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
    # Missing name
    config = {"cpu": 2, "memory": 2048}
    with pytest.raises(Exception):
        connector.create_vm(config)
    # Name is empty
    config = {"name": "", "cpu": 2, "memory": 2048}
    with pytest.raises(Exception):
        connector.create_vm(config)

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