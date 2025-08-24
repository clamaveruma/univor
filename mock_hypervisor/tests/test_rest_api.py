import pytest
import httpx

BASE_URL = "http://localhost:8000"  # Adjust as needed for test server


def test_create_vm():
    """Test creating a new VM via REST API."""
    payload = {"name": "testvm1", "cpu": 2, "memory": 2048}
    with httpx.Client() as client:
        response = client.post(f"{BASE_URL}/vms", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "testvm1"
        assert data["cpu"] == 2
        assert data["memory"] == 2048

def test_list_vms():
    """Test listing VMs."""
    with httpx.Client() as client:
        response = client.get(f"{BASE_URL}/vms")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

def test_get_vm():
    """Test retrieving a VM by ID."""
    payload = {"name": "testvm2", "cpu": 1, "memory": 1024}
    with httpx.Client() as client:
        create_resp = client.post(f"{BASE_URL}/vms", json=payload)
        vm_id = create_resp.json()["id"]
        response = client.get(f"{BASE_URL}/vms/{vm_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == vm_id

def test_update_vm():
    """Test updating a VM's configuration."""
    payload = {"name": "testvm3", "cpu": 1, "memory": 1024}
    with httpx.Client() as client:
        create_resp = client.post(f"{BASE_URL}/vms", json=payload)
        vm_id = create_resp.json()["id"]
        update_payload = {"cpu": 4, "memory": 4096}
        response = client.put(f"{BASE_URL}/vms/{vm_id}", json=update_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["cpu"] == 4
        assert data["memory"] == 4096

def test_delete_vm():
    """Test deleting a VM."""
    payload = {"name": "testvm4", "cpu": 1, "memory": 1024}
    with httpx.Client() as client:
        create_resp = client.post(f"{BASE_URL}/vms", json=payload)
        vm_id = create_resp.json()["id"]
        response = client.delete(f"{BASE_URL}/vms/{vm_id}")
        assert response.status_code == 204

def test_clone_vm():
    """Test cloning a VM."""
    payload = {"name": "testvm5", "cpu": 2, "memory": 2048}
    with httpx.Client() as client:
        create_resp = client.post(f"{BASE_URL}/vms", json=payload)
        vm_id = create_resp.json()["id"]
        clone_payload = {"name": "testvm5_clone"}
        response = client.post(f"{BASE_URL}/vms/{vm_id}/clone", json=clone_payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "testvm5_clone"

def test_vm_lifecycle():
    """Test VM lifecycle operations: start, stop, pause, resume."""
    payload = {"name": "testvm6", "cpu": 1, "memory": 1024}
    with httpx.Client() as client:
        create_resp = client.post(f"{BASE_URL}/vms", json=payload)
        vm_id = create_resp.json()["id"]
        for action in ["start", "pause", "resume", "stop"]:
            response = client.post(f"{BASE_URL}/vms/{vm_id}/{action}")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["running", "paused", "stopped"]

def test_search_vms():
    """Test searching for VMs by name."""
    with httpx.Client() as client:
        response = client.get(f"{BASE_URL}/vms?search=testvm")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
