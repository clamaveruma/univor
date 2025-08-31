"""
test_daemon_logging.py
----------------------
Test that the daemon writes expected log entries for VM lifecycle events.
"""
import os
import tempfile
import subprocess
import time
import httpx
import re
import sys
from pathlib import Path

def test_daemon_logging_lifecycle():
    port = 8000  # Use a fixed port for simplicity
    # Record syslog position before
    syslog_path = "/var/log/syslog"
    with open(syslog_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        start_pos = f.tell()
    # Start the daemon as a subprocess (no UNIVOR_LOGFILE)
    proc = subprocess.Popen([
        sys.executable, "-m", "mock_hypervisor.daemon", "--port", str(port)
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        # Wait for server to start
        time.sleep(1.5)
        # Create a VM
        vm = {"name": "testvm"}
        r = httpx.post(f"http://127.0.0.1:{port}/vms", json=vm)
        assert r.status_code == 201
        vm_id = r.json()["id"]
        # Start the VM
        r2 = httpx.post(f"http://127.0.0.1:{port}/vms/{vm_id}/start")
        assert r2.status_code == 200
        # Stop the VM
        r3 = httpx.post(f"http://127.0.0.1:{port}/vms/{vm_id}/stop")
        assert r3.status_code == 200
        # Clone the VM
        r4 = httpx.post(f"http://127.0.0.1:{port}/vms/{vm_id}/clone", json={"name": "clone1"})
        assert r4.status_code == 201
        # Shutdown
        httpx.post(f"http://127.0.0.1:{port}/shutdown")
        time.sleep(0.5)
    finally:
        proc.terminate()
        proc.wait(timeout=3)
    # Read new syslog entries
    with open(syslog_path, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(start_pos)
        log_content = f.read()
    print("\n===== SYSLOG CONTENT CAPTURED BY TEST =====\n" + log_content + "\n===== END SYSLOG CONTENT =====\n")
    # Check for expected log entries
    assert re.search(r"Created VM:.*testvm", log_content)
    assert re.search(r"lifecycle action 'start' -> status 'running'", log_content)
    assert re.search(r"lifecycle action 'stop' -> status 'stopped'", log_content)
    assert re.search(r"Cloned VM:.*clone1", log_content)
    assert "Shutdown requested via /shutdown endpoint." in log_content
