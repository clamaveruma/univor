def handle_result(result, success_message):
    if result.returncode == 0:
        print_and_log(success_message)
    else:
        print_error(result.stderr.strip())
        raise typer.Exit(result.returncode)

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
app = typer.Typer()


SERVICE_NAME = "mock_hypervisor"


@app.command()
def start(port: int = typer.Option(None, help="Port to start the daemon on (optional)")):
    """Start the mock_hypervisor daemon using systemd-run."""
    import sys
    python_executable = sys.executable
    cmd = [
        "systemd-run", "--user", "--unit", SERVICE_NAME, python_executable, "-m", "mock_hypervisor.daemon"
    ]
    if port is not None:
        cmd += ["--port", str(port)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    _handle_result(result, result.stdout.strip())


@app.command()
def stop():
    """Stop the mock_hypervisor daemon."""
    result = subprocess.run([
        "systemctl", "--user", "stop", f"run-{SERVICE_NAME}.service"
    ], capture_output=True, text=True)
    _handle_result(result, "Daemon stopped.")


@app.command()
def kill():
    """Forcefully kill the mock_hypervisor daemon."""
    result = subprocess.run([
        "systemctl", "--user", "kill", f"run-{SERVICE_NAME}.service"
    ], capture_output=True, text=True)
    _handle_result(result, "Daemon killed.")

@app.command()
def status():
    """Show the status of the mock_hypervisor daemon."""
    result = subprocess.run([
        "systemctl", "--user", "status", f"run-{SERVICE_NAME}.service"
    ], capture_output=True, text=True)
    _handle_result(result, result.stdout.strip())

if __name__ == "__main__":
    setup_logging(app_name="mock_hypervisor_launcher", daemon=False)
    monkeypatch_print()
    app()



# Handle the result of a subprocess command, private function
def _handle_result(result, success_message):
    if result.returncode == 0:
        print_and_log(success_message)
    else:
        print_error(result.stderr.strip())
        raise typer.Exit(result.returncode)
