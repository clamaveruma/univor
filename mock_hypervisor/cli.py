"""
This file is the entry point for the 'mockvisor' command-line tool.
Run 'mockvisor' in your shell to use the CLI.
"""
import typer
import psutil
from common.app_setup import setup_logging, set_print_logger, monkeypatch_print, print_and_log, print_error
import subprocess
import sys
import os
import signal
import httpx

app = typer.Typer()

# Set up logging for the CLI (not daemon)
logger = setup_logging(app_name="mockvisor", daemon=False)
set_print_logger(logger)  ## TODO: move inside setup_logging
monkeypatch_print()

@app.command()
def start_server(port: int = typer.Option(None, help="Port to run the server on (auto if not set)")):
    """Start a new mock hypervisor server (daemon) in the background."""
    cmd = [sys.executable, '-m', 'mock_hypervisor.daemon']
    if port:
        cmd += ["--port", str(port)]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        print_and_log(f"Started mockvisord with PID {proc.pid} on port {port or 'auto'}.")
    except Exception as e:
        print_error(f"Failed to start mockvisord: {e}")

# List running mockvisord daemons and their listening ports
@app.command()
def list_servers():
    """List running mockvisord daemons and their listening ports."""
    found = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Match process by name or command line
            if (
                proc.info['name'] == 'mockvisord' or
                (proc.info['cmdline'] and 'mockvisord' in ' '.join(proc.info['cmdline']))
            ):
                cons = proc.net_connections(kind='inet')
                listen_ports = [c.laddr.port for c in cons if c.status == psutil.CONN_LISTEN]
                if listen_ports:
                    for port in listen_ports:
                        print_and_log(f"PID: {proc.pid} | Port: {port} | Cmd: {' '.join(proc.info['cmdline'])}")
                else:
                    print_and_log(f"PID: {proc.pid} | No listening port found | Cmd: {' '.join(proc.info['cmdline'])}")
                found = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if not found:
        print_and_log("No running mockvisord daemons found.")


@app.command()
def stop_server(port: int = typer.Argument(..., help="Port of the server")):
    """Gracefully stop a running server via REST API (localhost only)."""
    url = f"http://127.0.0.1:{port}/shutdown"
    try:
        response = httpx.post(url, timeout=5)
        if response.status_code == 200:
            print_and_log(f"Server at 127.0.0.1:{port} stopped gracefully.")
        else:
            print_error(f"Failed to stop server at 127.0.0.1:{port}: {response.status_code} {response.text}")
    except Exception as e:
        print_error(f"Error contacting server at 127.0.0.1:{port}: {e}")

@app.command()
def kill_server(pid: int = typer.Argument(..., help="PID of the server process to kill")):
    """Force kill a running server by PID (sends SIGTERM)."""
    try:
        os.kill(pid, signal.SIGTERM)
        print_and_log(f"Sent SIGTERM to process {pid}.")
    except Exception as e:
        print_error(f"Failed to kill process {pid}: {e}")

if __name__ == "__main__":
    app()
