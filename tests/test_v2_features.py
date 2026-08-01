import pytest
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock
from nimcode.nim_client import NimClient
from nimcode.agent import Agent
from nimcode.repo_map import _extract_symbols
from nimcode.agents.subagent import SubAgent
from nimcode.mcp_client import MCPManager
from nimcode.tools import ToolRegistry
import httpx

@pytest.mark.asyncio
async def test_nim_client_chat_one_shot_retry():
    client = NimClient("fake-key")
    client.retry_base_delay = 0.01  # speed up test
    
    mock_post = AsyncMock()
    # Simulate a 429 response first, then success
    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Too Many Requests", request=MagicMock(), response=mock_429
    )
    
    mock_success = MagicMock()
    mock_success.status_code = 200
    mock_success.json.return_value = {"choices": [{"message": {"content": "Success"}}]}
    
    mock_post.side_effect = [mock_429, mock_success]
    
    with patch("httpx.AsyncClient.post", new=mock_post):
        result = await client.chat_one_shot("Hello")
        assert result == "Success"
        assert mock_post.call_count == 2

@pytest.mark.asyncio
async def test_repo_map_extract_symbols(tmp_path):
    py_file = tmp_path / "test.py"
    py_file.write_text("class MyTestClass:\n    pass\n\ndef my_method():\n    pass\n")
    
    symbols = _extract_symbols(str(py_file))
    assert "class MyTestClass" in symbols
    assert "def my_method()" in symbols
    
    ts_file = tmp_path / "test.ts"
    ts_file.write_text("export class MyTSClass {}\nexport const myFunc = () => {}\n")
    ts_symbols = _extract_symbols(str(ts_file))
    assert "🔹 MyTSClass" in ts_symbols
    assert "🔹 myFunc" in ts_symbols

@pytest.mark.asyncio
async def test_subagent_delegation():
    # Mock agent headless run
    with patch("nimcode.agents.subagent.Agent.run_headless", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = "TASK_COMPLETE"
        sub = SubAgent("fake-key")
        result = await sub.execute_task("Do something", ["file1.py"])
        assert "TASK_COMPLETE" in result

@pytest.mark.asyncio
async def test_mcp_manager_dynamic_add():
    manager = MCPManager({})
    
    with patch("mcp.client.stdio.stdio_client") as mock_client:
        with patch("mcp.client.session.ClientSession") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.list_tools = AsyncMock()
            mock_session_instance.list_tools.return_value = MagicMock(tools=[MagicMock(name="test_tool", description="A test")])
            
            # Context manager mocking
            mock_client_cm = AsyncMock()
            mock_client_cm.__aenter__.return_value = (MagicMock(), MagicMock())
            mock_client.return_value = mock_client_cm
            
            mock_session_cm = AsyncMock()
            mock_session_cm.__aenter__.return_value = mock_session_instance
            mock_session.return_value = mock_session_cm
            
            await manager.add_server("test-server", "echo", ["hello"])
            assert "test-server" in manager.sessions
            assert len(manager.server_tools["test-server"]) == 1
            
            # Now remove
            await manager.remove_server("test-server")
            assert "test-server" not in manager.sessions

def test_tools_registry_delegate_task():
    schema = ToolRegistry.get_tool_schema("DelegateTask")
    assert schema is not None
    assert "task_description" in schema["parameters"]
    assert "target_files" in schema["parameters"]

def test_tools_registry_call_mcp():
    schema = ToolRegistry.get_tool_schema("CallMCP")
    assert schema is not None
    assert "mcp_tool_name" in schema["parameters"]
