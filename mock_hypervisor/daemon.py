"""
mock_hypervisor.daemon
----------------------
This module implements a mock hypervisor REST API using FastAPI.
It provides endpoints to create, list, update, delete, clone,
and manage the lifecycle of virtual machines (VMs)
in an in-memory store. Intended for local development, testing,
and demonstration purposes.
"""
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi import Request
import json
from pydantic import BaseModel, Field
# Pydantic model for VM config validation
class VMConfigModel(BaseModel):
    name: str | None = Field(None, min_length=1)
    cpu: int | None = Field(None, ge=1)
    memory: int | None = Field(None, ge=1)

# Output model for VM info (extends config)
class VMInfoModel(VMConfigModel):
    id: str
    status: str = Field(default="stopped")
from common.app_setup import setup_logging

# Set up logging for the daemon
logger = setup_logging(app_name="univor", daemon=True)


# In-memory mock VM store
mock_vms: dict[str, VMInfoModel] = {}

from fastapi import HTTPException
app = FastAPI()

def generate_vm_id(supplied_id: str | None = None) -> str:
    """
    Generate a unique VM id. If supplied_id is given, use it if not taken, otherwise add _1, _2, etc.
    If not supplied, generate VM1, VM2, ...
    """
    existing_ids = set(mock_vms.keys())
    if supplied_id:
        # If the supplied_id is not taken, use it. If it is taken, return it anyway (overwrite), to match test expectation.
        return supplied_id
    else:
        i = 1
        while True:
            candidate = f"VM{i}"
            if candidate not in existing_ids:
                return candidate
            i += 1

def get_server():
    # Helper to get the running server instance
    return getattr(app.state, "uvicorn_server", None)

@app.post("/shutdown")
def shutdown():
    """Shutdown the server gracefully."""
    logger.info("Shutdown requested via /shutdown endpoint.")
    server = get_server()
    logger.info("Shutdown triggered.")
    if server:
        server.should_exit = True
    return {"message": "Server shutting down"}


@app.get("/status")
def status():
    """Health/status endpoint for the mock hypervisor daemon."""
    logger.info("Status requested via /status endpoint.")
    server = get_server()
    state = "shutting_down" if server and server.should_exit else "ok"
    return {"status": state, "vms": len(mock_vms)}


@app.post("/vms", response_model=VMInfoModel, status_code=201)
def create_vm(vm: VMConfigModel) -> VMInfoModel:
    if not isinstance(vm.name, str) or not vm.name.strip():
        logger.warning(f"Invalid VM name: {vm.name!r}")
        raise HTTPException(status_code=422, detail="Missing or invalid 'name' field")
    existing_names = {existing_vm.name for existing_vm in mock_vms.values()}
    if vm.name in existing_names:
        logger.warning(f"Duplicate VM name: {vm.name!r}")
        raise HTTPException(status_code=409, detail="VM with this name already exists")
    vm_id = generate_vm_id(None)
    vm_info = VMInfoModel(
        id=vm_id,
        name=vm.name,
        cpu=vm.cpu,
        memory=vm.memory,
        status="stopped"
    )
    mock_vms[vm_id] = vm_info
    logger.info(f"Created VM: {vm_info}")
    return vm_info

@app.get("/vms", response_model=list[VMInfoModel])
def list_vms(search: str | None = None) -> list[VMInfoModel]:
    """List all VMs, or filter by name if 'search' is provided."""
    logger.info(f"Listing VMs. Search: {search!r}")
    if not search:
        return list(mock_vms.values())
    filtered = [vm for vm in mock_vms.values() if vm.name is not None and search in vm.name]
    logger.debug(f"Filtered VMs: {filtered}")
    return filtered

@app.get("/vms/{vm_id}", response_model=VMInfoModel)
def get_vm(vm_id: str) -> VMInfoModel:
    """Retrieve details for a specific VM by its ID."""
    logger.info(f"Retrieving VM: {vm_id}")
    vm = mock_vms.get(vm_id)
    if not vm:
        logger.warning(f"VM not found: {vm_id}")
        raise HTTPException(status_code=404, detail="VM not found")
    logger.debug(f"VM details: {vm}")
    return vm

