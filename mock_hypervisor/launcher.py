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
        try:
            msg = json.loads(line)
            if msg.get("event") in ("port_selected", "port_used"):
                selected_port = int(msg["port"])
                break
        except Exception:
            continue
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
        msg = "A mock_hypervisor daemon is already running"
        running_port = _get_listening_port_of_pid(daemon_pid)
        result = {"returncode": 1, "msg": msg, "pid": daemon_pid, "port": running_port or "unknown"}
        exit_code = 1
    except psutil.NoSuchProcess:
        pid, used_port = _start_daemon(port)
        result = {"returncode": 0, "msg": "Started daemon", "pid": pid, "port": used_port}
        exit_code = 0
    print(json.dumps(result))
    raise typer.Exit(exit_code)

@app.command()
def stop():
    """Stop the mock_hypervisor daemon by finding its process."""
    import httpx
    import httpx
    pid = _find_daemon_pid()
    port = _get_listening_port_of_pid(pid)
    # Try graceful shutdown
    if port:
        try:
            httpx.post(f"http://127.0.0.1:{port}/shutdown", timeout=2)
        except Exception:
            pass
    time.sleep(2)
    if not _pid_running(pid):
        print_and_log(json.dumps({"returncode": 0, "msg": f"Stopped daemon (PID {pid}) via /shutdown"}))
        return
    # Fallback to SIGTERM
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass
    time.sleep(1)
    if not _pid_running(pid):
        print_and_log(json.dumps({"returncode": 0, "msg": f"Stopped daemon (PID {pid}) via SIGTERM"}))
        return
    print_and_log(json.dumps({"returncode": 1, "msg": f"Failed to stop daemon (PID {pid})"}))
    raise typer.Exit(1)

@app.command()
def kill():
    """Forcefully kill the mock_hypervisor daemon by finding its process."""
    pid = _find_daemon_pid()
    os.kill(pid, signal.SIGKILL)
    time.sleep(1)
    if not _pid_running(pid):
        print_and_log(json.dumps({"returncode": 0, "msg": f"Killed daemon with PID {pid}"}))
    else:
        print_and_log(json.dumps({"returncode": 1, "msg": f"Failed to kill daemon with PID {pid}."}))
        raise typer.Exit(1)





@app.command()
def status():
    """Show the status of the mock_hypervisor daemon by finding its process and querying the REST API."""
    import httpx
    result = {
        "returncode": 1,
        "msg": "Daemon not running.",
        "running": False,
        "pid": None,
        "port": None,
        "api_status": None
    }
    try:
        pid = _find_daemon_pid()
        port = _get_listening_port_of_pid(pid) or "unknown"
        result["pid"] = pid
        result["port"] = port
        resp = httpx.get(f"http://127.0.0.1:{port}/status", timeout=2)
        if resp.status_code == 200:
            result["api_status"] = resp.json()
            result["msg"] = f"Daemon running with PID {pid}"
            result["running"] = True
            result["returncode"] = 0
        else:
            result["api_status"] = {"error": resp.text}
            result["msg"] = f"Daemon running with PID {pid}, but REST API error"
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        result["msg"] = f"Error checking daemon status: {e}"
        result["api_status"] = {"error": str(e)}
    print_and_log(json.dumps(result))
    
@app.command()
def show_logs():
    """
    Show live logs from syslog filtered by 'univor'.
    """
    subprocess.run("sudo tail -f /var/log/syslog | grep --line-buffered 'univor'", shell=True)

def _pid_running(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def _find_daemon_pid():
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['cmdline'] and \
                'mock_hypervisor.daemon' in ' '.join(proc.info['cmdline']):
                    return proc.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    logger.debug("Daemon not running.")
    raise psutil.NoSuchProcess("Daemon not running.")
    
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


# Assign logger globally
logger = setup_logging(app_name="mock_hypervisor_launcher", daemon=False)
monkeypatch_print()

if __name__ == "__main__":
    app()