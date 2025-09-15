"""
launcher.py
-----------
A CLI to manage the mock_hypervisor daemon 

Using Python subprocess (cross-platform, WSL-friendly).
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
        try:
            ctx.invoke(status)
        finally:
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
def start(port: int | None = typer.Option(None, help="Port to start the daemon on (optional, auto if not set)")):
    """Start the mock_hypervisor daemon as a background process. 
    If no port is given, an automatic port will be selected.
    If already running: resturn error.
    returns json in any case.
    """
    result = {}
    exit_code = 0
    try:
        daemon_pid = _find_daemon_pid()
        if daemon_pid:
            msg = "A mock_hypervisor daemon is already running"
            running_port = _get_listening_port_of_pid(daemon_pid)
            result = {"returncode": 1, "msg": msg, "pid": daemon_pid, "port": running_port or "unknown"}
            exit_code = 1
        else:
            pid, used_port = _start_daemon(port)
            result = {"returncode": 0, "msg": "Started daemon", "pid": pid, "port": used_port}
            exit_code = 0
    except Exception as e:
        result = {"returncode": 1, "msg": f"Error: {e}"}
        exit_code = 1
    print(json.dumps(result))
    raise typer.Exit(exit_code)

@app.command()
def stop():
    """Stop the mock_hypervisor daemon by finding its process."""
    try:
        pid = _find_daemon_pid()
        if not pid:
            print(json.dumps({"returncode": 1, "msg": "Daemon not running."}))
            raise typer.Exit(1)
        status_after = None
        try:
            proc = psutil.Process(pid)
            status_before = proc.status()
        except Exception:
            status_before = None
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        try:
            proc = psutil.Process(pid)
            status_after = proc.status()
        except psutil.NoSuchProcess:
            print(json.dumps({"returncode": 0, "msg": f"Stopped daemon with PID {pid}"}))
            return
        except Exception:
            status_after = None
        if not _pid_running(pid):
            print(json.dumps({"returncode": 0, "msg": f"Stopped daemon with PID {pid}"}))
        elif status_after == psutil.STATUS_ZOMBIE:
            print(json.dumps({"returncode": 0, "msg": f"Stopped daemon with PID {pid} (zombie)"}))
        else:
            print(json.dumps({"returncode": 1, "msg": f"Failed to stop daemon with PID {pid}. Status: {status_after if status_after is not None else 'unknown'}"}))
            raise typer.Exit(1)
    except Exception as e:
        print(json.dumps({"returncode": 1, "msg": f"Error stopping daemon: {e}"}))
        raise typer.Exit(1)

@app.command()
def kill():
    """Forcefully kill the mock_hypervisor daemon by finding its process."""
    try:
        pid = _find_daemon_pid()
        if not pid:
            print(json.dumps({"returncode": 1, "msg": "Daemon not running."}))
            raise typer.Exit(1)
        os.kill(pid, signal.SIGKILL)
        time.sleep(1)
        if not _pid_running(pid):
            print(json.dumps({"returncode": 0, "msg": f"Killed daemon with PID {pid}"}))
        else:
            print(json.dumps({"returncode": 1, "msg": f"Failed to kill daemon with PID {pid}."}))
            raise typer.Exit(1)
    except Exception as e:
        print(json.dumps({"returncode": 1, "msg": f"Error killing daemon: {e}"}))
        raise typer.Exit(1)

@app.command()
def status():
    """Show the status of the mock_hypervisor daemon by finding its process."""
    try:
        pid = _find_daemon_pid()
        if not pid:
            print(json.dumps({"returncode": 0, "msg": "Daemon not running.", "running": False, "pid": None, "port": None}))
        else:
            port = _get_listening_port_of_pid(pid)
            print(json.dumps({"returncode": 0, "msg": f"Daemon running with PID {pid}", "running": True, "pid": pid, "port": port or "unknown"}))
    except Exception as e:
        print(json.dumps({"returncode": 1, "msg": f"Error: {e}", "running": False, "pid": None, "port": None}))
        raise typer.Exit(1)

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

def _get_listening_port_of_pid(pid: int | None) -> int | None:
    try:
        proc = psutil.Process(pid)
        cons = proc.net_connections(kind='inet')
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