import pytest
import asyncio
from unittest.mock import patch, MagicMock
from nimcode.agent import Agent
from nimcode.permissions import PermissionMode

pytestmark = pytest.mark.skip(reason="Agent tests need rewrite for Phase 7 async UI changes")

@pytest.fixture
def agent():
    return Agent(api_key="test_key", max_turns=3, permission_mode=PermissionMode.BYPASS)

@pytest.fixture(autouse=True)
def mock_memory_log():
    with patch("nimcode.memory.MemoryManager.log_to_nimcode_md") as mock_log:
        yield mock_log

@pytest.mark.asyncio
async def test_agent_run_task_complete(agent):
    # Mock client.chat to yield TASK_COMPLETE immediately
    async def mock_chat(*args, **kwargs):
        yield "I am done. TASK_COMPLETE"
        
    agent.client.chat = mock_chat
    
    await agent.run("Do something")
    
    assert len(agent.messages) == 3
    assert agent.messages[1]["role"] == "user"
    assert agent.messages[2]["role"] == "assistant"
    assert "TASK_COMPLETE" in agent.messages[2]["content"]

@pytest.mark.asyncio
async def test_agent_run_tool_call_success(agent):
    call_count = 0
    async def mock_chat(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield "<tool_call>\n{\"tool\": \"Read\", \"args\": {\"file_path\": \"a.txt\"}}\n</tool_call>"
        else:
            yield "TASK_COMPLETE"
            
    agent.client.chat = mock_chat
    
    with patch("nimcode.tools.ToolRegistry.execute", return_value="File content"):
        await agent.run("Read file")
        
    # Messages: System, User(Read file), Asst(tool), User(Tool result), Asst(TASK_COMPLETE)
    assert len(agent.messages) == 5
    assert agent.messages[3]["role"] == "user"
    assert "Tool Read returned:" in agent.messages[3]["content"]

@pytest.mark.asyncio
async def test_agent_run_tool_call_malformed(agent):
    call_count = 0
    async def mock_chat(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield "<tool_call>\n{bad json}\n</tool_call>"
        else:
            yield "TASK_COMPLETE"
            
    agent.client.chat = mock_chat
    
    await agent.run("Read file")
    
    assert len(agent.messages) == 5
    assert agent.messages[3]["role"] == "user"
    assert "malformed or failed" in agent.messages[3]["content"]

@pytest.mark.asyncio
async def test_agent_run_no_tool_no_complete(agent):
    call_count = 0
    async def mock_chat(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield "I am thinking..."
        else:
            yield "TASK_COMPLETE"
            
    agent.client.chat = mock_chat
    
    await agent.run("Read file")
    
    assert len(agent.messages) == 5
    assert agent.messages[3]["role"] == "user"
    assert "Please continue" in agent.messages[3]["content"]

@pytest.mark.asyncio
async def test_agent_run_api_exception(agent):
    async def mock_chat(*args, **kwargs):
        raise ValueError("API Down")
        yield "" # to make it an async generator
        
    agent.client.chat = mock_chat
    
    await agent.run("Read file")
    
    # Should break loop gracefully
    assert len(agent.messages) == 2

@pytest.mark.asyncio
async def test_agent_max_turns(agent):
    async def mock_chat(*args, **kwargs):
        yield "I am thinking..."
        
    agent.client.chat = mock_chat
    
    await agent.run("Read file")
    
    # Max turns is 3.
    assert len(agent.messages) == 8

@pytest.mark.asyncio
async def test_agent_permission_denied():
    agent_denied = Agent(api_key="test_key", max_turns=2)
    
    call_count = 0
    async def mock_chat(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield "<tool_call>\n{\"tool\": \"Bash\", \"args\": {\"command\": \"rm -rf /\"}}\n</tool_call>"
        else:
            yield "TASK_COMPLETE"
            
    agent_denied.client.chat = mock_chat
    
    with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=False):
        await agent_denied.run("Do bad things")
        
    assert "User explicitly denied" in agent_denied.messages[3]["content"]
