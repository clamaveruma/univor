"""
launcher.py
-----------
A CLI to manage the mock_hypervisor daemon using Python subprocess (cross-platform, WSL-friendly).
Finds the daemon process using psutil, no PID file needed.
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
import os
import signal
import sys
import time
import psutil

app = typer.Typer(add_completion=False, help="Manage the mock_hypervisor daemon. If no port is passed to start, an automatic port will be selected. If no command is given, status is shown.")

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        ctx.invoke(status)
        print("[bold yellow]Tip:[/bold yellow] Use [green]--help[/green] to see all available commands.")

def _start_daemon(port=None):
    """Start the daemon, optionally with a specific port. Returns (pid, port)."""
    python_executable = sys.executable
    if port is None: port = 0
    cmd = [python_executable, '-m', 'mock_hypervisor.daemon', '--port', str(port)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, close_fds=True)
    selected_port = None
    assert proc.stdout is not None
    for _ in range(10):
        line = proc.stdout.readline()
        if not line:
            break
        if "[MOCKDAEMON] Selected port:" in line or "[MOCKDAEMON] Using port:" in line:
            try:
                selected_port = int(line.strip().split(":")[-1])
            except Exception:
                selected_port = None
            break
    time.sleep(0.5)
    if proc.poll() is not None:
        print_error(f"Failed to start daemon. Process exited with code {proc.returncode}.")
        raise typer.Exit(1)
    return proc.pid, selected_port or port



@app.command()
def start(port: int = typer.Option(None, help="Port to start the daemon on (optional, auto if not set)")):
    """Start the mock_hypervisor daemon as a background process. If no port is given, an automatic port will be selected and displayed."""
    daemon_pid = _find_daemon_pid()
    if daemon_pid:
        print_error(f"A mock_hypervisor daemon is already running with PID {daemon_pid}. Only one instance is allowed.")
        raise typer.Exit(1)
    pid, used_port = _start_daemon(port)
    print_and_log(json.dumps({"returncode": 0, "msg": f"Started daemon with PID {pid}", "pid": pid, "port": used_port}))

@app.command()
def stop():
    """Stop the mock_hypervisor daemon by finding its process."""
    pid = _find_daemon_pid()
    if not pid:
        print_error("Daemon not running.")
        raise typer.Exit(1)
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        if not _pid_running(pid):
            print_and_log(json.dumps({"returncode": 0, "msg": f"Stopped daemon with PID {pid}"}))
        else:
            print_error(f"Failed to stop daemon with PID {pid}.")
            raise typer.Exit(1)
    except Exception as e:
        print_error(f"Error stopping daemon: {e}")
        raise typer.Exit(1)

@app.command()
def kill():
    """Forcefully kill the mock_hypervisor daemon by finding its process."""
    pid = _find_daemon_pid()
    if not pid:
        print_error("Daemon not running.")
        raise typer.Exit(1)
    try:
        os.kill(pid, signal.SIGKILL)
        time.sleep(1)
        if not _pid_running(pid):
            print_and_log(json.dumps({"returncode": 0, "msg": f"Killed daemon with PID {pid}"}))
        else:
            print_error(f"Failed to kill daemon with PID {pid}.")
            raise typer.Exit(1)
    except Exception as e:
        print_error(f"Error killing daemon: {e}")
        raise typer.Exit(1)

@app.command()
def status():
    """Show the status of the mock_hypervisor daemon by finding its process."""
    pid = _find_daemon_pid()
    if not pid:
        print_and_log(json.dumps({"returncode": 1, "msg": "Daemon not running."}))
        raise typer.Exit(1)
    port = _get_listening_port_of_pid(pid)
    print_and_log(json.dumps({"returncode": 0, "msg": f"Daemon running with PID {pid}", "pid": pid, "port": port or "unknown"}))

def _pid_running(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def _find_daemon_pid():
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['cmdline'] and 'mock_hypervisor.daemon' in ' '.join(proc.info['cmdline']):
                return proc.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def _get_listening_port_of_pid(pid: int) -> int | None:
    try:
        proc = psutil.Process(pid)
        cons = proc.connections(kind='inet')
        for c in cons:
            if c.status == psutil.CONN_LISTEN:
                return c.laddr.port
    except Exception:
        pass
    return None

setup_logging(app_name="mock_hypervisor_launcher", daemon=False)
monkeypatch_print()

if __name__ == "__main__":
    app()