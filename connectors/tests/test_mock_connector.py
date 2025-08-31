import subprocess
import time
import random
import socket
import pytest
from connectors.mock_hypervisor_connector import MockHypervisorConnector

def get_free_port():
    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

@pytest.fixture(scope="module")
def mock_hypervisor_servers():
    ports = [get_free_port(), get_free_port()]
    procs = []
    for port in ports:
        proc = subprocess.Popen([
            'mockvisord',
            '--port', str(port),
            '--no-daemon',
        ])
        procs.append(proc)
    time.sleep(2)  # Give servers time to start
    yield ports
    for proc in procs:
        proc.terminate()
        proc.wait()

def test_create_vms_on_multiple_hypervisors(mock_hypervisor_servers):
    port1, port2 = mock_hypervisor_servers
    h1 = MockHypervisorConnector(host='localhost', user='user', password='pass', port=port1)
    h2 = MockHypervisorConnector(host='localhost', user='user', password='pass', port=port2)

    # Example VM configs (adjust as needed)
    config1 = {'name': 'vm1', 'cpu': 2, 'memory': 2048}
    config2 = {'name': 'vm2', 'cpu': 4, 'memory': 4096}

    vm1 = h1.create_vm(config1)
    vm2 = h2.create_vm(config2)

    assert vm1.name == 'vm1'
    assert vm2.name == 'vm2'
    assert vm1.name != vm2.name
    # Ensure VMs are only in their respective hypervisors
    assert all(vm.name == 'vm1' for vm in h1.list_vms())
    assert all(vm.name == 'vm2' for vm in h2.list_vms())
