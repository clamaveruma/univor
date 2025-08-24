"""
mock_hypervisor.daemon
----------------------
This module implements a mock hypervisor REST API using FastAPI. It provides endpoints to create, list, update, delete, clone, and manage the lifecycle of virtual machines (VMs) in an in-memory store. Intended for local development, testing, and demonstration purposes.
"""
import typer
import typer
import uvicorn
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

app = FastAPI()




# In-memory mock VM store
mock_vms = {}
mock_id = 1

@app.post("/vms", status_code=201)
def create_vm(vm: dict):
    """Create a new virtual machine (VM) and return its details."""
    global mock_id
    vm["id"] = str(mock_id)
    mock_vms[vm["id"]] = vm
    mock_id += 1
    return vm

@app.get("/vms")
def list_vms(search: str | None = None):
    """List all VMs, or filter by name if 'search' is provided."""
    if not search:
        return list(mock_vms.values())
    return [vm for vm in mock_vms.values() if search in vm["name"]]

@app.get("/vms/{vm_id}")
def get_vm(vm_id: str):
    """Retrieve details for a specific VM by its ID."""
    vm = mock_vms.get(vm_id)
    if not vm:
        return JSONResponse(status_code=404, content={"error": "VM not found"})
    return vm

@app.put("/vms/{vm_id}")
def update_vm(vm_id: str, update: dict):
    """Update an existing VM's details by its ID."""
    vm = mock_vms.get(vm_id)
    if not vm:
        return JSONResponse(status_code=404, content={"error": "VM not found"})
    vm.update(update)
    return vm

@app.delete("/vms/{vm_id}", status_code=204)
def delete_vm(vm_id: str):
    """Delete a VM by its ID."""
    if vm_id in mock_vms:
        del mock_vms[vm_id]
        return JSONResponse(status_code=204, content=None)
    return JSONResponse(status_code=404, content={"error": "VM not found"})

@app.post("/vms/{vm_id}/clone", status_code=201)
def clone_vm(vm_id: str, clone: dict):
    """Clone an existing VM, assigning a new ID and (optionally) a new name."""
    global mock_id
    orig = mock_vms.get(vm_id)
    if not orig:
        return JSONResponse(status_code=404, content={"error": "VM not found"})
    new_vm = orig.copy()
    new_vm["id"] = str(mock_id)
    new_vm["name"] = clone.get("name", f"clone_{orig['name']}")
    mock_vms[new_vm["id"]] = new_vm
    mock_id += 1
    return new_vm

@app.post("/vms/{vm_id}/{action}")
def vm_lifecycle(vm_id: str, action: str):
    """Change the lifecycle state of a VM (start, stop, pause, resume)."""
    vm = mock_vms.get(vm_id)
    if not vm:
        return JSONResponse(status_code=404, content={"error": "VM not found"})
    if action not in ["start", "stop", "pause", "resume"]:
        return JSONResponse(status_code=400, content={"error": "Invalid action"})
    vm["status"] = {
        "start": "running",
        "stop": "stopped",
        "pause": "paused",
        "resume": "running"
    }[action]
    return vm

def main():
    """Run the FastAPI app using Uvicorn on localhost:8000."""
    uvicorn.run(app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    main()
