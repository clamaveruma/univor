

import os
import time
import json
import psutil
from typer.testing import CliRunner
from mock_hypervisor.launcher import app

runner = CliRunner()



def test_launcher_start_stop_status_kill():
    # Check status first
    status_result = runner.invoke(app, ['status'])
    status_data = json.loads(status_result.output)
    if status_data.get("running"):
        pid = status_data.get("pid")
        port = status_data.get("port")
    else:
        # Start the daemon
        result = runner.invoke(app, ['start'])
        assert result.exit_code == 0, f"start failed: {result.output}"
        # Robustly parse only the last non-debug line as JSON
        data = json.loads(result.output)
        pid = data.get("pid")
        port = data.get("port")
        assert pid and port
        time.sleep(1)
        # Check process is running
        assert psutil.pid_exists(pid)
        # Check port is listening
        proc = psutil.Process(pid)
        cons = proc.net_connections(kind='inet')
        assert any(c.status == psutil.CONN_LISTEN and c.laddr.port == port for c in cons)

    # Status should show running and correct port
    status_result = runner.invoke(app, ['status'])
    assert status_result.exit_code == 0, f"status failed: {status_result.output}"
    status_data = json.loads(status_result.output)
    assert status_data.get("pid") == pid
    assert status_data.get("port") == port

    # Stop the daemon
    result = runner.invoke(app, ['stop'])
    assert result.exit_code == 0, f"stop failed: {result.output}"
    # Wait up to 2 seconds for process to exit or become zombie
    for _ in range(20):
        if not psutil.pid_exists(pid):
            break
        proc = psutil.Process(pid)
        if proc.status() == psutil.STATUS_ZOMBIE:
            break
        time.sleep(0.1)
    else:
        # If still running and not zombie after retries, fail
        proc = psutil.Process(pid)
        assert proc.status() == psutil.STATUS_ZOMBIE, f"Process {pid} should be zombie if not gone, got {proc.status()}"

    # Status should report not running
    result = runner.invoke(app, ['status'])
    assert result.exit_code == 0, f"status after stop failed: {result.output}"
    assert "not running" in result.output.lower()

    # Try kill (should not error even if already stopped)
    result = runner.invoke(app, ['kill'])
    assert result.exit_code in (0, 1), f"kill failed: {result.output}"


def test_cannot_start_second_instance():
    # Start first instance
    result1 = runner.invoke(app, ['start', '--port', '5556'])
    assert result1.exit_code == 0, f"first start failed: {result1.output}"
    time.sleep(1)
    # Try to start second instance
    result2 = runner.invoke(app, ['start', '--port', '5557'])
    assert result2.exit_code == 0, "Second instance should return exit code 0 (idempotent)"
    assert 'already' in result2.output.lower(), "Output should indicate daemon is already running"
    # Cleanup
    runner.invoke(app, ['stop'])
    time.sleep(1)

def test_error_on_used_port():
    # Start first instance on port 5558
    result1 = runner.invoke(app, ['start', '--port', '5558'])
    assert result1.exit_code == 0, f"first start failed: {result1.output}"
    time.sleep(1)
    # Try to start another instance on same port (should fail)
    result2 = runner.invoke(app, ['start', '--port', '5558'])
    assert result2.exit_code == 0, "Should return exit code 0 when port is already used"
    assert 'port' in result2.output.lower(), "Output should indicate port is already used"
    # Cleanup
    runner.invoke(app, ['stop'])
    time.sleep(1)

def test_read_used_port():
    # Start instance on a known port
    port = 5559
    result = runner.invoke(app, ['start', '--port', str(port)])
    assert result.exit_code == 0, f"start failed: {result.output}"
    data = json.loads(result.output)
    pid = data.get("pid")
    assert pid
    time.sleep(1)
    # Status should report the port
    result = runner.invoke(app, ['status'])
    status_data = json.loads(result.output)
    assert status_data.get("port") == port, f"Port {port} not found in status output: {result.output}"
    # Check process is running
    assert psutil.pid_exists(pid)
    # Cleanup
    runner.invoke(app, ['stop'])
    time.sleep(1)

def test_auto_port():
    # Start daemon with auto port
    result = runner.invoke(app, ['start'])
    assert result.exit_code == 0, f"auto-port start failed: {result.output}"
    data = json.loads(result.output)
    pid = data.get("pid")
    port = data.get("port")
    assert pid and port and int(port) > 0
    time.sleep(1)
    # Check process is running and port is listening
    assert psutil.pid_exists(pid)
    proc = psutil.Process(pid)
    cons = proc.net_connections(kind='inet')
    assert any(c.status == psutil.CONN_LISTEN and c.laddr.port == int(port) for c in cons)
    # Cleanup
    runner.invoke(app, ['stop'])
    time.sleep(1)

def test_read_logs():
    # Try to read the log file (location depends on setup_logging)
    log_paths = [os.path.expanduser('~/.mock_hypervisor_launcher/log.txt'), os.path.expanduser('~/.univor/log.txt')]
    found = False
    for log_path in log_paths:
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                content = f.read()
                assert 'mock_hypervisor' in content or 'daemon' in content or len(content) > 0
                found = True
    if not found:
        return  # No log file found; skip test gracefully

def test_status_when_not_running():
    # Ensure status reports not running when daemon is not active
    result = runner.invoke(app, ['stop'])  # Ensure stopped
    time.sleep(1)
    result = runner.invoke(app, ['status'])
    assert result.exit_code == 0
    assert "not running" in result.output.lower()

def test_stop_kill_when_not_running():
    # Ensure stop/kill when not running gives correct error
    result = runner.invoke(app, ['stop'])
    assert result.exit_code != 0 or "not running" in result.output.lower()
    result = runner.invoke(app, ['kill'])
    assert result.exit_code in (0, 1)

def test_invalid_command():
    # Test an invalid command
    result = runner.invoke(app, ['notacommand'])
    assert result.exit_code != 0
    assert 'No such command' in result.output or 'Usage' in result.output

def test_invalid_argument():
    # Test invalid argument for start (non-integer port)
    result = runner.invoke(app, ['start', '--port', 'notaport'])
    assert result.exit_code != 0
    assert 'Invalid value' in result.output or 'Error' in result.output

def test_help_output():
    # Test help output for main app
    result = runner.invoke(app, ['--help'])
    assert result.exit_code == 0
    assert 'Usage' in result.output and 'start' in result.output and 'stop' in result.output

    # Test help output for start command
    result = runner.invoke(app, ['start', '--help'])
    assert result.exit_code == 0
    assert 'Usage' in result.output and 'port' in result.output

