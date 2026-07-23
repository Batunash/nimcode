import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from nimcode.agent import Agent
from nimcode.permissions import PermissionMode
import json

@pytest.fixture
def agent():
    return Agent(api_key="test_key", max_turns=3, permission_mode=PermissionMode.BYPASS)

def test_agent_init(agent):
    assert agent.client.api_key == "test_key"
    assert agent.max_turns == 3
    assert len(agent.messages) == 1
    assert agent.messages[0]["role"] == "system"

def test_save_load_history(agent, tmp_path):
    import os
    from unittest.mock import patch
    agent.messages.append({"role": "user", "content": "hi"})
    
    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        agent.save_history()
        # Ensure it attempts to dump
        assert mock_file.write.called
        
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", new_callable=MagicMock) as mock_open:
            mock_file = MagicMock()
            mock_file.read.return_value = json.dumps([{"role": "system", "content": "old"}])
            mock_open.return_value.__enter__.return_value = mock_file
            agent.load_history()
            assert agent.messages[0]["content"] == "old"

@pytest.mark.asyncio
async def test_run_headless_complete(agent):
    agent.client.chat_one_shot = AsyncMock(return_value="I am done. TASK_COMPLETE")
    agent.parser = MagicMock()
    agent.parser.parse.return_value = []
    res = await agent.run_headless("Do something", max_turns=3)
    assert res == "I am done. TASK_COMPLETE"
    assert len(agent.messages) == 3
    assert agent.messages[1]["role"] == "user"
    assert agent.messages[2]["role"] == "assistant"

