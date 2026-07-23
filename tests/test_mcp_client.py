import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from nimcode.mcp_client import MCPManager

def test_mcp_manager_init():
    config = {"mcp_servers": {"sqlite": {"command": "sqlite3"}}}
    manager = MCPManager(config)
    assert manager.servers["sqlite"]["command"] == "sqlite3"

@pytest.mark.asyncio
async def test_mcp_manager_initialize_no_servers():
    manager = MCPManager({})
    await manager.connect_all()
    assert not manager.sessions

@pytest.mark.asyncio
async def test_mcp_manager_initialize_import_error():
    config = {"mcp_servers": {"sqlite": {"command": "sqlite3", "args": ["--version"]}}}
    manager = MCPManager(config)
    with patch("builtins.__import__", side_effect=ImportError("No module named mcp")):
        await manager.connect_all()
    assert not manager.sessions

@pytest.mark.asyncio
async def test_mcp_manager_close():
    manager = MCPManager({})
    manager.exit_stack = AsyncMock()
    await manager.close()
    manager.exit_stack.aclose.assert_awaited_once()

def test_get_system_prompt_additions_empty():
    manager = MCPManager({})
    assert manager.get_system_prompt_additions() == ""

def test_get_system_prompt_additions_with_servers():
    config = {"mcp_servers": {"sqlite": {}, "github": {}}}
    manager = MCPManager(config)
    manager.sessions = {"sqlite": "fake_session", "github": "fake_session"}
    
    # Create fake tools
    class FakeTool:
        def __init__(self, name, description):
            self.name = name
            self.description = description
            
    manager.server_tools = {
        "sqlite": [FakeTool("query", "run query")], 
        "github": []
    }
    additions = manager.get_system_prompt_additions()
    assert "sqlite" in additions
    assert "github" in additions
    assert "query" in additions
    assert "run query" in additions

@pytest.mark.asyncio
async def test_call_tool_by_name():
    manager = MCPManager({})
    class FakeTool:
        def __init__(self, name):
            self.name = name
    manager.server_tools = {"sqlite": [FakeTool("query")]}
    
    fake_session = AsyncMock()
    fake_session.call_tool.return_value = "success"
    manager.sessions = {"sqlite": fake_session}
    
    result = await manager.call_tool_by_name("query", {"sql": "SELECT 1"})
    assert result == "success"
    fake_session.call_tool.assert_awaited_with("query", {"sql": "SELECT 1"})
    
    with pytest.raises(ValueError, match="MCP Tool not_found not found"):
        await manager.call_tool_by_name("not_found", {})

@pytest.mark.asyncio
async def test_call_tool():
    manager = MCPManager({})
    fake_session = AsyncMock()
    fake_session.call_tool.return_value = "success"
    manager.sessions = {"sqlite": fake_session}
    
    result = await manager.call_tool("sqlite", "query", {})
    assert result == "success"
    
    with pytest.raises(ValueError, match="Server unknown not found"):
        await manager.call_tool("unknown", "query", {})

@pytest.mark.asyncio
async def test_mcp_manager_connect_all_success():
    import sys
    from contextlib import asynccontextmanager
    
    config = {"mcp_servers": {"sqlite": {"command": "sqlite3", "args": ["--version"]}}}
    manager = MCPManager(config)
    
    # Mock the mcp SDK
    mcp_mock = MagicMock()
    
    session_instance = AsyncMock()
    session_instance.initialize = AsyncMock()
    
    class FakeListToolsResponse:
        def __init__(self):
            self.tools = ["tool1", "tool2"]
            
    session_instance.list_tools = AsyncMock(return_value=FakeListToolsResponse())
    
    @asynccontextmanager
    async def fake_stdio_client(*args, **kwargs):
        yield ("read", "write")
        
    @asynccontextmanager
    async def fake_ClientSession(*args, **kwargs):
        yield session_instance
        
    mcp_mock.client.stdio.stdio_client = fake_stdio_client
    mcp_mock.client.stdio.StdioServerParameters = MagicMock()
    mcp_mock.client.session.ClientSession = fake_ClientSession
    
    sys.modules['mcp'] = mcp_mock
    sys.modules['mcp.client'] = mcp_mock.client
    sys.modules['mcp.client.stdio'] = mcp_mock.client.stdio
    sys.modules['mcp.client.session'] = mcp_mock.client.session
    
    await manager.connect_all()
    
    assert "sqlite" in manager.sessions
    assert manager.server_tools["sqlite"] == ["tool1", "tool2"]
    
    # Test error during connection
    session_instance.list_tools.side_effect = Exception("Failed")
    config2 = {"mcp_servers": {"bad_server": {}}}
    manager2 = MCPManager(config2)
    await manager2.connect_all()
    assert "bad_server" not in manager2.server_tools
