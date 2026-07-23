import pytest
from nimcode.mcp_client import MCPManager

def test_mcp_manager_init():
    config = {"mcp_servers": {"sqlite": {"command": "sqlite3"}}}
    manager = MCPManager(config)
    assert manager.servers["sqlite"]["command"] == "sqlite3"

def test_mcp_manager_initialize():
    config = {"mcp_servers": {"sqlite": {"command": "sqlite3", "args": ["--version"]}}}
    manager = MCPManager(config)
    # Should not crash
    manager.initialize()

def test_get_system_prompt_additions_empty():
    manager = MCPManager({})
    assert manager.get_system_prompt_additions() == ""

def test_get_system_prompt_additions_with_servers():
    config = {"mcp_servers": {"sqlite": {}, "github": {}}}
    manager = MCPManager(config)
    additions = manager.get_system_prompt_additions()
    assert "sqlite" in additions
    assert "github" in additions
