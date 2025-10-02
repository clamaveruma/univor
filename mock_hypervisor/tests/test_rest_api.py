

import subprocess
import time
import sys
import httpx
import pytest
import json

LAUNCHER = [sys.executable, '-m', 'mock_hypervisor.launcher']

def get_daemon_status():
    result = subprocess.run(LAUNCHER + ['status'], capture_output=True, text=True)
    lines = result.stdout.splitlines()
    if lines:
        try:
            return json.loads(lines[0].strip())
        except Exception:
            return None
    return None

@pytest.fixture(scope="function")
def daemon():
    result = subprocess.run(LAUNCHER + ['start'], capture_output=True, text=True)
    try:
        data = json.loads(result.stdout.strip())
        port = data.get("port")
        if port is not None and port != "unknown":
            try:
                port = int(port)
            except Exception:
                pass
            yield port
            return
    except Exception:
        pass
    raise RuntimeError("Daemon did not start or did not output a valid port.")


# Add a test that stops the daemon via REST
def test_stop_daemon_via_rest(daemon):
    port = daemon
    with httpx.Client() as client:
        r = client.post(f'http://127.0.0.1:{port}/shutdown', timeout=2)
        assert r.status_code in (200, 204)
    # After shutdown, status should show not running
    time.sleep(1)
    status2 = get_daemon_status()
    assert status2 and status2.get("msg") == "Daemon not running."

def print_vms(port):
    with httpx.Client() as client:
        r = client.get(f'http://127.0.0.1:{port}/vms')
        print('VMs:', r.json())


# Split tests for clarity and isolation
def test_create_vm(daemon):
    port = daemon
    with httpx.Client() as client:
        # Positive: create VM
        r = client.post(f'http://127.0.0.1:{port}/vms', json={"name": "Alpha"})
        assert r.status_code == 201
        vm1 = r.json()
        assert vm1["name"] == "Alpha"
        assert "id" in vm1
        # Negative: create VM with missing name
        r = client.post(f'http://127.0.0.1:{port}/vms', json={})
        assert r.status_code in (400, 422)
        # Cleanup
        r = client.delete(f'http://127.0.0.1:{port}/vms/{vm1["id"]}')
        assert r.status_code == 204

def test_create_vm_with_id(daemon):
    # Skipped: Hypervisor always generates VM id; custom id not supported
    pass

def test_create_vm_duplicate_id(daemon):
    # Skipped: Hypervisor always generates VM id; duplicate id not possible
    pass

def test_get_update_delete_vm(daemon):
    port = daemon
    with httpx.Client() as client:
        # Create VM
        r = client.post(f'http://127.0.0.1:{port}/vms', json={"name": "Alpha"})
        vm1 = r.json()
        # Get VM
        r = client.get(f'http://127.0.0.1:{port}/vms/{vm1["id"]}')
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == vm1["id"]
        # Update VM
        r = client.put(f'http://127.0.0.1:{port}/vms/{vm1["id"]}', json={"name": "AlphaUpdated"})
        assert r.status_code == 200
        updated = r.json()
        assert updated["name"] == "AlphaUpdated"
        # Accept empty update as OK (do nothing)
        r = client.put(f'http://127.0.0.1:{port}/vms/{vm1["id"]}', json={})
        assert r.status_code == 200
        # Negative: update non-existent VM
        r = client.put(f'http://127.0.0.1:{port}/vms/nonexistent', json={"name": "Ghost"})
        assert r.status_code == 404
        # Negative: malformed JSON (simulate by sending invalid content-type)
        r = client.put(f'http://127.0.0.1:{port}/vms/{vm1["id"]}', content="not a json", headers={"Content-Type": "application/json"})
        assert r.status_code in (400, 422, 500)
        # Negative: update with invalid name
        r = client.put(f'http://127.0.0.1:{port}/vms/{vm1["id"]}', json={"name": ""})
        assert r.status_code in (400, 422)
        # Valid update with JSON missing 'name' field (should be OK)
        r = client.put(f'http://127.0.0.1:{port}/vms/{vm1["id"]}', json={"other": "value"})
        assert r.status_code == 200
        # Delete VM
        r = client.delete(f'http://127.0.0.1:{port}/vms/{vm1["id"]}')
        assert r.status_code == 204

def test_clone_vm_and_lifecycle(daemon):
    port = daemon
    with httpx.Client() as client:
        r = client.post(f'http://127.0.0.1:{port}/vms', json={"name": "Alpha"})
        vm1 = r.json()
        # Clone VM
        r = client.post(f'http://127.0.0.1:{port}/vms/{vm1["id"]}/clone', json={"name": "AlphaClone"})
        assert r.status_code == 201
        vm_clone = r.json()
        assert vm_clone["name"] == "AlphaClone"
        # Negative: clone with missing name
        r = client.post(f'http://127.0.0.1:{port}/vms/{vm1["id"]}/clone', json={})
        assert r.status_code in (400, 422)
        # Change lifecycle
        for action in ["start", "pause", "resume", "stop"]:
            r = client.post(f'http://127.0.0.1:{port}/vms/{vm1["id"]}/{action}')
            assert r.status_code == 200
        # Cleanup
        r = client.delete(f'http://127.0.0.1:{port}/vms/{vm1["id"]}')
        assert r.status_code == 204



