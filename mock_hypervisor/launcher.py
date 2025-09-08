"""
launcher.py
-----------
A CLI to manage the mock_hypervisor daemon using systemd-run.
Systemd ensures only one instance can run at a time.
"""

from common.app_setup import (
    print_and_log,
    print_error,
    setup_logging,
    monkeypatch_print,
)


import subprocess
import typer

import json

app = typer.Typer()

SERVICE_NAME = "mock_hypervisor"


@app.command()
def start(
    port: int = typer.Option(None, help="Port to start the daemon on (optional)")
):
    """Start the mock_hypervisor daemon using systemd-run."""
    import sys
    python_executable = sys.executable
    cmd = [
        "systemd-run", "--user", "--unit", SERVICE_NAME, python_executable, "-m", "mock_hypervisor.daemon"
    ]
    if port is not None:
        cmd += ["--port", str(port)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    _handle_result(result)



@app.command()
def stop():
    """Stop the mock_hypervisor daemon."""
    result = subprocess.run([
        "systemctl", "--user", "stop", f"run-{SERVICE_NAME}.service"
    ], capture_output=True, text=True)
    _handle_result(result)


@app.command()
def kill():
    """Forcefully kill the mock_hypervisor daemon."""
    result = subprocess.run([
        "systemctl", "--user", "kill", f"run-{SERVICE_NAME}.service"
    ], capture_output=True, text=True)
    _handle_result(result)

@app.command()
def status():
    """Show the status of the mock_hypervisor daemon."""
    result = subprocess.run([
        "systemctl", "--user", "status", f"run-{SERVICE_NAME}.service"
    ], capture_output=True, text=True)
        # get the PID:
    pid = _get_pid_of_service(f"run-{SERVICE_NAME}.service")
    port = _get_listening_port_of_pid(pid) if pid else None
    _handle_result(result, {"port": port if port else "unknown"})


setup_logging(app_name="mock_hypervisor_launcher", daemon=False)
monkeypatch_print()
if __name__ == "__main__":
    app()



##### tools:
# Handle the result of a subprocess command, private function
def _handle_result(process_result, extra_data: dict = {}):
    return_code = process_result.returncode
    output = {
        "returncode": return_code,
        "msg": process_result.stdout.strip() or process_result.stderr.strip()
    }
    # merge extra_data dict:
    output.update(extra_data)
   
    json_out = json.dumps(output)

    if return_code == 0:
        print_and_log(json_out)
    else:
        print_error(json_out)
        raise typer.Exit(return_code)

def _get_pid_of_service(service_name: str) -> int | None:
    """Get the main PID of a systemd service."""
    result = subprocess.run([
        "systemctl", "--user", "show", service_name, "-p", "MainPID"
    ], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    if output.startswith("MainPID="):
        pid_str = output.split("=")[1]
        try:
            pid = int(pid_str)
            return pid if pid != 0 else None
        except ValueError:
            return None
    return None

def _get_listening_port_of_pid(pid: int) -> int | None:
    result = subprocess.run([
        "ss", "-tnlp", "|", "grep", str(pid)
    ], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    # Parse the output to find the port
    for line in output.splitlines():
        parts = line.split()
        if len(parts) > 4:
            return int(parts[4].split(":")[-1])
    return None