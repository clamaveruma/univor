import subprocess
import time
import socket
import sys
import httpx



def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def start_daemon(port):
    cmd = [sys.executable, '-m', 'mock_hypervisor.daemon', '--port', str(port)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # Wait for server to start
    for _ in range(30):
        try:
            with httpx.Client() as client:
                r = client.get(f'http://127.0.0.1:{port}/vms', timeout=0.5)
            if r.status_code == 200:
                return proc
        except Exception:
            time.sleep(0.2)
    raise RuntimeError('Daemon did not start')

def shutdown_daemon(port):
    try:
        with httpx.Client() as client:
            client.post(f'http://127.0.0.1:{port}/shutdown', timeout=2)
    except Exception:
        pass

def print_vms(port):
    with httpx.Client() as client:
        r = client.get(f'http://127.0.0.1:{port}/vms')
        print('VMs:', r.json())

def test_rest_api_full():
    port = get_free_port()
    proc = start_daemon(port)
    try:
        with httpx.Client() as client:
            # Create VM without id
            r = client.post(f'http://127.0.0.1:{port}/vms', json={"name": "Alpha"})
            assert r.status_code == 201
            vm1 = r.json()
            print('Created VM:', vm1)
            print_vms(port)

            # Create VM with id
            r = client.post(f'http://127.0.0.1:{port}/vms', json={"id": "custom", "name": "Beta"})
            assert r.status_code == 201
            vm2 = r.json()
            print('Created VM with id:', vm2)
            print_vms(port)

            # Create VM with duplicate id
            r = client.post(f'http://127.0.0.1:{port}/vms', json={"id": "custom", "name": "Gamma"})
            assert r.status_code == 201
            vm3 = r.json()
            print('Created VM with duplicate id:', vm3)
            print_vms(port)

            # Get VM
            r = client.get(f'http://127.0.0.1:{port}/vms/{vm1["id"]}')
            assert r.status_code == 200
            print('Get VM:', r.json())

            # Update VM
            r = client.put(f'http://127.0.0.1:{port}/vms/{vm1["id"]}', json={"name": "AlphaUpdated"})
            assert r.status_code == 200
            print('Updated VM:', r.json())
            print_vms(port)

            # Clone VM
            r = client.post(f'http://127.0.0.1:{port}/vms/{vm1["id"]}/clone', json={"name": "AlphaClone"})
            assert r.status_code == 201
            vm_clone = r.json()
            print('Cloned VM:', vm_clone)
            print_vms(port)

            # Change lifecycle
            for action in ["start", "pause", "resume", "stop"]:
                r = client.post(f'http://127.0.0.1:{port}/vms/{vm1["id"]}/{action}')
                assert r.status_code == 200
                print(f'Lifecycle {action}:', r.json())

            # Delete VM
            r = client.delete(f'http://127.0.0.1:{port}/vms/{vm1["id"]}')
            assert r.status_code == 204
            print('Deleted VM:', vm1["id"])
            print_vms(port)

    finally:
        shutdown_daemon(port)
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.terminate()
            proc.wait(timeout=2)

def test_vm_lifecycle():
    """Test VM lifecycle operations: start, stop, pause, resume."""
    payload = {"name": "testvm6", "cpu": 1, "memory": 1024}
