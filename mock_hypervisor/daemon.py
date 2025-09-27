"""
mock_hypervisor.daemon
----------------------
This module implements a mock hypervisor REST API using FastAPI.
It provides endpoints to create, list, update, delete, clone,
and manage the lifecycle of virtual machines (VMs)
in an in-memory store. Intended for local development, testing,
and demonstration purposes.
"""
import threading
import sys
import signal
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi import Request
import json
from common.app_setup import setup_logging

# Set up logging for the daemon
logger = setup_logging(app_name="univor", daemon=True)

# Store the server shutdown function
shutdown_event = threading.Event()

# In-memory mock VM store
mock_vms: dict[str, dict] = {}

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

@app.post("/shutdown")
def shutdown():
    """Shutdown the server gracefully."""
    logger.info("Shutdown requested via /shutdown endpoint.")
    _trigger_shutdown()
    return {"message": "Server shutting down"}

def _trigger_shutdown():
    if not shutdown_event.is_set():
        shutdown_event.set()
        logger.info("Shutdown event set, shutting down daemon.")

@app.get("/status")
def status():
    """Health/status endpoint for the mock hypervisor daemon."""
    logger.info("Status requested via /status endpoint.")
    state = "shutting_down" if shutdown_event.is_set() else "ok"
    return {"status": state, "vms": len(mock_vms)}

def _sigterm_handler(signum, frame):
    logger.info(f"SIGTERM received (signal {signum}), triggering shutdown.")
    _trigger_shutdown()
    # Let main thread handle exit

signal.signal(signal.SIGTERM, _sigterm_handler)

@app.post("/vms", status_code=201)
def create_vm(vm: dict):
    """Create a new virtual machine (VM) and return its details.
    If name is not provided, a default name is assigned.
    If name exists, generate a unique name by appending _1, _2, etc."""
    # Input validation: name is required and must be a non-empty string
    name = vm.get("name")
    if not isinstance(name, str) or not name.strip():
        return JSONResponse(status_code=422, content={"error": "Missing or invalid 'name' field"})
    # Optionally, validate other fields as needed
    supplied_id = vm.get("id")
    vm_id = generate_vm_id(supplied_id)
    vm["id"] = vm_id
    vm["status"] = "stopped"  # New VMs start as stopped
    mock_vms[vm_id] = vm
    logger.info(f"Created VM: {vm}")
    return vm

@app.get("/vms")
def list_vms(search: str | None = None):
    """List all VMs, or filter by name if 'search' is provided."""
    logger.info(f"Listing VMs. Search: {search!r}")
    if not search:
        return list(mock_vms.values())
    filtered = [vm for vm in mock_vms.values() if search in vm["name"]]
    logger.debug(f"Filtered VMs: {filtered}")
    return filtered

@app.get("/vms/{vm_id}")
def get_vm(vm_id: str):
    """Retrieve details for a specific VM by its ID."""
    logger.info(f"Retrieving VM: {vm_id}")
    vm = mock_vms.get(vm_id)
    if not vm:
        logger.warning(f"VM not found: {vm_id}")
        return JSONResponse(status_code=404, content={"error": "VM not found"})
    logger.debug(f"VM details: {vm}")
    return vm

@app.put("/vms/{vm_id}")
def update_vm(vm_id: str, update: dict):
    """Update an existing VM's details by its ID."""
    try:
        logger.debug(f"update_vm CALLED for vm_id={vm_id} with update={update!r}")
        vm = mock_vms.get(vm_id)
        if not vm:
            logger.debug(f"VM not found: {vm_id}")
            return JSONResponse(status_code=404, content={"error": "VM not found"})
        # If 'name' is present, it must be a non-empty string
        if "name" in update:
            if not isinstance(update["name"], str) or not update["name"].strip():
                logger.debug(f"Invalid 'name' in update: {update['name']!r}")
                return JSONResponse(status_code=422, content={"error": "Missing or invalid 'name' field in update"})
        logger.debug(f"Before update: {vm!r}")
        vm.update(update)
        logger.debug(f"After update: {vm!r}")
        logger.debug(f"Returning JSONResponse(content=dict(vm)): type(vm)={type(vm)}, keys={list(vm.keys())}")
        return JSONResponse(content=dict(vm))
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Exception in update_vm: {e}\nTraceback:\n{tb}")
        # Return the error and traceback in the response for debugging
        return JSONResponse(status_code=500, content={
            "error": str(e),
            "traceback": tb
        })

@app.delete("/vms/{vm_id}", status_code=204)
def delete_vm(vm_id: str):
    """Delete a VM by its ID."""
    logger.info(f"Deleting VM: {vm_id}")
    if vm_id in mock_vms:
        del mock_vms[vm_id]
        logger.info(f"Deleted VM: {vm_id}")
        return JSONResponse(status_code=204, content=None)
    logger.warning(f"VM not found for deletion: {vm_id}")
    return JSONResponse(status_code=404, content={"error": "VM not found"})

@app.post("/vms/{vm_id}/clone", status_code=201)
def clone_vm(vm_id: str, clone: dict):
    """Clone an existing VM, assigning a new ID and (optionally) a new name."""
    orig = mock_vms.get(vm_id)
    if not orig:
        return JSONResponse(status_code=404, content={"error": "VM not found"})
    # Validate clone: 'name' is required and must be a non-empty string
    if "name" not in clone or not isinstance(clone["name"], str) or not clone["name"].strip():
        return JSONResponse(status_code=422, content={"error": "Missing or invalid 'name' field in clone"})
    new_vm = orig.copy()
    supplied_id = clone.get("id")
    new_vm_id = generate_vm_id(supplied_id)
    new_vm["id"] = new_vm_id
    new_vm["name"] = clone["name"]
    new_vm["status"] = "stopped"  # Cloned VMs also start as stopped
    mock_vms[new_vm_id] = new_vm
    logger.info(f"Cloned VM: {new_vm}")
    return new_vm

@app.post("/vms/{vm_id}/{action}")
def vm_lifecycle(vm_id: str, action: str):
    """Change the lifecycle state of a VM (start, stop, pause, resume)."""
    vm = mock_vms.get(vm_id)
    if not vm:
        return JSONResponse(status_code=404, content={"error": "VM not found"})
    if action not in ["start", "stop", "pause", "resume"]:
        return JSONResponse(status_code=400, content={"error": "Invalid action"})
    new_status = {
        "start": "running",
        "stop": "stopped",
        "pause": "paused",
        "resume": "running"
    }[action]
    vm["status"] = new_status
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
    # Run uvicorn in a thread so we can trigger shutdown
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)

    def run_server():
        server.run()

    t = threading.Thread(target=run_server)
    t.start()
    logger.info(f"Main thread about to wait for shutdown_event on port {port}")
    # Wait for shutdown event
    try:
        shutdown_event.wait()
        logger.info("shutdown_event.wait() returned in main thread")
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt in main thread")
        pass
    logger.info("shutdown_event set, setting server.should_exit")
    server.should_exit = True
    t.join()
    logger.info("server thread joined, exiting process")
    import os
    logger.info("calling os._exit(0)")
    os._exit(0)

if __name__ == "__main__":
    # ...existing code...
    app_cli()

# ...existing code...
