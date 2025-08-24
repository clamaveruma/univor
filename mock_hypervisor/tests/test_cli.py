import pytest
from typer.testing import CliRunner
from mock_hypervisor.cli import app

runner = CliRunner()

def test_start_server():
    result = runner.invoke(app, ["start-server", "--port", "12345"])
    assert result.exit_code == 0
    assert "Server started on port 12345" in result.output

def test_list_servers():
    result = runner.invoke(app, ["list-servers"])
    assert result.exit_code == 0
    assert "Listing servers" in result.output

def test_kill_server():
    result = runner.invoke(app, ["kill-server", "12345"])
    assert result.exit_code == 0
    assert "Killed server 12345" in result.output

