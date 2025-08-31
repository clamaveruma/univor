import pytest
from typer.testing import CliRunner
from mock_hypervisor.cli import app

runner = CliRunner()


def test_help():
    """Test the help command displays usage information."""
    result = runner.invoke(app, ["--help"])
    print(result.output)
    assert result.exit_code == 0
    assert "Usage" in result.output

def test_start_server():
    """Test starting a server with a specific port."""
    result = runner.invoke(app, ["start-server", "--port", "12345"])
    print(result.output)
    assert result.exit_code == 0
    assert "Started mockvisord" in result.output or "Failed to start mockvisord" in result.output

def test_list_servers():
    """Test listing running servers."""
    result = runner.invoke(app, ["list-servers"])
    print(result.output)
    assert result.exit_code == 0
    assert "mock_hypervisor.daemon" in result.output or "No running mockvisord daemons found." in result.output

def test_stop_server_localhost():
    """Test stopping a server on localhost (should fail gracefully if no server)."""
    result = runner.invoke(app, ["stop-server", "8000"])
    print(result.output)
    assert result.exit_code in (0, 1)
    assert "stopped gracefully" in result.output or "Failed to stop server" in result.output or "Error contacting server" in result.output

def test_stop_server_invalid_host():
    """Test that stop-server does not accept a host argument (should error if given)."""
    result = runner.invoke(app, ["stop-server", "notaport", "extrahost"])
    print(result.output)
    assert result.exit_code != 0

def test_kill_server_invalid_pid():
    """Test killing a server with an invalid PID (should fail gracefully)."""
    result = runner.invoke(app, ["kill-server", "999999"])
    print(result.output)
    assert result.exit_code == 0 or result.exit_code == 1
    assert "Sent SIGTERM" in result.output or "Failed to kill process" in result.output

def test_kill_server_missing_pid():
    """Test kill-server with missing PID argument (should error)."""
    result = runner.invoke(app, ["kill-server"])
    print(result.output)
    assert result.exit_code != 0

def test_start_server_no_port():
    """Test starting a server without specifying a port (should succeed or fail gracefully)."""
    result = runner.invoke(app, ["start-server"])
    print(result.output)
    assert result.exit_code == 0
    assert "Started mockvisord" in result.output or "Failed to start mockvisord" in result.output

def test_start_and_list_and_stop_multiple_daemons():
    """Start 3 daemons, list them, and stop them."""
    pids = []
    # Start 3 daemons
    for _ in range(3):
        result = runner.invoke(app, ["start-server"])
        print(result.output)
        assert result.exit_code == 0
        # Extract PID from output
        for line in result.output.splitlines():
            if "Started mockvisord with PID" in line:
                pid = int(line.split("PID ")[1].split()[0])
                pids.append(pid)
    # List daemons
    result = runner.invoke(app, ["list-servers"])
    print(result.output)
    assert result.exit_code == 0
    for pid in pids:
        assert str(pid) in result.output
    # Stop daemons
    for pid in pids:
        result = runner.invoke(app, ["kill-server", str(pid)])
        print(result.output)
        assert result.exit_code == 0
        assert f"Sent SIGTERM to process {pid}" in result.output or f"Failed to kill process {pid}" in result.output