@pytest.mark.asyncio
async def test_run_headless_tool_call(agent):
    call_count = 0
    async def mock_chat_one_shot(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "<tool_call>\n{\"tool\": \"Read\", \"args\": {\"file_path\": \"a.txt\"}}\n</tool_call>"
        else:
            return "TASK_COMPLETE"
            
    agent.client.chat_one_shot = mock_chat_one_shot
    agent.parser = MagicMock()
    agent.parser.parse.side_effect = [
        [{"tool": "Read", "args": {"file_path": "a.txt"}}],
        []
    ]
    
    with patch("nimcode.tools.ToolRegistry.execute", return_value="File content"):
        res = await agent.run_headless("Read file", max_turns=3)
        assert res == "TASK_COMPLETE"
        
    assert len(agent.messages) == 5
    assert agent.messages[3]["role"] == "user"
    assert "Tool Read returned:" in agent.messages[3]["content"]
    assert "File content" in agent.messages[3]["content"]

@pytest.mark.asyncio
async def test_run_headless_exception(agent):
    agent.client.chat_one_shot = AsyncMock(side_effect=Exception("API Down"))
    res = await agent.run_headless("Read file", max_turns=3)
    assert "Subagent error" in res
    assert "API Down" in res

@pytest.mark.asyncio
async def test_run_headless_max_turns(agent):
    agent.client.chat_one_shot = AsyncMock(return_value="<tool_call>\n{\"tool\": \"Read\", \"args\": {\"file_path\": \"a.txt\"}}\n</tool_call>")
    agent.parser = MagicMock()
    agent.parser.parse.return_value = [{"tool": "Read", "args": {"file_path": "a.txt"}}]
    
    with patch("nimcode.tools.ToolRegistry.execute", return_value="File content"):
        res = await agent.run_headless("Read file", max_turns=2)
        assert "max turns" in res

@pytest.mark.asyncio
async def test_distill_memory(agent):
    # Setup some old messages
    for i in range(10):
        agent.messages.append({"role": "user", "content": f"msg {i}"})
        
    agent.client.chat_one_shot = AsyncMock(return_value="Summarized history")
    
    new_msgs = await agent._distill_memory()
    assert "[PREVIOUS MEMORY SUMMARY]" in agent.messages[0]["content"]
    assert "Summarized history" in agent.messages[0]["content"]
    assert len(new_msgs) == 5

@pytest.mark.asyncio
async def test_stream_response_success(agent):
    from unittest.mock import patch, MagicMock
    
    # Mocking the client.chat generator
    async def mock_gen():
        yield "Thinking..."
        yield " Done!"
    
    class FakeGenerator:
        def __init__(self):
            self._gen = mock_gen()
        def __aiter__(self):
            return self._gen
            
    agent.client.chat = MagicMock(return_value=FakeGenerator())
    
    res = await agent._stream_response()
    assert "Thinking... Done!" in res

@pytest.mark.asyncio
async def test_run_subagent_max_turns(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    
    agent._stream_response = AsyncMock(return_value="Something")
    
    await agent.run("Hi")
    assert agent.messages[-1]["role"] == "user"
    assert "Please continue" in agent.messages[-1]["content"]

@pytest.mark.asyncio
async def test_run_subagent_tool_denied(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent._stream_response = AsyncMock(return_value="<tool_call>{\"tool\": \"Read\", \"args\": {}}</tool_call>")
    
    with patch("nimcode.lenient_parser.LenientParser.process_model_response") as mock_parse:
        mock_parse.return_value = ("prose", [{"tool": "Read", "args": {}}])
        with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=False):
            await agent.run("Hi")
            assert "User explicitly denied" in agent.messages[-1]["content"]

@pytest.mark.asyncio
async def test_run_subagent_tool_success(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent.max_turns = 2
    agent._stream_response = AsyncMock(side_effect=["<tool_call>{\"tool\": \"Read\", \"args\": {}}</tool_call>", "TASK_COMPLETE"])
    
    with patch("nimcode.lenient_parser.LenientParser.process_model_response") as mock_parse:
        mock_parse.side_effect = [
            ("prose", [{"tool": "Read", "args": {}}]),
            ("prose", [])
        ]
        with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=True):
            with patch("nimcode.tools.ToolRegistry.get_tool_schema", return_value={"name": "Read"}):
                with patch("nimcode.tools.ToolRegistry.execute", return_value="Output"):
                    await agent.run("Hi")
                    # Should reach TASK_COMPLETE

@pytest.mark.asyncio
async def test_run_subagent_tool_error(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent.max_turns = 2
    agent._stream_response = AsyncMock(side_effect=["<tool_call>{\"tool\": \"Read\", \"args\": {}}</tool_call>", "TASK_COMPLETE"])
    
    with patch("nimcode.lenient_parser.LenientParser.process_model_response") as mock_parse:
        mock_parse.side_effect = [
            ("prose", [{"tool": "Read", "args": {}}]),
            ("prose", [])
        ]
        with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=True):
            with patch("nimcode.tools.ToolRegistry.get_tool_schema", return_value={"name": "Read"}):
                with patch("nimcode.tools.ToolRegistry.execute", side_effect=Exception("Read Error")):
                    await agent.run("Hi")
                    assert "Your tool call was malformed or failed: Read Error" in agent.messages[-2]["content"]

@pytest.mark.asyncio
async def test_run_subagent_mcp_tool(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent.max_turns = 2
    agent._stream_response = AsyncMock(side_effect=["<tool_call>{\"tool\": \"Read\", \"args\": {}}</tool_call>", "TASK_COMPLETE"])
    
    with patch("nimcode.lenient_parser.LenientParser.process_model_response") as mock_parse:
        mock_parse.side_effect = [
            ("prose", [{"tool": "Read", "args": {}}]),
            ("prose", [])
        ]
        with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=True):
            with patch("nimcode.tools.ToolRegistry.get_tool_schema", return_value=None):
                
                class MockCallToolResult:
                    def __init__(self, text):
                        self.text = text
                class MockMCPResult:
                    def __init__(self):
                        self.content = [MockCallToolResult("MCP Output")]
                        
                agent.mcp.call_tool_by_name = AsyncMock(return_value=MockMCPResult())
                await agent.run("Hi")
                assert "Tool Read returned:\nMCP Output" in agent.messages[-2]["content"]

@pytest.mark.asyncio
async def test_run_subagent_mcp_tool_error(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent.max_turns = 2
    agent._stream_response = AsyncMock(side_effect=["<tool_call>{\"tool\": \"Read\", \"args\": {}}</tool_call>", "TASK_COMPLETE"])
    
    with patch("nimcode.lenient_parser.LenientParser.process_model_response") as mock_parse:
        mock_parse.side_effect = [
            ("prose", [{"tool": "Read", "args": {}}]),
            ("prose", [])
        ]
        with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=True):
            with patch("nimcode.tools.ToolRegistry.get_tool_schema", return_value=None):
                agent.mcp.call_tool_by_name = AsyncMock(side_effect=Exception("MCP Down"))
                await agent.run("Hi")
                assert "Error executing MCP tool Read: MCP Down" in agent.messages[-2]["content"]

def test_agent_git_context_error():
    with patch("os.path.exists", return_value=True):
        with patch("subprocess.check_output", side_effect=Exception("Git error")):
            agent = Agent(api_key="key")
            assert "GIT CONTEXT" not in agent.messages[0]["content"]
            
def test_agent_load_skills(tmp_path):
    nimcode_dir = tmp_path / ".nimcode"
    nimcode_dir.mkdir()
    skills_dir = nimcode_dir / "skills"
    skills_dir.mkdir()
    (skills_dir / "skill1.md").write_text("Do good stuff")
    
    with patch("os.getcwd", return_value=str(tmp_path)):
        agent = Agent(api_key="key")
        assert "CRITICAL USER SKILLS" in agent.messages[0]["content"]
        assert "Do good stuff" in agent.messages[0]["content"]

@pytest.mark.asyncio
async def test_agent_auto_linting_py(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent.max_turns = 2
    agent._stream_response = AsyncMock(side_effect=["<tool_call>{\"tool\": \"Write\", \"args\": {\"file_path\": \"test.py\"}}</tool_call>", "TASK_COMPLETE"])
    
    with patch("nimcode.lenient_parser.LenientParser.process_model_response") as mock_parse:
        mock_parse.side_effect = [
            ("prose", [{"tool": "Write", "args": {"file_path": "test.py"}}]),
            ("prose", [])
        ]
        with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=True):
            with patch("nimcode.tools.ToolRegistry.get_tool_schema", return_value={"name": "Write"}):
                with patch("nimcode.tools.ToolRegistry.execute", return_value="Diff:\n+ print('hello')"):
                    with patch("subprocess.run") as mock_run:
                        # Mock flake8 error
                        mock_run.return_value = MagicMock(returncode=1, stdout="Syntax error")
                        await agent.run("Hi")
                        assert "Auto-Linter found errors:" in agent.messages[-2]["content"]

@pytest.mark.asyncio
async def test_agent_auto_linting_js(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent.max_turns = 2
    agent._stream_response = AsyncMock(side_effect=["<tool_call>{\"tool\": \"Write\", \"args\": {\"file_path\": \"test.js\"}}</tool_call>", "TASK_COMPLETE"])
    
    with patch("nimcode.lenient_parser.LenientParser.process_model_response") as mock_parse:
        mock_parse.side_effect = [
            ("prose", [{"tool": "Write", "args": {"file_path": "test.js"}}]),
            ("prose", [])
        ]
        with patch("nimcode.permissions.PermissionEngine.check_permission", return_value=True):
            with patch("nimcode.tools.ToolRegistry.get_tool_schema", return_value={"name": "Write"}):
                with patch("nimcode.tools.ToolRegistry.execute", return_value="Output"):
                    with patch("subprocess.run") as mock_run:
                        await agent.run("Hi")
                        assert mock_run.call_count == 1
                        assert "prettier" in mock_run.call_args[0][0]

@pytest.mark.asyncio
async def test_distill_memory_context_full(agent):
    agent.mcp = MagicMock()
    agent.mcp.connect_all = AsyncMock()
    agent._stream_response = AsyncMock(return_value="TASK_COMPLETE")
    
    # Fake large token count
    agent.memory.count_messages_tokens = MagicMock(return_value=5000)
    agent.memory.max_tokens = 4000
    agent._distill_memory = AsyncMock(return_value=[{"role": "system", "content": "Distilled"}])
    
    await agent.run("Hi")
    assert agent.messages[0]["content"] == "Distilled"
