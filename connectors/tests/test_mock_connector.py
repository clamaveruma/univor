import subprocess
import time
import random
import socket
import pytest

from connectors.mock_hypervisor_connector import MockHypervisorConnector

@pytest.fixture(scope="module")
def mock_hypervisor_servers():
    procs = []
    ports = []
    for _ in range(2):
        proc = subprocess.Popen(
            [
                'mockvisor',
                'start',
                '--port', '0',
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        # Read lines until we find the port info
        port = None
        for line in iter(proc.stdout.readline, ''):
            if 'Listening on port' in line:
                # Example: 'Listening on port 12345\n'
                port = int(line.strip().split()[-1])
                break
        if port is None:
            proc.terminate()
            raise RuntimeError('Could not determine port for mockvisor')
        ports.append(port)
        procs.append(proc)
    time.sleep(1)  # Give servers a moment to finish startup
    yield ports
    for proc in procs:
        stop_proc = subprocess.Popen([
            'mockvisor',
            'stop',
            # Optionally, you may need to pass an identifier or port
        ])
        stop_proc.wait()
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