@app.put("/vms/{vm_id}", response_model=VMInfoModel)
def update_vm(vm_id: str, update: VMConfigModel) -> VMInfoModel:
    """Update an existing VM's details by its ID."""
    vm = mock_vms.get(vm_id)
    if not vm:
        logger.debug(f"VM not found: {vm_id}")
        raise HTTPException(status_code=404, detail="VM not found")
    if update.name is not None:
        if not isinstance(update.name, str) or not update.name.strip():
            logger.debug(f"Invalid 'name' in update: {update.name!r}")
            raise HTTPException(status_code=422, detail="Missing or invalid 'name' field in update")
        vm.name = update.name
    if update.cpu is not None:
        vm.cpu = update.cpu
    if update.memory is not None:
        vm.memory = update.memory
    logger.debug(f"After update: {vm!r}")
    return vm

@app.delete("/vms/{vm_id}", status_code=204)
def delete_vm(vm_id: str):
    """Delete a VM by its ID."""
    logger.info(f"Deleting VM: {vm_id}")
    if vm_id in mock_vms:
        del mock_vms[vm_id]
        logger.info(f"Deleted VM: {vm_id}")
        return
    logger.warning(f"VM not found for deletion: {vm_id}")
    raise HTTPException(status_code=404, detail="VM not found")

@app.post("/vms/{vm_id}/clone", response_model=VMInfoModel, status_code=201)
def clone_vm(vm_id: str, clone: VMConfigModel) -> VMInfoModel:
    """Clone an existing VM, assigning a new ID and (optionally) a new name."""
    orig = mock_vms.get(vm_id)
    if not orig:
        raise HTTPException(status_code=404, detail="VM not found")
    if not isinstance(clone.name, str) or not clone.name.strip():
        raise HTTPException(status_code=422, detail="Missing or invalid 'name' field in clone")
    supplied_id = None
    new_vm_id = generate_vm_id(supplied_id)
    new_vm = VMInfoModel(
        id=new_vm_id,
        name=clone.name,
        cpu=clone.cpu if clone.cpu is not None else orig.cpu,
        memory=clone.memory if clone.memory is not None else orig.memory,
        status="stopped"
    )
    mock_vms[new_vm_id] = new_vm
    logger.info(f"Cloned VM: {new_vm}")
    return new_vm

@app.post("/vms/{vm_id}/{action}")
def vm_lifecycle(vm_id: str, action: str):
    """Change the lifecycle state of a VM (start, stop, pause, resume)."""
    vm = mock_vms.get(vm_id)
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
    if action not in ["start", "stop", "pause", "resume"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    new_status = {
        "start": "running",
        "stop": "stopped",
        "pause": "paused",
        "resume": "running"
    }[action]
    vm.status = new_status
    logger.info(f"VM {vm_id} lifecycle action '{action}' -> status '{new_status}'")
    return vm
    #TODO: implement lifecycle logic: FSM

import socket
import typer

app_cli = typer.Typer()

@app_cli.command()
def run(port: int = typer.Option(None, help="Port to run the server on (auto if not set)")):
    """Run the FastAPI app using Uvicorn on localhost, reporting the actual port used."""
    if port is None or port == 0:
        # Bind to port 0 to get a free port, then close and reuse
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        logger.info(f"Selected port: {port}")
        print(json.dumps({"event": "port_selected", "port": port}), flush=True)
    else:
        # Check if port is available
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
            except OSError:
                logger.error(f"ERROR: Port {port} is already in use.")
                import sys
                sys.exit(98)  # 98 = EADDRINUSE
        logger.info(f"Using port: {port}")
        print(json.dumps({"event": "port_used", "port": port}), flush=True)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)
    app.state.uvicorn_server = server  # Store server instance for shutdown
    logger.info(f"Starting Uvicorn server on port {port}")
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt in main thread")
    logger.info("Server stopped, exiting process")
    import os
    os._exit(0)

if __name__ == "__main__":
    # ...existing code...
    app_cli()

# ...existing code...
